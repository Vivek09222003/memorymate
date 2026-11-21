"""Time helpers. The database stores UTC; people see their own local time."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.config import settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def local_now() -> datetime:
    """The current time where the user lives (not the server's UTC time)."""
    return datetime.now(local_tz())


def local_dt(d: date, t: time) -> datetime:
    """Combine a local date and time into a time-zone-aware datetime."""
    return datetime.combine(d, t, tzinfo=local_tz())


def show(dt: datetime) -> str:
    """Friendly local text, e.g. 'Mon 23 Nov, 11:00 AM'."""
    local = dt.astimezone(local_tz())
    return local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")
