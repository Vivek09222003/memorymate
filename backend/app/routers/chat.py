"""The conversation endpoint: the user says something, MemoryMate understands it.

Flow:  save the user's message → ask Gemini (with people, approved memories and
recent chat as context) → store any facts as PENDING memories → save and return the reply.
A plain "yes" / "no" right after a question is handled directly (see confirmations.py).
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import confirmations
from app.ai import AIError, understand
from app.database import get_db
from app.models import (Memory, MemoryStatus, MemoryType, Message, OccurrenceStatus, Person,
                        ReminderOccurrence, User, Visibility)
from app.retrieval import search
from app.schemas import ChatIn, ChatOut
from app.security import get_current_user
from app.timeutil import local_now, local_tz, show

router = APIRouter(prefix="/chat", tags=["Chat"])


def _safe_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _told_on(memory: Memory) -> str:
    """The day the user told us this, in their own time zone (e.g. '22 November 2026')."""
    if memory.created_at is None:
        return "unknown"
    local = memory.created_at.astimezone(local_now().tzinfo)
    return local.strftime("%d %B %Y").lstrip("0")


STATUS_WORDS = {
    OccurrenceStatus.DONE: "done (taken)",
    OccurrenceStatus.MISSED: "missed, not marked done",
    OccurrenceStatus.DUE: "ringing now, not answered yet",
    OccurrenceStatus.SCHEDULED: "upcoming",
    OccurrenceStatus.SKIPPED: "cancelled",
}


def _reminder_lines(db: Session, user: User) -> list[str]:
    """Today's and the next 7 days' reminders, so the AI can answer 'Did I take my 8 PM medicine?'."""
    start = datetime.combine(local_now().date(), datetime.min.time(), tzinfo=local_tz())
    alerts = db.scalars(
        select(ReminderOccurrence)
        .where(ReminderOccurrence.owner_id == user.id,
               ReminderOccurrence.is_main.is_(True),
               ReminderOccurrence.for_due_at >= start,
               ReminderOccurrence.for_due_at < start + timedelta(days=8))
        .order_by(ReminderOccurrence.for_due_at)
        .limit(40)
    ).all()
    return [f"- {show(o.for_due_at)}: {o.reminder.title} ({o.reminder.kind.value.lower()}"
            f"{', ' + o.reminder.notes if o.reminder.notes else ''}) - {STATUS_WORDS[o.status]}" for o in alerts]


def _memory_for_ai(m: Memory) -> dict:
    replaced_on = m.valid_to.strftime("%d %B %Y").lstrip("0") if m.valid_to else None
    return {"id": m.id, "fact": m.normalized_fact, "told_on": _told_on(m),
            "replaced_on": replaced_on if m.status == MemoryStatus.HISTORICAL else None,
            "unsure": m.confidence < 0.7}


def _same(a: str | None, b: str | None) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def _already_known(active: list[Memory], c, person_id: int | None) -> bool:
    """True if this exact fact is already remembered."""
    return any(m.person_id == person_id and c.attribute and _same(m.attribute, c.attribute)
               and _same(m.value, c.value) for m in active)


def _already_waiting(db: Session, owner_id: int, c, person_id: int | None) -> Memory | None:
    """The same fact, already waiting for the user's yes/no (so we show it again instead of a copy)."""
    waiting = db.scalars(select(Memory).where(Memory.owner_id == owner_id,
                                              Memory.status == MemoryStatus.PENDING)).all()
    for m in waiting:
        if _same(m.normalized_fact, c.normalized_fact) or (
                c.attribute and m.person_id == person_id
                and _same(m.attribute, c.attribute) and _same(m.value, c.value)):
            return m
    return None


def _what_it_replaces(c, person_id: int | None, relevant_by_id: dict[int, Memory],
                      active: list[Memory]) -> int | None:
    """Which current memory this new fact corrects, if any.
    1. The AI's pick, if it is a real, current memory of this user.
    2. Otherwise: same person + same attribute with a different value (e.g. city: Bangalore → Hyderabad)."""
    picked = relevant_by_id.get(c.replaces_memory_id or -1)
    if picked is not None and picked.status == MemoryStatus.ACTIVE:
        return picked.id
    if person_id is not None and c.attribute:
        for m in active:
            if m.person_id == person_id and _same(m.attribute, c.attribute) and not _same(m.value, c.value):
                return m.id
    return None


def _find_person(people: list[Person], name: str | None, relation: str | None) -> Person | None:
    """Match the AI's 'Ananya' or 'granddaughter' to a saved person."""
    if name:
        for p in people:
            if p.name.lower() == name.strip().lower():
                return p
    if relation:
        matches = [p for p in people if (p.relation_to_user or "").lower() == relation.strip().lower()]
        if len(matches) == 1:  # only if it's unambiguous
            return matches[0]
    return None


