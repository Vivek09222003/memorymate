"""Answering MemoryMate's questions with a plain "yes" or "no".

After each reply we store what MemoryMate asked about (memories to keep, a reminder to set,
people to add, memories to forget). If the next message is just "yes" / "no" (also haan/nahi,
avunu/vaddu), we do it, with no AI call and no ids needed.
"""
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import ChatState, Memory, MemoryStatus, Person, PersonType, User
from app.reminders import first_due, plan_alerts
from app.schemas import ReminderCreate
from app.timeutil import show

_END = r"(?=$|[\s.,!?।])"  # the word must end here ("no" but not "now")
_YES = re.compile(
    r"^\W*(yes|yeah|yep|yup|ok|okay|sure|correct|right|please do|do it|go ahead|save it|remember it|"
    r"haan|haa|ha|han|ji haan|ji|theek hai|thik hai|avunu|sare|"
    r"हाँ|हां|हा|जी हाँ|जी|ठीक है|అవును|సరే)" + _END,
    re.IGNORECASE)
_NO = re.compile(
    r"^\W*(no|nope|nah|don't|do not|not now|cancel|leave it|"
    r"ji nahi|ji nahin|nahi|nahin|na|mat karo|vaddu|ledu|"
    r"जी नहीं|नहीं|नही|ना|వద్దు|లేదు)" + _END,
    re.IGNORECASE)


def yes_or_no(message: str) -> str | None:
    """'yes', 'no', or None if the message is more than a short answer."""
    if len(message.split()) > 6:  # "Yes, and also my son Ravi..." is a new message, not just an answer
        return None
    if _NO.match(message):
        return "no"
    if _YES.match(message):
        return "yes"
    return None


# ---------- remembering what was asked ----------
def load(db: Session, user_id: int) -> dict:
    state = db.get(ChatState, user_id)
    return dict(state.pending) if state and state.pending else {}


def save(db: Session, user_id: int, pending: dict) -> None:
    pending = {k: v for k, v in pending.items() if v}  # drop empty parts
    state = db.get(ChatState, user_id)
    if state is None:
        db.add(ChatState(owner_id=user_id, pending=pending))
    else:
        state.pending = pending


def has_questions(pending: dict) -> bool:
    return any(pending.get(k) for k in ("memory_ids", "forget_ids", "reminder", "people"))


# ---------- acting on the answer ----------
def apply(db: Session, user: User, pending: dict, answer: str) -> str:
    """Do (or drop) everything that was asked, and return a plain-English summary."""
    from app.routers.memories import activate  # here to avoid a circular import
    from app.routers.reminders import new_reminder

    done: list[str] = []
    memories = [m for m in (db.get(Memory, i) for i in pending.get("memory_ids", []))
                if m is not None and m.owner_id == user.id and m.status == MemoryStatus.PENDING]

    if answer == "no":
        for m in memories:
            m.status = MemoryStatus.DELETED
        save(db, user.id, {})
        return "All right, I won't do that."

    for m in memories:
        activate(db, m)
        done.append(f"I'll remember: {m.normalized_fact}")

    for i in pending.get("forget_ids", []):
        m = db.get(Memory, i)
        if m is not None and m.owner_id == user.id and m.status == MemoryStatus.ACTIVE:
            m.status = MemoryStatus.DELETED
            m.embedding = None
            done.append(f"I've forgotten: {m.normalized_fact}")

    for p in pending.get("people", []):
        db.add(Person(owner_id=user.id, name=p["name"][:100], relation_to_user=(p.get("relationship") or None),
                      person_type=PersonType.DOCTOR if "doctor" in (p.get("relationship") or "").lower()
                      else PersonType.FAMILY))
        done.append(f"I've added {p['name']} to your people.")

    r = pending.get("reminder")
    if r:
        try:
            reminder = new_reminder(ReminderCreate(title=r["title"], kind=r["kind"], date=r["date"],
                                                   time=r.get("time") or "09:00"), user.id)
            db.add(reminder)
            db.flush()
            due = first_due(reminder)
            plan_alerts(db, reminder, due)
            done.append(f"Reminder set: {reminder.title}, {show(due)}.")
        except (HTTPException, ValueError, KeyError, TypeError):
            done.append("I couldn't set that reminder because the date or time wasn't clear (or has passed). "
                        "Please tell me again with the day and time.")

    save(db, user.id, {})
    return "Done. " + " ".join(done) if done else "There was nothing left to do."
