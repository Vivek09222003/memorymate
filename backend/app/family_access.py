"""Giving, changing and removing family access: shared by the chat ("let Rajesh see my medicines")
and the /family endpoints.

A family member doesn't need an account first: giving access creates an INVITED link with a code.
When they sign up (or log in) as family and enter the code, the link becomes ACTIVE.
"""
import secrets

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HELPER_ROLES, FamilyLink, LinkStatus, Person, PersonType, User, UserRole

SCOPES = {  # field on FamilyLink → words for people
    "can_see_medicines": "medicines",
    "can_see_appointments": "appointments",
    "can_see_emergency": "emergency contacts",
    "can_see_shared_memories": "memories you've marked as shared",
    "can_suggest_reminders": "suggest reminders",
}
DEFAULTS = {"can_see_medicines": True, "can_see_appointments": True, "can_see_emergency": True,
            "can_see_shared_memories": False, "can_suggest_reminders": True}
# A doctor sees what's needed for care: medicines, appointments and tasks, health notes and emergency info.
# Never family memories (those stay private or shared with family only).
DOCTOR_DEFAULTS = {"can_see_medicines": True, "can_see_appointments": True, "can_see_emergency": True,
                   "can_see_shared_memories": False, "can_suggest_reminders": True}


def is_doctor(name: str, relation: str | None, person: Person | None) -> bool:
    if person is not None and person.person_type == PersonType.DOCTOR:
        return True
    rel = (relation or "").lower()
    return any(w in rel for w in ("doctor", "nurse", "physician")) or name.strip().lower().startswith("dr")


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, easy to read out over the phone


def new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        if db.scalar(select(FamilyLink).where(FamilyLink.invite_code == code)) is None:
            return code


def can_see_words(link: FamilyLink) -> str:
    words_for = dict(SCOPES)
    if link.can_see_medicines or link.can_see_appointments:
        words_for["can_see_appointments"] = "appointments, tasks and health notes"
    see = [words for field, words in words_for.items() if field != "can_suggest_reminders" and getattr(link, field)]
    return ", ".join(see) if see else "nothing yet"


def find_link(db: Session, elder_id: int, name: str) -> FamilyLink | None:
    """The live or invited link for 'Priya' / 'Dr. Sharma' (first names and titles are fine)."""
    want = name.strip().lower().replace("dr.", "").replace("dr ", "").strip()
    links = db.scalars(select(FamilyLink).where(FamilyLink.elder_id == elder_id,
                                                FamilyLink.status.in_([LinkStatus.ACTIVE, LinkStatus.INVITED]))).all()
    exact = [l for l in links if l.display_name.lower() == name.strip().lower()]
    if len(exact) == 1:
        return exact[0]
    loose = [l for l in links if want and want.split()[0] in l.display_name.lower().split()]
    return loose[0] if len(loose) == 1 else None


def grant(db: Session, elder: User, name: str, flags: dict, email: str | None = None,
          memories_asked: bool = False) -> str:
    """Give someone access. Links an existing family account by email, otherwise creates an invite code."""
    existing = find_link(db, elder.id, name)
    if existing is not None:
        return update(existing, flags)

    people = db.scalars(select(Person).where(Person.owner_id == elder.id)).all()
    person = next((p for p in people if p.name.lower() == name.strip().lower()), None)
    relation = (person.relation_to_user if person and person.relation_to_user else None) or "family"
    doctor = is_doctor(name, relation, person)
    if doctor and relation == "family":
        relation = "doctor"
    link = FamilyLink(elder_id=elder.id, relation=relation[:50], invite_name=name.strip()[:100],
                      **(DOCTOR_DEFAULTS if doctor else DEFAULTS))
    for field, value in flags.items():
        if field in SCOPES and value is not None:
            setattr(link, field, bool(value))
    if doctor and not memories_asked:
        link.can_see_shared_memories = False  # doctors get care information only, unless memories were asked for

    account = None
    if email:
        account = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if account is not None and account.role in HELPER_ROLES and account.id != elder.id:
        link.family_user_id = account.id
        link.status = LinkStatus.ACTIVE
        db.add(link)
        return f"{name} can now see your {can_see_words(link)}."
    link.status = LinkStatus.INVITED
    link.invite_code = new_code(db)
    db.add(link)
    return (f"{name} will be able to see your {can_see_words(link)}. Ask them to sign up in MemoryMate "
            f"and enter this code: {link.invite_code}")


def update(link: FamilyLink, flags: dict) -> str:
    changed = False
    for field, value in flags.items():
        if field in SCOPES and value is not None and getattr(link, field) != bool(value):
            setattr(link, field, bool(value))
            changed = True
    who = link.display_name
    if not changed:
        return f"{who} can already see your {can_see_words(link)}."
    return f"Updated. {who} can now see your {can_see_words(link)}."


def revoke(link: FamilyLink) -> str:
    link.status = LinkStatus.REVOKED
    link.invite_code = None
    return f"{link.display_name} can no longer see any of your information."


def join(db: Session, member: User, code: str) -> FamilyLink:
    """A family member enters the code they were given."""
    if member.role not in HELPER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only family or doctor accounts can join with a code.")
    link = db.scalar(select(FamilyLink).where(FamilyLink.invite_code == code.strip().upper(),
                                              FamilyLink.status == LinkStatus.INVITED))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That code isn't valid (or was already used).")
    if link.elder_id == member.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't join your own account.")
    already = db.scalar(select(FamilyLink).where(FamilyLink.elder_id == link.elder_id,
                                                 FamilyLink.family_user_id == member.id,
                                                 FamilyLink.status == LinkStatus.ACTIVE))
    if already is not None:  # keep one link per person: move the new permissions onto it
        for field in SCOPES:
            setattr(already, field, getattr(link, field))
        link.status = LinkStatus.REVOKED
        link.invite_code = None
        return already
    link.family_user_id = member.id
    link.status = LinkStatus.ACTIVE
    link.invite_code = None
    return link
