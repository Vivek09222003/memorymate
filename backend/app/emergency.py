"""Emergency mode: the elder asks for help, and everyone who may see emergency information is alerted.

Two ways in:
  - the red Help button      → POST /emergency/sos
  - chat words like "bachao", "help me", "I fell", "emergency", "ambulance"
    → caught here BEFORE the AI is called, so it works even when the AI service is busy.

The AI can also notice that someone sounds unwell; then the chat only SUGGESTS pressing Help
(see routers/chat.py), so a sentence like "I'm a bit tired" never alarms the whole family.
"""
import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (AlertStatus, EmergencyAlert, Memory, MemoryStatus, Person, User, Visibility)
from app.timeutil import local_now

# Phrases that talk ABOUT emergencies ("add Rajesh as my emergency contact") are not emergencies.
_ABOUT = re.compile(r"emergency\s*(contact|number|info|information|detail|list|mode|button)s?|"
                    r"what\s*(is|'s|does)\s*(an?\s*)?(sos|emergency)|(sos|emergency)\s*(kya|ka\s*matlab)|"
                    r"आपातकालीन\s*संपर्क", re.IGNORECASE)

# Clear calls for help, in English, Hinglish and Hindi. Any one of these is enough.
_STRONG = re.compile(
    r"\b(sos|emergency|ambulance|bachao|bachaao|bachaon|i\s*(have\s*)?fell|i\s*have\s*fallen|fell\s*down|"
    r"gir\s*(gaya|gayi|gai|gya|gyi)|chest\s*pain|heart\s*attack|can'?t\s*breathe|cannot\s*breathe|"
    r"saans\s*nahi|seene\s*(mein|me|main)\s*dard|madad\s*(karo|kijiye|kro|chahiye|chaiye))\b"
    r"|बचाओ|बचाइए|एम्बुलेंस|आपातकाल|गिर\s*ग(या|ई|यी)|सीने\s*में\s*दर्द|सांस\s*नहीं|मदद\s*(करो|कीजिए|चाहिए)",
    re.IGNORECASE)

# "help" / "madad" on its own counts only in a short message ("help!", "help me please"),
# so "can you help me remember Rajesh's number?" is a normal chat.
_HELP = re.compile(r"\b(help|madad)\b|मदद", re.IGNORECASE)

# One alert at a time: pressing Help again within this time reuses the open alert.
REUSE_WITHIN = timedelta(minutes=30)


def is_emergency(text: str) -> bool:
    t = _ABOUT.sub(" ", text or "")
    if _STRONG.search(t):
        return True
    words = re.findall(r"\w+", t)
    return len(words) <= 4 and bool(_HELP.search(t)) and "?" not in t


def contacts(db: Session, elder_id: int) -> list[Person]:
    return db.scalars(select(Person).where(Person.owner_id == elder_id,
                                           Person.is_emergency_contact.is_(True))
                      .order_by(Person.name)).all()


def information(db: Session, elder_id: int) -> list[str]:
    """Facts the elder chose to show in emergencies, e.g. 'Blood group B+'."""
    return list(db.scalars(select(Memory.normalized_fact).where(
        Memory.owner_id == elder_id, Memory.status == MemoryStatus.ACTIVE,
        Memory.visibility == Visibility.EMERGENCY)).all())


def active_alert(db: Session, elder_id: int) -> EmergencyAlert | None:
    return db.scalar(select(EmergencyAlert).where(EmergencyAlert.elder_id == elder_id,
                                                  EmergencyAlert.status == AlertStatus.ACTIVE)
                     .order_by(EmergencyAlert.id.desc()))


def raise_alert(db: Session, elder: User, source: str, message: str | None = None) -> EmergencyAlert:
    """Open an alert (or reuse the one opened in the last 30 minutes). The caller commits."""
    open_alert = active_alert(db, elder.id)
    if open_alert and open_alert.created_at >= local_now() - REUSE_WITHIN:
        if message:
            open_alert.message = message
        return open_alert
    alert = EmergencyAlert(elder_id=elder.id, source=source, message=message)
    db.add(alert)
    db.flush()
    return alert


def resolve(alert: EmergencyAlert, by: User) -> None:
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = local_now()
    alert.resolved_by_id = by.id


def reply(language: str, people: list[Person], someone_alerted: bool) -> str:
    """What MemoryMate says right after help is asked for. Short, calm, and in the chosen language."""
    numbers = ", ".join(f"{p.name}: {p.phone}" for p in people if p.phone)
    if language == "hi":
        text = ("मैंने आपके परिवार को तुरंत सूचना भेज दी है। घबराइए नहीं, मदद आ रही है।" if someone_alerted
                else "अभी कोई परिवार वाला जुड़ा नहीं है, इसलिए कृपया तुरंत किसी को कॉल करें।")
        return text + (f"\nअभी इन्हें कॉल करें: {numbers}" if numbers else "") + "\nज़रूरत हो तो 108 पर कॉल करें।"
    if language == "hinglish":
        text = ("Maine aapki family ko turant alert bhej diya hai. Ghabraiye mat, madad aa rahi hai." if someone_alerted
                else "Abhi koi family member juda nahi hai, isliye kripya turant kisi ko call kijiye.")
        return text + (f"\nAbhi inhe call kijiye: {numbers}" if numbers else "") + "\nZaroorat ho to 108 par call kijiye."
    text = ("I've alerted your family right away. Stay calm, help is on the way." if someone_alerted
            else "No family member is connected yet, so please call someone right now.")
    return text + (f"\nCall now: {numbers}" if numbers else "") + "\nIf you need urgent help, call 108."
