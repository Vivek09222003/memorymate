"""Answering MemoryMate's questions with a plain "yes" or "no".

After each reply we store what MemoryMate asked about (memories to keep, a reminder to set,
people to add, memories to forget). If the next message is just "yes" / "no" (also haan/nahi,
avunu/vaddu), we do it, with no AI call and no ids needed.
"""
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import family_access
from app.models import (ChatState, Memory, MemoryStatus, Person, PersonType, Reminder, ReminderStatus, User,
                        Visibility)
from app.reminders import cancel as cancel_reminder
from app.reminders import first_due, plan_alerts
from app.schemas import ReminderCreate
from app.timeutil import local_now, show

_END = r"(?=$|[\s.,!?।])"  # the word must end here ("no" but not "now")
_YES = re.compile(
    r"^\W*(yes|yeah|yep|yup|ok|okay|okk?|sure|correct|right|please do|do it|go ahead|save it|remember it|"
    r"haan ji|haanji|haan|haa|ha|han|hn|ji haan|ji ha|ji|"
    r"theek hai|thik hai|thik h|theek h|theek|thik|sahi hai|sahi|"
    r"sab (theek|thik|acha|accha|achha|sahi)( hai| h)?|"
    r"acha|accha|achha|achchha|bilkul|zaroor|jarur|chalega|kar do|kardo|save karo|yaad rakho|"
    r"हाँ जी|हाँ|हां|हा|जी हाँ|जी|ठीक है|ठीक|सही है|अच्छा|बिल्कुल|ज़रूर|जरूर|चलेगा)" + _END,
    re.IGNORECASE)
_NO = re.compile(
    r"^\W*(no|nope|nah|don't|do not|not now|cancel|leave it|"
    r"ji nahi|ji nahin|nahi chahiye|nahi|nahin|nhi|nai|na|mat karo|mat|rehne do|rehnedo|chhodo|chodo|"
    r"जी नहीं|नहीं चाहिए|नहीं|नही|ना|मत करो|रहने दो|छोड़ो)" + _END,
    re.IGNORECASE)


def answer_language(message: str, fallback: str) -> str:
    """The language of a short answer like "haan", "हाँ" or "yes", so the reply can match it."""
    if re.search(r"[\u0900-\u097F]", message):
        return "hi"
    low = message.lower()
    if re.search(r"\b(haan|haanji|haa|ha|han|hn|na|ji|theek|thik|sahi|sab|acha|accha|achha|bilkul|zaroor|jarur|"
                 r"chalega|kar|karo|nahi|nahin|nhi|nai|mat|rehne|chhodo|chodo)\b", low):
        return "hinglish"
    if re.search(r"\b(yes|yeah|yep|ok|okay|sure|no|nope|correct|right)\b", low):
        return "en"
    return fallback


# Words that may follow a yes/no without making it a new message ("haan ji please", "ok thank you").
_FILLER = {"ji", "please", "pls", "plz", "thanks", "thank", "you", "thankyou", "dhanyavaad", "shukriya", "hai", "h",
           "haan", "ha", "ok", "okay", "yes", "sure", "no", "na", "nahi", "nhi", "karo", "kar", "do", "de", "dijiye",
           "kijiye", "it", "that", "go", "ahead", "save", "bhai", "beta", "beti", "bas", "abhi", "sab", "theek",
           "thik", "acha", "accha", "achha", "sahi", "toh", "to", "chahiye", "mat", "rehne", "jee"}


def yes_or_no(message: str) -> str | None:
    """'yes', 'no', or None if the message says more than a short answer."""
    if "?" in message or len(message.split()) > 6:
        return None  # a question or a new message, not just an answer
    match = _NO.match(message) or _YES.match(message)
    if not match:
        return None
    rest = re.findall(r"[^\W\d_]+", message[match.end():].lower())
    if any(w not in _FILLER and not re.search(r"[\u0900-\u097F]", w) for w in rest):
        return None  # "acha, aur Rajesh kahan rehta hai" is a new message
    return "no" if _NO.match(message) else "yes"


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
    return any(pending.get(k) for k in ("memory_ids", "forget_ids", "reminders", "reminder", "people", "access", "visibility",
                                        "cancel_reminders"))