@router.post("", response_model=ChatOut)
def chat(data: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 0. A plain "yes" / "no" answers what MemoryMate just asked. No AI call, no ids.
    answer = confirmations.yes_or_no(data.message)
    asked = confirmations.load(db, user.id)
    if answer and confirmations.has_questions(asked):
        db.add(Message(owner_id=user.id, role="user", text=data.message, language=user.preferred_language))
        reply = confirmations.apply(db, user, asked, answer)
        db.add(Message(owner_id=user.id, role="assistant", text=reply, language=user.preferred_language))
        db.commit()
        return ChatOut(reply=reply, intent="CONFIRMATION")

    people = db.scalars(select(Person).where(Person.owner_id == user.id)).all()
    # Only the memories relevant to this message (people first, then by meaning), including
    # older replaced facts so "Where did Rahul live before?" can be answered.
    relevant = [h.memory for h in search(db, user.id, data.message, people,
                                         statuses=(MemoryStatus.ACTIVE, MemoryStatus.HISTORICAL))]
    relevant_by_id = {m.id: m for m in relevant}
    recent = list(reversed(db.scalars(
        select(Message).where(Message.owner_id == user.id).order_by(Message.id.desc()).limit(8)
    ).all()))

    # 1. Save what the user said (memories will point back to this message).
    user_msg = Message(owner_id=user.id, role="user", text=data.message, language=user.preferred_language)
    db.add(user_msg)
    db.flush()  # gives user_msg an id without committing yet

    # 2. Ask the AI.
    try:
        result = understand(
            data.message,
            user_name=user.name,
            language=user.preferred_language,
            people=[{"name": p.name, "relation": p.relation_to_user} for p in people],
            memories=[_memory_for_ai(m) for m in relevant],
            history=[{"role": m.role, "text": m.text} for m in recent],
            reminders=_reminder_lines(db, user),
        )
    except AIError as e:
        db.commit()  # keep the user's message even if the AI failed
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))

    # 3. Store each fact as a PENDING memory. Nothing is permanent until approved.
    active = [m for m in relevant if m.status == MemoryStatus.ACTIVE]
    pending: list[Memory] = []
    for c in result.memories:
        person = _find_person(people, c.person_name, c.relationship)
        person_id = person.id if person else None
        if _already_known(active, c, person_id):
            continue  # already remembered
        waiting = _already_waiting(db, user.id, c, person_id)
        if waiting is not None:
            pending.append(waiting)  # show the one already waiting, so it can be approved
            continue
        memory = Memory(
            owner_id=user.id,
            person_id=person.id if person else None,
            source_message_id=user_msg.id,
            memory_type=MemoryType(c.memory_type),
            original_text=data.message,
            normalized_fact=c.normalized_fact,
            attribute=(c.attribute or None) and c.attribute[:50],
            value=(c.value or None) and c.value[:255],
            event_date=_safe_date(c.event_date),
            confidence=c.confidence,
            status=MemoryStatus.PENDING,
            visibility=Visibility.PRIVATE,
            valid_from=local_now().date(),
            replaces_id=_what_it_replaces(c, person_id, relevant_by_id, active),
        )
        db.add(memory)
        pending.append(memory)

    # Memories the user asked to forget. Only offered here; DELETE /memories/{id} confirms.
    forget = [relevant_by_id[i] for i in result.forget_memory_ids
              if i in relevant_by_id and relevant_by_id[i].status == MemoryStatus.ACTIVE]

    known_names = {p.name.lower() for p in people}
    suggested = [p for p in result.new_people if p.name.strip().lower() not in known_names]

    # 4. Remember what this reply asks about, so a plain "yes" / "no" can answer it next.
    db.flush()  # gives the new memories their ids
    confirmations.save(db, user.id, {
        "memory_ids": [m.id for m in pending],
        "forget_ids": [m.id for m in forget],
        "reminder": result.reminder.model_dump() if result.reminder else None,
        "people": [p.model_dump() for p in suggested],
    })
    waiting = bool(pending or forget or result.reminder or suggested)

    # 5. Save the reply.
    db.add(Message(owner_id=user.id, role="assistant", text=result.reply, language=user.preferred_language))
    db.commit()
    for m in pending:
        db.refresh(m)

    return ChatOut(
        reply=result.reply,
        intent=result.intent,
        pending_memories=pending,
        forget_candidates=forget,
        suggested_people=suggested,
        reminder_suggestion=result.reminder,
        waiting_for_yes_or_no=waiting,
    )
