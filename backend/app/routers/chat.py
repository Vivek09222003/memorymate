"""The conversation endpoint: the user says something, MemoryMate understands it.

Flow:  save the user's message → ask Gemini (with people, approved memories and
recent chat as context) → store any facts as PENDING memories → save and return the reply.
A plain "yes" / "no" right after a question is handled directly (see confirmations.py).
"""
import logging
import re
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import confirmations, emergency, family_access
from app.ai import AIError, translate, understand
from app.database import get_db
from app.models import (FamilyLink, LinkStatus, Memory, MemoryStatus, MemoryType, Message, OccurrenceStatus,
                        Person, Reminder, ReminderOccurrence, ReminderStatus, User, UserRole, Visibility)
from app.retrieval import search
from app.routers.emergency import alert_out
from app.routers.memories import sync_phone
from app.schemas import ChatIn, ChatOut
from app.security import get_current_user
from app.timeutil import local_now, local_tz, show

router = APIRouter(prefix="/chat", tags=["Chat"])
log = logging.getLogger("memorymate.chat")


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


def _reminder_lines(db: Session, user: User, days: int = 8) -> list[str]:
    """Today's and the next 7 days' reminders, so the AI can answer 'Did I take my 8 PM medicine?'."""
    start = datetime.combine(local_now().date(), datetime.min.time(), tzinfo=local_tz())
    alerts = db.scalars(
        select(ReminderOccurrence)
        .where(ReminderOccurrence.owner_id == user.id,
               ReminderOccurrence.is_main.is_(True),
               ReminderOccurrence.for_due_at >= start,
               ReminderOccurrence.for_due_at < start + timedelta(days=days))
        .order_by(ReminderOccurrence.for_due_at)
        .limit(80)
    ).all()
    names = {}
    for o in alerts:
        sid = o.reminder.suggested_by_id
        if sid and sid not in names:
            who = db.get(User, sid)
            names[sid] = who.name if who else "a family member"
    waiting = db.scalars(select(Reminder).where(Reminder.owner_id == user.id,
                                                Reminder.status == ReminderStatus.SUGGESTED)).all()
    waiting_lines = []
    for r in waiting:
        who = db.get(User, r.suggested_by_id) if r.suggested_by_id else None
        waiting_lines.append(f"- [R#{r.id}] {show(r.due_at)}: {r.title} ({r.kind.value.lower()}"
                             f"{', ' + r.notes if r.notes else ''}) - SUGGESTED by "
                             f"{who.name if who else 'a family member'}, NOT accepted yet "
                             f"(the user accepts it with the Accept button)")
    return waiting_lines + [f"- [R#{o.reminder.id}] {show(o.for_due_at)}: {o.reminder.title} ({o.reminder.kind.value.lower()}"
            f"{', ' + o.reminder.notes if o.reminder.notes else ''}"
            f"{', suggested by ' + names[o.reminder.suggested_by_id] + ' and accepted by the user' if o.reminder.suggested_by_id else ', set by the user'})"
            f" - {STATUS_WORDS[o.status]}" for o in alerts]


SHARE_WORDS = re.compile(r"share|family|emergenc|doctor|let .* see|show it|बता|परिवार|आपात|కుటుంబ|అత్యవసర",
                         re.IGNORECASE)


def _safe_visibility(suggested: str, reply: str) -> Visibility:
    """Safety net: a memory is only shared if the question clearly said so. Otherwise it stays private."""
    try:
        wanted = Visibility(suggested)
    except ValueError:
        return Visibility.PRIVATE
    if wanted != Visibility.PRIVATE and not SHARE_WORDS.search(reply or ""):
        return Visibility.PRIVATE
    return wanted


def _memory_for_ai(m: Memory) -> dict:
    replaced_on = m.valid_to.strftime("%d %B %Y").lstrip("0") if m.valid_to else None
    return {"id": m.id, "fact": m.normalized_fact, "told_on": _told_on(m),
            "replaced_on": replaced_on if m.status == MemoryStatus.HISTORICAL else None,
            "unsure": m.confidence < 0.7}


