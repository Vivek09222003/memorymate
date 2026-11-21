"""Reminder logic: planning alerts, ringing them on time, and repeating them.

A Reminder is the plan ("Metformin, every day at 8 PM").
A ReminderOccurrence is one alert ("tonight's 8 PM Metformin"), and records what the user did.
"""
import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import OccurrenceStatus, Reminder, ReminderOccurrence, ReminderStatus, Repeat
from app.timeutil import local_tz

log = logging.getLogger("memorymate.reminders")

MISSED_AFTER = timedelta(hours=1)   # an alert nobody answers becomes MISSED after this
CHECK_EVERY_SECONDS = 30
PREVIOUS_EVENING = time(18, 0)      # "the evening before" alert time


def _now() -> datetime:
    return datetime.now(timezone.utc)


def next_due(due: datetime, repeat: Repeat) -> datetime | None:
    """The next time a repeating reminder is due, keeping the same local clock time."""
    local = due.astimezone(local_tz())
    if repeat == Repeat.DAILY:
        nxt = local + timedelta(days=1)
    elif repeat == Repeat.WEEKLY:
        nxt = local + timedelta(weeks=1)
    elif repeat == Repeat.YEARLY:
        try:
            nxt = local.replace(year=local.year + 1)
        except ValueError:  # 29 February
            nxt = local.replace(year=local.year + 1, day=28)
    else:
        return None
    return nxt


def plan_alerts(db: Session, reminder: Reminder, due: datetime) -> None:
    """Create the alerts for one due time: the main one, and optionally the evening before."""
    now = _now()
    main_at = due - timedelta(minutes=reminder.remind_minutes_before)
    db.add(ReminderOccurrence(reminder_id=reminder.id, owner_id=reminder.owner_id,
                              for_due_at=due, fire_at=max(main_at, now), is_main=True))
    if reminder.remind_previous_evening:
        local_due = due.astimezone(local_tz())
        evening = datetime.combine(local_due.date() - timedelta(days=1), PREVIOUS_EVENING, tzinfo=local_tz())
        if evening > now:
            db.add(ReminderOccurrence(reminder_id=reminder.id, owner_id=reminder.owner_id,
                                      for_due_at=due, fire_at=evening, is_main=False))


def first_due(reminder: Reminder) -> datetime:
    """For a repeating reminder whose first time has passed today, start from the next one."""
    due = reminder.due_at
    while due < _now() and reminder.repeat != Repeat.NONE:
        due = next_due(due, reminder.repeat)
    return due


def advance(db: Session, occ: ReminderOccurrence) -> None:
    """After a main alert rings (or is marked done early): plan the next repeat,
    or close a one-time reminder. Only main alerts move a reminder forward."""
    if not occ.is_main or occ.advanced:
        return
    occ.advanced = True  # so a snooze or a second "done" can't plan the next one twice
    nxt = next_due(occ.for_due_at, occ.reminder.repeat)
    if nxt is not None:
        plan_alerts(db, occ.reminder, nxt)
    else:
        occ.reminder.status = ReminderStatus.COMPLETED


def tick(db: Session) -> int:
    """One pass of the scheduler. Returns how many alerts started ringing."""
    now = _now()

    # 1. Ring alerts whose time has come.
    ready = db.scalars(
        select(ReminderOccurrence)
        .join(Reminder)
        .where(ReminderOccurrence.status == OccurrenceStatus.SCHEDULED,
               ReminderOccurrence.fire_at <= now,
               Reminder.status == ReminderStatus.ACTIVE)
    ).all()
    for occ in ready:
        occ.status = OccurrenceStatus.DUE
        occ.fired_at = now
        log.info("Reminder ringing: %s (user %s)", occ.reminder.title, occ.owner_id)
        advance(db, occ)
        if occ.is_main and occ.reminder.repeat == Repeat.NONE:
            occ.reminder.status = ReminderStatus.COMPLETED  # also after a snoozed one-time alert

    # 2. Alerts nobody answered become MISSED (a later step can tell family, with permission).
    stale = db.scalars(
        select(ReminderOccurrence).where(
            ReminderOccurrence.status == OccurrenceStatus.DUE,
            ReminderOccurrence.fired_at <= now - MISSED_AFTER)
    ).all()
    for occ in stale:
        occ.status = OccurrenceStatus.MISSED

    db.commit()
    return len(ready)


async def run_forever() -> None:
    """Started when the server starts. Checks for due reminders every 30 seconds."""
    while True:
        try:
            await asyncio.to_thread(_tick_once)
        except Exception:  # never let one bad pass stop the scheduler
            log.exception("Reminder check failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def _tick_once() -> None:
    with SessionLocal() as db:
        tick(db)
