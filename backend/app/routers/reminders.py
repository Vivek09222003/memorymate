"""Reminder endpoints: create, list, what's ringing now, today's checklist, done, snooze, cancel."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (OccurrenceStatus, Person, Reminder, ReminderKind, ReminderOccurrence,
                        ReminderStatus, Repeat, User)
from app.reminders import advance, first_due, plan_alerts, tick
from app.schemas import AlertOut, ReminderCreate, ReminderOut
from app.security import get_current_user
from app.timeutil import local_dt, local_now, local_tz, show

router = APIRouter(prefix="/reminders", tags=["Reminders"])

# Sensible defaults per kind: (minutes before, also remind the evening before?)
DEFAULTS = {
    ReminderKind.APPOINTMENT: (60, True),
    ReminderKind.BIRTHDAY: (0, True),
    ReminderKind.MEDICINE: (0, False),
    ReminderKind.CALL: (0, False),
    ReminderKind.TASK: (0, False),
}


def alert_out(o: ReminderOccurrence) -> AlertOut:
    r = o.reminder
    return AlertOut(id=o.id, reminder_id=r.id, title=r.title, kind=r.kind, notes=r.notes,
                    when=show(o.for_due_at), for_due_at=o.for_due_at, fire_at=o.fire_at,
                    is_main=o.is_main, status=o.status, snooze_count=o.snooze_count)


def _reminder_out(r: Reminder) -> ReminderOut:
    out = ReminderOut.model_validate(r)
    upcoming = [o for o in r.occurrences if o.status == OccurrenceStatus.SCHEDULED]
    if upcoming:
        out.next_alert_at = min(o.fire_at for o in upcoming)
        out.next_alert_local = show(out.next_alert_at)
    return out


def _own_alert(db: Session, user: User, alert_id: int) -> ReminderOccurrence:
    occ = db.get(ReminderOccurrence, alert_id)
    if occ is None or occ.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    return occ


def new_reminder(data: ReminderCreate, owner_id: int, *, suggested_by_id: int | None = None) -> Reminder:
    """Build a reminder from the request, with sensible defaults for its kind.
    A suggestion from family starts as SUGGESTED and gets no alerts until the elder accepts it."""
    due = local_dt(data.date, data.time)
    if data.repeat == Repeat.NONE and due <= local_now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That time has already passed.")
    minutes, evening = DEFAULTS[data.kind]
    return Reminder(
        owner_id=owner_id, person_id=data.person_id, title=data.title.strip(), kind=data.kind,
        notes=data.notes, due_at=due, repeat=data.repeat, visibility=data.visibility,
        remind_minutes_before=minutes if data.remind_minutes_before is None else data.remind_minutes_before,
        remind_previous_evening=(evening if data.remind_previous_evening is None else data.remind_previous_evening)
        and data.repeat == Repeat.NONE,  # no "evening before" for daily medicines
        status=ReminderStatus.SUGGESTED if suggested_by_id else ReminderStatus.ACTIVE,
        suggested_by_id=suggested_by_id,
    )


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder(data: ReminderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.person_id is not None:
        person = db.get(Person, data.person_id)
        if person is None or person.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found.")
    reminder = new_reminder(data, user.id)
    db.add(reminder)
    db.flush()
    plan_alerts(db, reminder, first_due(reminder))
    db.commit()
    db.refresh(reminder)
    return _reminder_out(reminder)


@router.get("/suggestions", response_model=list[ReminderOut])
def suggestions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Reminders that family members suggested, waiting for your yes or no."""
    return [_reminder_out(r) for r in db.scalars(
        select(Reminder).where(Reminder.owner_id == user.id, Reminder.status == ReminderStatus.SUGGESTED)
        .order_by(Reminder.created_at)).all()]


def _own_suggestion(db: Session, user: User, reminder_id: int) -> Reminder:
    reminder = db.get(Reminder, reminder_id)
    if reminder is None or reminder.owner_id != user.id or reminder.status != ReminderStatus.SUGGESTED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suggestion not found.")
    return reminder


