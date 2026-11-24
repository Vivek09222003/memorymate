"""Database tables for the memory vault.

User ── Person ── Relationship
  │        │
  ├── Message
  ├── Memory (optionally about a Person, linked to the Message it came from)
  ├── Reminder ── ReminderOccurrence (each time it rings, and what the user did)
  ├── FamilyLink (a trusted family member and exactly what they may see)
  ├── AccessLog (who looked at what, and when)
  ├── ChatState (what MemoryMate just asked, so a plain "yes" or "no" can answer it)
  └── EmergencyAlert (the elder asked for help; family and doctors see it until it's resolved)
"""
import enum
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


# ---------- fixed choices ----------
class UserRole(str, enum.Enum):
    ELDER = "ELDER"      # the person MemoryMate helps
    FAMILY = "FAMILY"    # a trusted family member or caregiver
    DOCTOR = "DOCTOR"    # the elder's doctor: sees health information, can suggest medicines and notes




# People who can be linked to an elder and see what the elder allows.
HELPER_ROLES = (UserRole.FAMILY, UserRole.DOCTOR)


class PersonType(str, enum.Enum):
    FAMILY = "FAMILY"
    FRIEND = "FRIEND"
    DOCTOR = "DOCTOR"
    OTHER = "OTHER"


class MemoryType(str, enum.Enum):
    PERSONAL_FACT = "PERSONAL_FACT"   # "Ananya studies engineering"
    PREFERENCE = "PREFERENCE"         # "I like tea at 7 AM"
    EVENT = "EVENT"                   # "Ravi visited on Sunday"
    HEALTH = "HEALTH"                 # "Dr. Sharma said to walk daily"
    ROUTINE = "ROUTINE"               # "I call my daughter on Sunday evenings"


class MemoryStatus(str, enum.Enum):
    PENDING = "PENDING"        # waiting for the user to say yes
    ACTIVE = "ACTIVE"          # approved and current
    HISTORICAL = "HISTORICAL"  # replaced by a newer fact (kept for the timeline)
    DELETED = "DELETED"        # forgotten at the user's request


class Visibility(str, enum.Enum):
    PRIVATE = "PRIVATE"              # only the user and the AI
    SHARED_FAMILY = "SHARED_FAMILY"  # trusted family members
    CARE = "CARE"                    # medicines and appointments
    EMERGENCY = "EMERGENCY"          # shown in emergency mode


class ReminderKind(str, enum.Enum):
    MEDICINE = "MEDICINE"
    APPOINTMENT = "APPOINTMENT"
    BIRTHDAY = "BIRTHDAY"
    CALL = "CALL"
    TASK = "TASK"