def _person_type(p: dict) -> PersonType:
    """The AI's category if valid, otherwise worked out from the relationship."""
    try:
        return PersonType(p.get("person_type") or "")
    except ValueError:
        rel = (p.get("relationship") or "").lower()
        if "doctor" in rel or "nurse" in rel or p["name"].lower().startswith("dr"):
            return PersonType.DOCTOR
        if "friend" in rel or "neighbo" in rel:
            return PersonType.FRIEND
        return PersonType.FAMILY if rel else PersonType.OTHER


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

    # People first, so memories about a newly added person can be linked to them.
    added: list[Person] = []
    for p in pending.get("people", []):
        phone = (p.get("phone") or "").strip()[:30] or None
        emergency = p.get("is_emergency_contact")
        person = db.get(Person, p["id"]) if p.get("id") else None
        if person is not None and person.owner_id == user.id:
            changes = []
            if phone:
                person.phone = phone
                changes.append(f"phone {phone}")
            if emergency is not None:
                person.is_emergency_contact = bool(emergency)
                changes.append("emergency contact" if emergency else "no longer an emergency contact")
            done.append(f"I've updated {person.name}: {', '.join(changes)}." if changes else "")
        else:
            relation = p.get("relationship") or None
            person = Person(owner_id=user.id, name=p["name"][:100], relation_to_user=relation, phone=phone,
                            is_emergency_contact=bool(emergency), person_type=_person_type(p))
            db.add(person)
            added.append(person)
            as_what = f" as your {relation}" if relation else ""
            extra = (f" with the number {phone}" if phone else "") + (", as an emergency contact" if emergency else "")
            done.append(f"I've saved {person.name}{as_what} ({person.person_type.value.lower()}){extra}.")
    db.flush()

    for m in memories:
        if m.person_id is None:
            for person in added:
                first = person.name.lower().replace("dr.", "").replace("dr ", "").split()
                if first and first[0] in m.normalized_fact.lower():
                    m.person_id = person.id
                    break
        activate(db, m)
        done.append(f"I'll remember: {m.normalized_fact}")

    for i in pending.get("forget_ids", []):
        m = db.get(Memory, i)
        if m is not None and m.owner_id == user.id and m.status == MemoryStatus.ACTIVE:
            m.status = MemoryStatus.DELETED
            m.embedding = None
            done.append(f"I've forgotten: {m.normalized_fact}")


    suggestions = list(pending.get("reminders") or [])
    if pending.get("reminder"):  # saved by an older version
        suggestions.append(pending["reminder"])
    for r in suggestions:
        try:
            reminder = new_reminder(ReminderCreate(
                title=r["title"], kind=r["kind"],
                date=r.get("date") or local_now().date(),  # daily medicines may come without a date
                time=r.get("time") or "09:00",
                repeat=r.get("repeat") or "NONE",
                notes=r.get("notes")), user.id)
            db.add(reminder)
            db.flush()
            due = first_due(reminder)
            plan_alerts(db, reminder, due)
            how_often = {"DAILY": " (every day)", "WEEKLY": " (every week)", "YEARLY": " (every year)"}
            done.append(f"Reminder set: {reminder.title}, {show(due)}{how_often.get(reminder.repeat.value, '')}.")
        except (HTTPException, ValueError, KeyError, TypeError):
            done.append(f"I couldn't set the reminder \"{r.get('title', '')}\" because the date or time wasn't "
                        "clear (or has passed). Please tell me again with the day and time.")

    # Reminders to remove.
    removed = []
    for c in pending.get("cancel_reminders", []):
        r = db.get(Reminder, c["id"])
        if r is not None and r.owner_id == user.id and r.status == ReminderStatus.ACTIVE:
            cancel_reminder(r)
            removed.append(r.title)
    if removed:
        done.append("Removed: " + ", ".join(removed) + ".")

    # Who may see existing memories.
    WHO = {"PRIVATE": "kept private", "SHARED_FAMILY": "shared with your family",
           "CARE": "visible to family who help with your health", "EMERGENCY": "shown in emergencies"}
    for v in pending.get("visibility", []):
        m = db.get(Memory, v["memory_id"])
        if m is not None and m.owner_id == user.id and m.status == MemoryStatus.ACTIVE:
            m.visibility = Visibility(v["visibility"])
            done.append(f"\"{m.normalized_fact}\" is now {WHO.get(v['visibility'], v['visibility'])}.")

    # Family access the user asked to give, change or remove.
    for a in pending.get("access", []):
        flags = {"can_see_medicines": a.get("medicines"), "can_see_appointments": a.get("appointments"),
                 "can_see_emergency": a.get("emergency"), "can_see_shared_memories": a.get("shared_memories"),
                 "can_suggest_reminders": a.get("suggest_reminders")}
        link = family_access.find_link(db, user.id, a["name"])
        if a.get("action") == "REVOKE":
            done.append(family_access.revoke(link) if link else f"{a['name']} didn't have access anyway.")
        elif link is not None:
            done.append(family_access.update(link, flags))
        else:
            done.append(family_access.grant(db, user, a["name"], flags, a.get("email"),
                                            memories_asked=bool(a.get("memories_asked"))))
        db.flush()

    save(db, user.id, {})
    done = [d for d in done if d]
    return "Done. " + " ".join(done) if done else "There was nothing left to do."