def _same(a: str | None, b: str | None) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def _same_value(a: str | None, b: str | None) -> bool:
    """'123 456 789' equals '123456789'; otherwise compare words, ignoring case and punctuation."""
    da, db_ = re.sub(r"\D", "", a or ""), re.sub(r"\D", "", b or "")
    if len(da) >= 6 and len(db_) >= 6:
        return da[-10:] == db_[-10:]  # "+91 90000 00001" equals "9000000001"
    words = lambda t: re.sub(r"[^\w\s]", "", (t or "").lower()).split()
    return words(a) == words(b)


def _already_known(active: list[Memory], c, person_id: int | None) -> Memory | None:
    """The approved memory that already says this, if any (same fact text, or same person + kind + value)."""
    for m in active:
        if _same(m.normalized_fact, c.normalized_fact):
            return m
        if m.person_id is not None and m.person_id == person_id:
            same_person = True
        elif m.person_id is None and person_id is None and not c.person_name:
            same_person = True  # both are about the user themself
        elif m.person_id is None or person_id is None:
            # One copy isn't linked to a saved person yet: only the same if it names the same person
            # ("Ravi lives in Hyderabad" is not the same as "Rahul lives in Hyderabad").
            name = (c.person_name or "").strip().lower()
            same_person = bool(name) and name in m.normalized_fact.lower()
        else:
            same_person = False
        if same_person and c.attribute and _same(m.attribute, c.attribute) and _same_value(m.value, c.value):
            return m
    return None


BUSY = {
    "hinglish": "Abhi AI service thodi busy hai, isliye mujhe jawab dene mein dikkat ho rahi hai. "
                "Ek minute baad phir se try kijiye.",
    "en": "I'm having a little trouble thinking right now because the AI service is busy. "
          "Please try again in a minute.",
    "hi": "अभी AI सेवा व्यस्त है, इसलिए मुझे थोड़ी परेशानी हो रही है। कृपया एक मिनट बाद फिर से कोशिश करें।",
}
TROUBLE = {
    "hinglish": "Maaf kijiye, meri taraf se kuch gadbad ho gayi. Phir se try kijiye.",
    "en": "Sorry, something went wrong on my side. Please try again, and if it keeps happening, "
          "ask someone to check the server window.",
    "hi": "माफ़ कीजिए, मेरी तरफ़ से कुछ गड़बड़ हो गई। कृपया फिर से कोशिश करें।",
}

# "Tell me about everyone / everything": search alone returns only the closest few memories.
BROAD = re.compile(r"\b(every\s?(one|body|thing|person|people)|all (the )?(people|my|of|memories|you know)|"
                   r"show (me )?(all|everything)|list (all|everything|my)|whole family|"
                   r"sab(hi|ko|kuch)?|sabke)\b", re.IGNORECASE)


# Words that show the user really meant to share memories (not just "health information").
MEMORY_WORDS = re.compile(r"memor|yaad|यादें|याद|everything|sab kuch|sabkuch|सब कुछ|family news|baatein", re.IGNORECASE)


def _family_access_lines(db: Session, user: User) -> list[str]:
    links = db.scalars(select(FamilyLink).where(FamilyLink.elder_id == user.id,
                                                FamilyLink.status == LinkStatus.ACTIVE)).all()
    lines = []
    for l in links:
        can = [label for flag, label in [(l.can_see_medicines, "medicines"),
                                         (l.can_see_appointments, "appointments"),
                                         (l.can_see_emergency, "emergency contacts"),
                                         (l.can_see_shared_memories, "memories marked as shared")] if flag]
        lines.append(f"- {l.family_user.name} (linked as {l.relation}): can see {', '.join(can) or 'nothing'}"
                     + ("; can suggest reminders" if l.can_suggest_reminders else ""))
    return lines


ALREADY_KNOW = {
    "hinglish": "Yeh mujhe pehle se pata hai. Aapne pehle bataya tha, isliye kuch naya save karne ki zarurat nahi.",
    "en": "I already know that. You've told me before, so there's nothing new to save.",
    "hi": "मुझे यह पहले से पता है। आपने मुझे पहले बताया था, इसलिए कुछ नया सहेजने की ज़रूरत नहीं है।",
}


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


def _clean_name(name: str) -> str:
    return re.sub(r"^(dr|mr|mrs|ms|shri|smt)\.?\s+", "", name.strip().lower())


