"""Shapes of the data the API accepts and returns (checked automatically by Pydantic)."""
import datetime as dt
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai import NewPerson, ReminderSuggestion
from app.models import (LinkStatus, MemoryStatus, MemoryType, OccurrenceStatus, PersonType, ReminderKind,
                        ReminderStatus, Repeat, UserRole, Visibility)


# ---------- accounts ----------
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Vivek"])
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", examples=["vivek@example.com"])
    password: str = Field(min_length=6, max_length=72, examples=["secret123"])
    role: UserRole = UserRole.ELDER
    preferred_language: str = Field(default="en", pattern=r"^(en|hi|te)$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: UserRole
    preferred_language: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- people ----------
class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Ananya"])
    person_type: PersonType = PersonType.FAMILY
    relation_to_user: str | None = Field(default=None, max_length=50, examples=["granddaughter"])
    phone: str | None = Field(default=None, max_length=30, examples=["+91 90000 00002"])
    is_emergency_contact: bool = False


class PersonUpdate(BaseModel):
    """Every field is optional: send only what changes."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    person_type: PersonType | None = None
    relation_to_user: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    is_emergency_contact: bool | None = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    person_type: PersonType
    relation_to_user: str | None
    phone: str | None
    is_emergency_contact: bool
    created_at: datetime


# ---------- relationships between people ----------
class RelationshipCreate(BaseModel):
    from_person_id: int = Field(examples=[2])
    to_person_id: int = Field(examples=[3])
    relation: str = Field(min_length=1, max_length=50, examples=["daughter"])


class RelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_person_id: int
    to_person_id: int
    relation: str


# ---------- memories (Step 3) ----------
class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int | None
    memory_type: MemoryType
    original_text: str
    normalized_fact: str
    attribute: str | None
    value: str | None
    event_date: date | None
    confidence: float
    status: MemoryStatus
    visibility: Visibility
    replaces_id: int | None = None   # set when this memory corrects an older one
    valid_from: date | None = None
    valid_to: date | None = None     # set when it was replaced (HISTORICAL)
    created_at: datetime
    approved_at: datetime | None


class MemoryHit(BaseModel):
    """One search result: the memory, how it was found, and how close its meaning is."""
    memory: MemoryOut
    matched_by: str           # "person", "meaning" or "recent"
    distance: float | None    # 0.0 = same meaning; smaller is closer


class VisibilityUpdate(BaseModel):
    visibility: Visibility


# ---------- chat (Step 3) ----------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000, examples=["My granddaughter Ananya started computer engineering at NIT Kurukshetra this year."])


class ChatOut(BaseModel):
    reply: str
    intent: str
    pending_memories: list[MemoryOut] = []   # waiting for the user's yes/no
    forget_candidates: list[MemoryOut] = []  # the user asked to forget these; confirm with DELETE /memories/{id}
    suggested_people: list[NewPerson] = []   # people the AI heard about who aren't saved yet
    reminder_suggestion: ReminderSuggestion | None = None  # set it by answering "yes"
    waiting_for_yes_or_no: bool = False  # True: just reply "yes" or "no" to the question


# ---------- reminders (Step 4a) ----------
class ReminderCreate(BaseModel):
    """You can paste a chat 'reminder_suggestion' straight in here."""
    title: str = Field(min_length=1, max_length=200, examples=["Meet Dr. Sharma"])
    kind: ReminderKind = Field(examples=["APPOINTMENT"])
    date: dt.date = Field(examples=["2026-11-23"])   # dt.date because the field itself is called "date"
    time: dt.time = Field(examples=["11:00"])
    repeat: Repeat = Repeat.NONE
    notes: str | None = Field(default=None, max_length=500, examples=["Bring the blood test report"])
    person_id: int | None = None
    # Leave these out to use sensible defaults for the kind (appointments: 1 hour before + the evening before).
    remind_minutes_before: int | None = Field(default=None, ge=0, le=7 * 24 * 60)
    remind_previous_evening: bool | None = None
    visibility: Visibility = Visibility.CARE


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: ReminderKind
    notes: str | None
    person_id: int | None
    due_at: datetime
    repeat: Repeat
    remind_minutes_before: int
    remind_previous_evening: bool
    status: ReminderStatus
    visibility: Visibility
    suggested_by_id: int | None = None
    next_alert_at: datetime | None = None
    next_alert_local: str | None = None


class AlertOut(BaseModel):
    """One alert. 'title' and 'when' are ready to show on screen."""
    id: int
    reminder_id: int
    title: str
    kind: ReminderKind
    notes: str | None
    when: str              # local time of the event, e.g. "Mon 23 Nov, 11:00 AM"
    for_due_at: datetime
    fire_at: datetime
    is_main: bool          # False = an early "evening before" alert
    status: OccurrenceStatus
    snooze_count: int


# ---------- family (Step 5) ----------
class Scopes(BaseModel):
    """What a family member may see. Conversations and PRIVATE memories are never shared."""
    can_see_medicines: bool = True
    can_see_appointments: bool = True
    can_see_shared_memories: bool = False
    can_see_emergency: bool = True
    can_suggest_reminders: bool = True


class FamilyLinkCreate(Scopes):
    family_email: str = Field(examples=["priya@example.com"])
    relation: str = Field(min_length=1, max_length=50, examples=["daughter"])


class FamilyLinkUpdate(BaseModel):
    """Send only what changes."""
    relation: str | None = Field(default=None, max_length=50)
    can_see_medicines: bool | None = None
    can_see_appointments: bool | None = None
    can_see_shared_memories: bool | None = None
    can_see_emergency: bool | None = None
    can_suggest_reminders: bool | None = None


class FamilyLinkOut(Scopes):
    id: int
    relation: str
    status: LinkStatus
    family_user_id: int
    family_name: str
    family_email: str
    elder_id: int
    elder_name: str
    created_at: datetime


class SharedMemoryOut(BaseModel):
    fact: str
    event_date: date | None
    told_on: str


class EmergencyOut(BaseModel):
    contacts: list[PersonOut]
    information: list[str]   # memories the elder marked EMERGENCY, e.g. "Blood group B+"


class FamilyDashboard(BaseModel):
    """Only the sections the elder allows are filled; the rest are listed in hidden_sections."""
    elder_name: str
    relation: str
    as_of: str
    medicines_today: list[AlertOut] | None = None
    missed_medicines_today: int | None = None
    upcoming_appointments: list[AlertOut] | None = None
    shared_memories: list[SharedMemoryOut] | None = None
    emergency: EmergencyOut | None = None
    hidden_sections: list[str] = []


class AccessLogOut(BaseModel):
    viewer_name: str
    section: str
    viewed_at: str


class ReminderSuggestionIn(BaseModel):
    """A family member's suggestion. It does nothing until the elder accepts it."""
    title: str = Field(min_length=1, max_length=200, examples=["Call Priya"])
    kind: ReminderKind = Field(examples=["CALL"])
    date: dt.date = Field(examples=["2026-11-24"])
    time: dt.time = Field(examples=["18:00"])
    repeat: Repeat = Repeat.NONE
    notes: str | None = Field(default=None, max_length=500)
