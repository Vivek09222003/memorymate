"""Emergency mode.

Elder         — POST /emergency/sos (the red Help button), GET /emergency/active, resolve it ("I'm safe").
Family/doctor — GET /emergency/alerts: open alerts of every elder who lets them see emergency information.
                They can resolve an alert once they've handled it.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import emergency
from app.database import get_db
from app.models import (HELPER_ROLES, AlertStatus, EmergencyAlert, FamilyLink, LinkStatus, User, UserRole)
from app.schemas import EmergencyAlertOut, PersonOut, SosIn
from app.security import get_current_user
from app.timeutil import show

router = APIRouter(prefix="/emergency", tags=["Emergency"])


def _name_key(name: str | None) -> str:
    """'Dr. Satish Kumar' and 'satish' both become 'satish', so we can tell a contact is the viewer."""
    words = re.sub(r"^\s*(dr|doctor)\.?\s+", "", (name or "").lower()).split()
    return words[0] if words else ""


def alert_out(db: Session, alert: EmergencyAlert, viewer: User | None = None) -> EmergencyAlertOut:
    """viewer: the family member or doctor looking at it. Their own entry is left out of the contacts,
    so Priya isn't offered "Call Priya"."""
    people = emergency.contacts(db, alert.elder_id)
    if viewer is not None and viewer.id != alert.elder_id:
        me = _name_key(viewer.name)
        people = [p for p in people if _name_key(p.name) != me]
    return EmergencyAlertOut(
        id=alert.id, elder_id=alert.elder_id, elder_name=alert.elder.name, status=alert.status.value,
        source=alert.source, message=alert.message, raised_at=show(alert.created_at),
        contacts=[PersonOut.model_validate(p) for p in people],
        information=emergency.information(db, alert.elder_id),
        resolved_by=alert.resolved_by.name if alert.resolved_by else None,
        notified=[l.display_name for l in db.scalars(select(FamilyLink).where(
            FamilyLink.elder_id == alert.elder_id, FamilyLink.status == LinkStatus.ACTIVE,
            FamilyLink.family_user_id.is_not(None), FamilyLink.can_see_emergency.is_(True))).all()],
    )


def _elder_only(user: User) -> None:
    if user.role != UserRole.ELDER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the elderly user can ask for help here.")


def _helper_link(db: Session, elder_id: int, user: User) -> FamilyLink | None:
    """The helper's live link to this elder, if it allows emergency information."""
    return db.scalar(select(FamilyLink).where(FamilyLink.elder_id == elder_id,
                                              FamilyLink.family_user_id == user.id,
                                              FamilyLink.status == LinkStatus.ACTIVE,
                                              FamilyLink.can_see_emergency.is_(True)))


@router.post("/sos", response_model=EmergencyAlertOut, status_code=status.HTTP_201_CREATED)
def sos(data: SosIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The red Help button. Alerts family and doctors at once and returns who to call."""
    _elder_only(user)
    alert = emergency.raise_alert(db, user, "button", data.message if data else None)
    db.commit()
    db.refresh(alert)
    return alert_out(db, alert)


@router.get("/active", response_model=EmergencyAlertOut | None)
def my_active_alert(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The elder's open alert, if there is one (so the page can keep showing it after a refresh)."""
    _elder_only(user)
    alert = emergency.active_alert(db, user.id)
    return alert_out(db, alert) if alert else None


@router.get("/alerts", response_model=list[EmergencyAlertOut])
def alerts_for_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Family/doctor: open alerts from every elder who lets you see emergency information."""
    if user.role not in HELPER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This needs a family or doctor account.")
    elder_ids = db.scalars(select(FamilyLink.elder_id).where(FamilyLink.family_user_id == user.id,
                                                             FamilyLink.status == LinkStatus.ACTIVE,
                                                             FamilyLink.can_see_emergency.is_(True))).all()
    if not elder_ids:
        return []
    rows = db.scalars(select(EmergencyAlert).where(EmergencyAlert.elder_id.in_(elder_ids),
                                                   EmergencyAlert.status == AlertStatus.ACTIVE)
                      .order_by(EmergencyAlert.id.desc())).all()
    return [alert_out(db, a, viewer=user) for a in rows]


@router.post("/{alert_id}/resolve", response_model=EmergencyAlertOut)
def resolve(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """'I'm safe now' (elder) or 'Handled' (family/doctor who can see emergencies)."""
    alert = db.get(EmergencyAlert, alert_id)
    allowed = alert is not None and (alert.elder_id == user.id or _helper_link(db, alert.elder_id, user))
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    if alert.status == AlertStatus.ACTIVE:
        emergency.resolve(alert, user)
        db.commit()
        db.refresh(alert)
    return alert_out(db, alert, viewer=user)