def _find_person(people: list[Person], name: str | None, relation: str | None) -> Person | None:
    """Match the AI's 'Ananya', 'Dr. Sharma' / 'Sharma', or 'granddaughter' / 'doctor' to one saved person.
    Only returns a match when exactly one person fits, so 'my son' never guesses between two sons."""
    def only(matches: list[Person]) -> Person | None:
        return matches[0] if len(matches) == 1 else None

    if name:
        wanted = _clean_name(name)
        exact = only([p for p in people if _clean_name(p.name) == wanted])
        if exact:
            return exact
        partial = only([p for p in people if wanted and (wanted in _clean_name(p.name).split()
                                                          or _clean_name(p.name) in wanted.split())])
        if partial:
            return partial
    if relation:
        rel = relation.strip().lower()
        exact = only([p for p in people if (p.relation_to_user or "").lower() == rel])
        if exact:
            return exact
        # "doctor" matches "family doctor"; "son" matches "elder son"
        head = rel.split()[-1] if rel else ""
        loose = only([p for p in people if head and head in (p.relation_to_user or "").lower().split()])
        if loose:
            return loose
    return None


@router.post("", response_model=ChatOut)
def chat(data: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 0a. A call for help comes first: alert family at once, without waiting for the AI
    #     (so it still works when the AI service is busy).
    if user.role == UserRole.ELDER and emergency.is_emergency(data.message):
        alert = emergency.raise_alert(db, user, "chat", data.message)
        db.commit()
        db.refresh(alert)
        out = alert_out(db, alert)
        reply = emergency.reply(user.preferred_language, emergency.contacts(db, user.id), bool(out.notified))
        db.add(Message(owner_id=user.id, role="user", text=data.message, language=user.preferred_language))
        db.add(Message(owner_id=user.id, role="assistant", text=reply, language=user.preferred_language))
        db.commit()
        log.warning("EMERGENCY alert %s raised by user %s from chat", alert.id, user.id)
        return ChatOut(reply=reply, intent="EMERGENCY", emergency=out)

    # 0b. A plain "yes" / "no" answers what MemoryMate just asked. No AI call, no ids.
    answer = confirmations.yes_or_no(data.message)
    asked = confirmations.load(db, user.id)
    if answer and confirmations.has_questions(asked):
        db.add(Message(owner_id=user.id, role="user", text=data.message, language=user.preferred_language))
        reply = confirmations.apply(db, user, asked, answer)
        if user.preferred_language != "en":  # our summaries are written in English
            reply = translate(reply, user.preferred_language)
        db.add(Message(owner_id=user.id, role="assistant", text=reply, language=user.preferred_language))
        db.commit()
        return ChatOut(reply=reply, intent="CONFIRMATION")

    started = time.perf_counter()
    people = db.scalars(select(Person).where(Person.owner_id == user.id)).all()
    # Only the memories relevant to this message (people first, then by meaning), including
    # older replaced facts so "Where did Rahul live before?" can be answered.
    relevant = [h.memory for h in search(db, user.id, data.message, people,
                                         statuses=(MemoryStatus.ACTIVE, MemoryStatus.HISTORICAL))]
    if BROAD.search(data.message):  # "tell me about everyone": give the AI all current memories
        seen = {m.id for m in relevant}
        relevant += [m for m in db.scalars(select(Memory).where(Memory.owner_id == user.id,
                                                                Memory.status == MemoryStatus.ACTIVE)
                                           .order_by(Memory.created_at.desc()).limit(60)).all()
                     if m.id not in seen]
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
            reminders=_reminder_lines(db, user, days=60 if BROAD.search(data.message) else 8),
            family_access=_family_access_lines(db, user),
        )
    except AIError as e:
        db.commit()  # keep the user's message even if the AI failed
        log.error("Chat failed: %s", e)  # technical details for the terminal only
        friendly = (BUSY if e.temporary else TROUBLE).get(user.preferred_language, BUSY["en"] if e.temporary else TROUBLE["en"])
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, friendly)

    # 3. Store each fact as a PENDING memory. Nothing is permanent until approved.
    active = [m for m in relevant if m.status == MemoryStatus.ACTIVE]
    pending: list[Memory] = []
    already: list[Memory] = []
    for c in result.memories:
        person = _find_person(people, c.person_name, c.relationship)
        person_id = person.id if person else None
        known = _already_known(active, c, person_id)
        if known is not None:
            if known.person_id is None and person_id is not None:
                known.person_id = person_id  # link the older copy to the person now
                sync_phone(db, known)          # e.g. the doctor's number reaches their contact
            already.append(known)
            continue  # already remembered: don't ask again
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
            visibility=_safe_visibility(c.visibility, result.reply),
            valid_from=local_now().date(),
            replaces_id=_what_it_replaces(c, person_id, relevant_by_id, active),
        )
        db.add(memory)
        pending.append(memory)

    # Memories the user asked to forget. Only offered here; DELETE /memories/{id} confirms.
    forget = [relevant_by_id[i] for i in result.forget_memory_ids
              if i in relevant_by_id and relevant_by_id[i].status == MemoryStatus.ACTIVE]

    # People to add, or changes to people already saved (phone number, emergency contact).
    suggested = []
    for p in result.new_people:
        existing = _find_person(people, p.name, None)
        if existing is None:
            p.id = None  # never trust an id from the AI
            suggested.append(p)
        elif (p.phone and p.phone.strip() != (existing.phone or "")) or \
                (p.is_emergency_contact is not None and p.is_emergency_contact != existing.is_emergency_contact):
            p.id = existing.id
            p.name = existing.name
            suggested.append(p)

    # Everything they said is already remembered: say so instead of asking "Should I save it?".
    reply = result.reply
    if already and not pending and not forget and not suggested and not result.reminders and not result.access_changes \
            and not result.visibility_changes and not result.cancel_reminder_ids \
            and "?" in reply:
        # The AI still asked to save something we already have: answer naturally instead.
        reply = ALREADY_KNOW.get(user.preferred_language, ALREADY_KNOW["en"])

    # Reminders the user asked to remove (confirmed with "yes").
    cancel_list = []
    for rid in dict.fromkeys(result.cancel_reminder_ids):
        r = db.get(Reminder, rid)
        if r is not None and r.owner_id == user.id and r.status == ReminderStatus.ACTIVE:
            cancel_list.append({"id": r.id, "title": r.title})

    # Sharing changes for existing memories (confirmed with "yes").
    visibility_changes = [{"memory_id": v.memory_id, "visibility": v.visibility} for v in result.visibility_changes
                          if v.memory_id in relevant_by_id
                          and relevant_by_id[v.memory_id].status == MemoryStatus.ACTIVE]

    # Family access changes (only what the user asked for; confirmed with "yes").
    access_changes = []
    for a in result.access_changes:
        link = family_access.find_link(db, user.id, a.name)
        if a.action in ("UPDATE", "REVOKE") and link is None:
            continue  # nobody by that name has access; the reply already said what it could
        change = a.model_dump()
        change["memories_asked"] = bool(MEMORY_WORDS.search(data.message))
        access_changes.append(change)

    # 4. Remember what this reply asks about, so a plain "yes" / "no" can answer it next.
    db.flush()  # gives the new memories their ids
    confirmations.save(db, user.id, {
        "memory_ids": [m.id for m in pending],
        "forget_ids": [m.id for m in forget],
        "reminders": [r.model_dump() for r in result.reminders],
        "people": [p.model_dump() for p in suggested],
        "access": access_changes,
        "visibility": visibility_changes,
        "cancel_reminders": cancel_list,
    })
    waiting = bool(pending or forget or result.reminders or suggested or access_changes or visibility_changes
                   or cancel_list)

    # 5. Save the reply.
    db.add(Message(owner_id=user.id, role="assistant", text=reply, language=user.preferred_language))
    db.commit()
    log.info("Chat answered in %.1fs total", time.perf_counter() - started)
    for m in pending:
        db.refresh(m)

    return ChatOut(
        reply=reply,
        intent=result.intent,
        pending_memories=pending,
        forget_candidates=forget,
        suggested_people=suggested,
        reminder_suggestions=result.reminders,
        reminder_suggestion=result.reminders[0] if result.reminders else None,
        access_changes=access_changes,
        visibility_changes=visibility_changes,
        reminders_to_cancel=cancel_list,
        waiting_for_yes_or_no=waiting,
        # The AI thinks they sound unwell: show the Help button, but only they decide to alert family.
        suggest_help=result.intent == "EMERGENCY",
    )