class Repeat(str, enum.Enum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    YEARLY = "YEARLY"


class ReminderStatus(str, enum.Enum):
    SUGGESTED = "SUGGESTED"   # proposed by a family member, waiting for the elder's yes
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"   # a one-time reminder that has happened
    CANCELLED = "CANCELLED"


class OccurrenceStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"  # waiting for its time
    DUE = "DUE"              # ringing now, waiting for the user
    DONE = "DONE"            # user pressed Done / Taken
    MISSED = "MISSED"        # nobody answered within an hour
    SKIPPED = "SKIPPED"      # the reminder was cancelled before it rang


def _enum(e):
    # Store enums as plain text so they're easy to read in the database.
    return Enum(e, native_enum=False, length=20)


# ---------- tables ----------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole), default=UserRole.ELDER)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")  # en, hi, te
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    people: Mapped[list["Person"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    memories: Mapped[list["Memory"]] = relationship(back_populates="owner", cascade="all, delete-orphan",
                                                    foreign_keys="Memory.owner_id")


class Person(Base):
    """Someone in the user's life: family, friends, doctors."""
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    person_type: Mapped[PersonType] = mapped_column(_enum(PersonType), default=PersonType.FAMILY)
    relation_to_user: Mapped[str | None] = mapped_column(String(50))  # "granddaughter", "cardiologist"
    phone: Mapped[str | None] = mapped_column(String(30))
    is_emergency_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="people")
    memories: Mapped[list["Memory"]] = relationship(back_populates="person")


class Relationship(Base):
    """A link between two people, e.g. Priya --daughter--> Ananya.
    Direct links to the user are stored on Person.relation_to_user instead."""
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    to_person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(50))  # "daughter": to_person is from_person's daughter


class Message(Base):
    """Every chat message, so each memory can point back to where it came from."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # "user" or "assistant"
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Memory(Base):
    """One structured, permission-controlled memory."""
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), index=True)
    source_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    # Step 4c: the older memory this one corrects (it becomes HISTORICAL when this is approved)
    replaces_id: Mapped[int | None] = mapped_column(ForeignKey("memories.id", ondelete="SET NULL"))
    # Doctor's notes: who wrote it (the elder still has to accept it)
    suggested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    memory_type: Mapped[MemoryType] = mapped_column(_enum(MemoryType))
    original_text: Mapped[str] = mapped_column(Text)        # the user's own words, any language
    normalized_fact: Mapped[str] = mapped_column(Text)      # short English fact used for search
    attribute: Mapped[str | None] = mapped_column(String(50))  # "education", "city", "birthday"
    value: Mapped[str | None] = mapped_column(String(255))     # "Computer Engineering", "Bangalore"
    event_date: Mapped[date | None] = mapped_column(Date)

    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 to 1.0
    status: Mapped[MemoryStatus] = mapped_column(_enum(MemoryStatus), default=MemoryStatus.PENDING, index=True)
    visibility: Mapped[Visibility] = mapped_column(_enum(Visibility), default=Visibility.PRIVATE)

    valid_from: Mapped[date | None] = mapped_column(Date)   # when this became true
    valid_to: Mapped[date | None] = mapped_column(Date)     # set when replaced by a newer fact
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Filled in Step 4 (vector search).
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim), nullable=True)

    owner: Mapped[User] = relationship(back_populates="memories", foreign_keys=[owner_id])
    person: Mapped[Person | None] = relationship(back_populates="memories")
    source_message: Mapped[Message | None] = relationship()


class Reminder(Base):
    """Something to remember at a time: a medicine, appointment, birthday, call or task."""
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"))
    source_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[ReminderKind] = mapped_column(_enum(ReminderKind))
    notes: Mapped[str | None] = mapped_column(Text)        # e.g. "500 mg, after dinner"
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # first (or only) time
    repeat: Mapped[Repeat] = mapped_column(_enum(Repeat), default=Repeat.NONE)
    remind_minutes_before: Mapped[int] = mapped_column(Integer, default=0)
    remind_previous_evening: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ReminderStatus] = mapped_column(_enum(ReminderStatus), default=ReminderStatus.ACTIVE, index=True)
    visibility: Mapped[Visibility] = mapped_column(_enum(Visibility), default=Visibility.CARE)
    suggested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))  # Step 5
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    occurrences: Mapped[list["ReminderOccurrence"]] = relationship(
        back_populates="reminder", cascade="all, delete-orphan", order_by="ReminderOccurrence.fire_at")


class ReminderOccurrence(Base):
    """One alert. For medicines this is also the intake log ("Did I take my 8 PM tablet?")."""
    __tablename__ = "reminder_occurrences"

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    for_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # the event this alert is about
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)  # when to ring
    is_main: Mapped[bool] = mapped_column(Boolean, default=True)  # False for "evening before" alerts
    advanced: Mapped[bool] = mapped_column(Boolean, default=False)  # next repeat already planned
    status: Mapped[OccurrenceStatus] = mapped_column(
        _enum(OccurrenceStatus), default=OccurrenceStatus.SCHEDULED, index=True)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snooze_count: Mapped[int] = mapped_column(Integer, default=0)

    reminder: Mapped[Reminder] = relationship(back_populates="occurrences")


class LinkStatus(str, enum.Enum):
    INVITED = "INVITED"   # access given, waiting for the family member to join with the code
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class FamilyLink(Base):
    """A trusted family member (or doctor) linked by the elder, with what they may see.
    Only the elder creates, changes or revokes it. Conversations and PRIVATE memories are never shared."""
    __tablename__ = "family_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(50))  # "son", "daughter", "doctor"
    invite_name: Mapped[str | None] = mapped_column(String(100))  # who it's for, before they join
    invite_code: Mapped[str | None] = mapped_column(String(12), unique=True)  # they enter it to join
    status: Mapped[LinkStatus] = mapped_column(_enum(LinkStatus), default=LinkStatus.ACTIVE)

    can_see_medicines: Mapped[bool] = mapped_column(Boolean, default=True)
    can_see_appointments: Mapped[bool] = mapped_column(Boolean, default=True)
    can_see_shared_memories: Mapped[bool] = mapped_column(Boolean, default=False)
    can_see_emergency: Mapped[bool] = mapped_column(Boolean, default=True)
    can_suggest_reminders: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    elder: Mapped[User] = relationship(foreign_keys=[elder_id])
    family_user: Mapped[User | None] = relationship(foreign_keys=[family_user_id])

    @property
    def display_name(self) -> str:
        return self.family_user.name if self.family_user else (self.invite_name or "family member")


class AccessLog(Base):
    """Every time a family member opens part of the elder's information."""
    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    viewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(50))  # "medicines", "appointments", ...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    viewer: Mapped[User] = relationship(foreign_keys=[viewer_id])


class ChatState(Base):
    """What the last reply asked the user to confirm. One row per user, replaced every turn.
    pending = {"memory_ids": [..], "forget_ids": [..], "reminder": {..} | None, "people": [{..}]}"""
    __tablename__ = "chat_states"

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    pending: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class AlertStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"       # help was asked for; family and doctors see a red alert
    RESOLVED = "RESOLVED"   # the elder said they're safe, or a family member handled it


class EmergencyAlert(Base):
    """The elder pressed Help or said something like "bachao" / "I fell". Shown to every linked helper
    who may see emergency information, until the elder or a helper marks it resolved."""
    __tablename__ = "emergency_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(10))           # "button" or "chat"
    message: Mapped[str | None] = mapped_column(Text)          # what they said, if it came from chat
    status: Mapped[AlertStatus] = mapped_column(_enum(AlertStatus), default=AlertStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    elder: Mapped[User] = relationship(foreign_keys=[elder_id])
    resolved_by: Mapped[User | None] = relationship(foreign_keys=[resolved_by_id])
