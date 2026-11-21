"""Family connection: the elder decides who may see what; family see only that.

Elder side   — link a family account, change its permissions, revoke it, see the access log.
Family side  — see the elders who linked them, open a dashboard of what's allowed,
               suggest a reminder (it only rings if the elder accepts it).

Conversations and PRIVATE memories are never included, whatever the permissions.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (AccessLog, FamilyLink, LinkStatus, Memory, MemoryStatus, OccurrenceStatus, Person,
                        Reminder, ReminderKind, ReminderOccurrence, ReminderStatus, User, UserRole, Visibility)
from app.routers.reminders import alert_out, new_reminder
from app.schemas import (AccessLogOut, EmergencyOut, FamilyDashboard, FamilyLinkCreate, FamilyLinkOut,
                         FamilyLinkUpdate, PersonOut, ReminderCreate, ReminderOut, ReminderSuggestionIn,
                         SharedMemoryOut)
from app.security import get_current_user
from app.timeutil import local_now, local_tz, show

router = APIRouter(prefix="/family", tags=["Family"])

SHAREABLE = [Visibility.CARE, Visibility.SHARED_FAMILY, Visibility.EMERGENCY]  # never PRIVATE


# ---------- helpers ----------
def _require(user: User, role: UserRole) -> None:
    if user.role != role:
        who = "the elderly user's" if role == UserRole.ELDER else "a family"
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"This needs {who} account.")


def _link_out(link: FamilyLink) -> FamilyLinkOut:
    return FamilyLinkOut(
        id=link.id, relation=link.relation, status=link.status, created_at=link.created_at,
        family_user_id=link.family_user_id, family_name=link.family_user.name, family_email=link.family_user.email,
        elder_id=link.elder_id, elder_name=link.elder.name,
        can_see_medicines=link.can_see_medicines, can_see_appointments=link.can_see_appointments,
        can_see_shared_memories=link.can_see_shared_memories, can_see_emergency=link.can_see_emergency,
        can_suggest_reminders=link.can_suggest_reminders,
    )


def _active_link(db: Session, elder_id: int, family_user: User) -> FamilyLink:
    """The family member's live link to this elder, or 404 (we don't reveal whether the elder exists)."""
    link = db.scalar(select(FamilyLink).where(FamilyLink.elder_id == elder_id,
                                              FamilyLink.family_user_id == family_user.id,
                                              FamilyLink.status == LinkStatus.ACTIVE))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not linked to this person.")
    return link


def _today_start() -> datetime:
    return datetime.combine(local_now().date(), datetime.min.time(), tzinfo=local_tz())


# ---------- elder side ----------
@router.post("/links", response_model=FamilyLinkOut, status_code=status.HTTP_201_CREATED)
def link_family(data: FamilyLinkCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Elder: give a family member access. They must already have a FAMILY account."""
    _require(user, UserRole.ELDER)
    member = db.scalar(select(User).where(func.lower(User.email) == data.family_email.strip().lower()))
    if member is None or member.role != UserRole.FAMILY:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No family account with that email. Ask them to register with role FAMILY first.")
    link = db.scalar(select(FamilyLink).where(FamilyLink.elder_id == user.id,
                                              FamilyLink.family_user_id == member.id))
    if link is None:
        link = FamilyLink(elder_id=user.id, family_user_id=member.id, relation=data.relation)
        db.add(link)
    elif link.status == LinkStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already linked. Change permissions with PATCH instead.")
    link.status = LinkStatus.ACTIVE
    link.relation = data.relation
    for scope, value in data.model_dump(exclude={"family_email", "relation"}).items():
        setattr(link, scope, value)
    db.commit()
    db.refresh(link)
    return _link_out(link)