@router.post("/{reminder_id}/accept", response_model=ReminderOut)
def accept_suggestion(reminder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Yes: the suggested reminder becomes active and will ring."""
    reminder = _own_suggestion(db, user, reminder_id)
    due = first_due(reminder)
    if reminder.repeat == Repeat.NONE and due <= local_now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That time has already passed. Decline it instead.")
    reminder.status = ReminderStatus.ACTIVE
    plan_alerts(db, reminder, due)
    db.commit()
    db.refresh(reminder)
    return _reminder_out(reminder)


@router.post("/{reminder_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_suggestion(reminder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """No: the suggestion is dropped."""
    reminder = _own_suggestion(db, user, reminder_id)
    reminder.status = ReminderStatus.CANCELLED
    db.commit()


@router.get("", response_model=list[ReminderOut])
def list_reminders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """All active reminders, soonest first."""
    reminders = db.scalars(
        select(Reminder).where(Reminder.owner_id == user.id, Reminder.status == ReminderStatus.ACTIVE)
    ).all()
    out = [_reminder_out(r) for r in reminders]
    far = datetime.max.replace(tzinfo=timezone.utc)
    return sorted(out, key=lambda r: r.next_alert_at or far)


@router.get("/due", response_model=list[AlertOut])
def ringing_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Alerts ringing right now. The app checks this every 30 seconds and shows a big popup."""
    alerts = db.scalars(
        select(ReminderOccurrence)
        .where(ReminderOccurrence.owner_id == user.id, ReminderOccurrence.status == OccurrenceStatus.DUE)
        .order_by(ReminderOccurrence.fire_at)
    ).all()
    return [alert_out(o) for o in alerts]


@router.get("/today", response_model=list[AlertOut])
def today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Today's checklist (main alerts only). For medicines this is the intake log:
    DONE = taken, MISSED = not taken, SCHEDULED = later today."""
    start = datetime.combine(local_now().date(), datetime.min.time(), tzinfo=local_tz())
    alerts = db.scalars(
        select(ReminderOccurrence)
        .where(ReminderOccurrence.owner_id == user.id,
               ReminderOccurrence.is_main.is_(True),
               ReminderOccurrence.for_due_at >= start,
               ReminderOccurrence.for_due_at < start + timedelta(days=1))
        .order_by(ReminderOccurrence.for_due_at)
    ).all()
    return [alert_out(o) for o in alerts]


@router.post("/alerts/{alert_id}/done", response_model=AlertOut)
def mark_done(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """'Taken' / 'Done'. Works early (before it rings) and late (after it was missed)."""
    occ = _own_alert(db, user, alert_id)
    if occ.status == OccurrenceStatus.SKIPPED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reminder was cancelled.")
    if occ.status == OccurrenceStatus.SCHEDULED:
        advance(db, occ)  # done early: still plan the next repeat
    occ.status = OccurrenceStatus.DONE
    occ.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(occ)
    return alert_out(occ)


@router.post("/alerts/{alert_id}/snooze", response_model=AlertOut)
def snooze(alert_id: int, minutes: int = Query(10, ge=1, le=240),
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """'Remind me later': rings again after the given minutes."""
    occ = _own_alert(db, user, alert_id)
    if occ.status not in (OccurrenceStatus.DUE, OccurrenceStatus.MISSED):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only a ringing or missed alert can be snoozed.")
    occ.status = OccurrenceStatus.SCHEDULED
    occ.fire_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    occ.fired_at = None
    occ.snooze_count += 1
    if occ.reminder.status == ReminderStatus.COMPLETED:
        occ.reminder.status = ReminderStatus.ACTIVE  # so a one-time reminder can ring again
    db.commit()
    db.refresh(occ)
    return alert_out(occ)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel(reminder_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reminder = db.get(Reminder, reminder_id)
    if reminder is None or reminder.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found.")
    reminder.status = ReminderStatus.CANCELLED
    for o in reminder.occurrences:
        if o.status == OccurrenceStatus.SCHEDULED:
            o.status = OccurrenceStatus.SKIPPED
    db.commit()


@router.post("/check-now", tags=["Testing"])
def check_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """For testing: run the reminder check immediately instead of waiting up to 30 seconds."""
    return {"started_ringing": tick(db)}