@router.get("/links", response_model=list[FamilyLinkOut])
def my_family(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Elder: everyone you've given access to, and exactly what they can see."""
    _require(user, UserRole.ELDER)
    return [_link_out(l) for l in db.scalars(
        select(FamilyLink).where(FamilyLink.elder_id == user.id, FamilyLink.status == LinkStatus.ACTIVE)).all()]


@router.patch("/links/{link_id}", response_model=FamilyLinkOut)
def change_permissions(link_id: int, data: FamilyLinkUpdate,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Elder: switch individual permissions on or off. Send only what changes."""
    _require(user, UserRole.ELDER)
    link = db.get(FamilyLink, link_id)
    if link is None or link.elder_id != user.id or link.status != LinkStatus.ACTIVE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(link, field, value)
    db.commit()
    db.refresh(link)
    return _link_out(link)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(link_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Elder: remove a family member's access completely, effective immediately."""
    _require(user, UserRole.ELDER)
    link = db.get(FamilyLink, link_id)
    if link is None or link.elder_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found.")
    link.status = LinkStatus.REVOKED
    db.commit()


@router.get("/access-log", response_model=list[AccessLogOut])
def access_log(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Elder: who looked at what, newest first (last 100)."""
    _require(user, UserRole.ELDER)
    rows = db.scalars(select(AccessLog).where(AccessLog.elder_id == user.id)
                      .order_by(AccessLog.id.desc()).limit(100)).all()
    return [AccessLogOut(viewer_name=r.viewer.name, section=r.section, viewed_at=show(r.created_at)) for r in rows]


# ---------- family side ----------
@router.get("/my-elders", response_model=list[FamilyLinkOut])
def my_elders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Family: the people who have linked you, and what each lets you see."""
    _require(user, UserRole.FAMILY)
    return [_link_out(l) for l in db.scalars(
        select(FamilyLink).where(FamilyLink.family_user_id == user.id, FamilyLink.status == LinkStatus.ACTIVE)).all()]


@router.get("/elders/{elder_id}/dashboard", response_model=FamilyDashboard)
def dashboard(elder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Family: today's picture of your relative, limited to what they allow. Each section you open is logged."""
    _require(user, UserRole.FAMILY)
    link = _active_link(db, elder_id, user)
    start = _today_start()
    out = FamilyDashboard(elder_name=link.elder.name, relation=link.relation, as_of=show(local_now()))
    seen: list[str] = []

    def main_alerts(kind: ReminderKind, frm: datetime, to: datetime):
        return db.scalars(
            select(ReminderOccurrence).join(Reminder)
            .where(ReminderOccurrence.owner_id == elder_id, ReminderOccurrence.is_main.is_(True),
                   ReminderOccurrence.for_due_at >= frm, ReminderOccurrence.for_due_at < to,
                   Reminder.kind == kind, Reminder.visibility.in_(SHAREABLE),
                   Reminder.status.not_in([ReminderStatus.SUGGESTED, ReminderStatus.CANCELLED]))
            .order_by(ReminderOccurrence.for_due_at)).all()

    if link.can_see_medicines:
        meds = main_alerts(ReminderKind.MEDICINE, start, start + timedelta(days=1))
        out.medicines_today = [alert_out(o) for o in meds]
        out.missed_medicines_today = sum(1 for o in meds if o.status == OccurrenceStatus.MISSED)
        seen.append("medicines")
    else:
        out.hidden_sections.append("medicines")

    if link.can_see_appointments:
        appts = main_alerts(ReminderKind.APPOINTMENT, start, start + timedelta(days=30))
        # Only what is still to come: not already done, missed or cancelled.
        out.upcoming_appointments = [alert_out(o) for o in appts
                                     if o.status in (OccurrenceStatus.SCHEDULED, OccurrenceStatus.DUE)]
        seen.append("appointments")
    else:
        out.hidden_sections.append("appointments")

    if link.can_see_shared_memories:
        mems = db.scalars(select(Memory).where(Memory.owner_id == elder_id, Memory.status == MemoryStatus.ACTIVE,
                                               Memory.visibility == Visibility.SHARED_FAMILY)
                          .order_by(Memory.created_at.desc()).limit(20)).all()
        out.shared_memories = [SharedMemoryOut(fact=m.normalized_fact, event_date=m.event_date,
                                               told_on=show(m.created_at)) for m in mems]
        seen.append("shared memories")
    else:
        out.hidden_sections.append("shared memories")

    if link.can_see_emergency:
        contacts = db.scalars(select(Person).where(Person.owner_id == elder_id,
                                                   Person.is_emergency_contact.is_(True))).all()
        info = db.scalars(select(Memory.normalized_fact).where(
            Memory.owner_id == elder_id, Memory.status == MemoryStatus.ACTIVE,
            Memory.visibility == Visibility.EMERGENCY)).all()
        out.emergency = EmergencyOut(contacts=[PersonOut.model_validate(p) for p in contacts], information=list(info))
        seen.append("emergency")
    else:
        out.hidden_sections.append("emergency")

    for section in seen:
        db.add(AccessLog(elder_id=elder_id, viewer_id=user.id, section=section))
    db.commit()
    return out


@router.post("/elders/{elder_id}/reminders", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def suggest_reminder(elder_id: int, data: ReminderSuggestionIn,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Family: suggest a reminder. It stays SUGGESTED, and only rings once the elder accepts it."""
    _require(user, UserRole.FAMILY)
    link = _active_link(db, elder_id, user)
    if not link.can_suggest_reminders:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You're not allowed to suggest reminders.")
    reminder = new_reminder(ReminderCreate(**data.model_dump()), elder_id, suggested_by_id=user.id)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return ReminderOut.model_validate(reminder)
