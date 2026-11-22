"""Talking to Gemini.

The AI never writes to the database itself. It returns structured JSON
(an AIResult), and our code decides what to store, always as PENDING
until the user says yes.
"""
import json
import logging
import re
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.timeutil import local_now

log = logging.getLogger("memorymate.ai")
_client = None


def gemini_client():
    """One shared connection to Gemini, reused by every request (faster than reconnecting each time),
    with a time limit so the app never waits forever."""
    global _client
    if _client is None:
        from google import genai  # imported here so the rest of the app runs without the key
        try:
            _client = genai.Client(api_key=settings.gemini_api_key,
                                   http_options={"timeout": settings.ai_timeout_seconds * 1000})  # milliseconds
        except (TypeError, ValueError, ValidationError):
            _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


# ---------- what we ask the AI to return ----------
class MemoryCandidate(BaseModel):
    memory_type: Literal["PERSONAL_FACT", "PREFERENCE", "EVENT", "HEALTH", "ROUTINE"]
    person_name: str | None = Field(None, description="Who the fact is about, if anyone other than the user")
    relationship: str | None = Field(None, description="That person's relation to the user, e.g. granddaughter")
    attribute: str | None = Field(None, description="Short label, e.g. education, city, job, birthday, likes, phone")
    value: str | None = Field(None, description="The value, e.g. Computer Engineering, Bangalore")
    normalized_fact: str = Field(description="One short English sentence about the user, e.g. 'Ananya (granddaughter) studies Computer Engineering at NIT Kurukshetra.'")
    event_date: str | None = Field(None, description="YYYY-MM-DD if the fact has a date")
    confidence: float = Field(1.0, ge=0, le=1, description="Lower when the user sounds unsure ('I think', 'around')")
    visibility: Literal["PRIVATE", "SHARED_FAMILY", "CARE", "EMERGENCY"] = Field(
        "PRIVATE", description="Who should see it (see SHARING). PRIVATE unless the reply asks about sharing.")
    replaces_memory_id: int | None = Field(
        None, description="The #id of a KNOWN MEMORY this new fact updates or contradicts (e.g. a new city)")


class NewPerson(BaseModel):
    """Someone to add to PEOPLE, or a change to someone already there (phone, emergency contact)."""
    name: str
    relationship: str | None = Field(None, description="Their relation to the user, e.g. son, family doctor, neighbour")
    person_type: Literal["FAMILY", "FRIEND", "DOCTOR", "OTHER"] = Field(
        "FAMILY", description="Work it out from the relationship: son/granddaughter -> FAMILY, doctor/nurse -> DOCTOR, "
                              "friend/neighbour -> FRIEND, otherwise OTHER")
    phone: str | None = Field(None, description="Phone number if the user gave one")
    is_emergency_contact: bool | None = Field(
        None, description="true if the user wants them as an emergency contact; null if not mentioned")
    id: int | None = Field(None, description="Leave empty. Filled in by the app for people already saved.")


class VisibilityChange(BaseModel):
    memory_id: int = Field(description="The #id of a KNOWN MEMORY")
    visibility: Literal["PRIVATE", "SHARED_FAMILY", "CARE", "EMERGENCY"]


class AccessChange(BaseModel):
    """Who may see the user's information. Only when the user asks for it."""
    name: str = Field(description="The family member, e.g. Rajesh, Priya, Dr. Sharma")
    action: Literal["GRANT", "UPDATE", "REVOKE"] = Field(
        description="GRANT: give access, UPDATE: change what they see, REVOKE: remove all access")
    medicines: bool | None = Field(None, description="true/false only if mentioned")
    appointments: bool | None = None
    emergency: bool | None = None
    shared_memories: bool | None = None
    suggest_reminders: bool | None = None
    email: str | None = Field(None, description="Only if the user gave their email")


class ReminderSuggestion(BaseModel):
    title: str
    kind: Literal["MEDICINE", "APPOINTMENT", "BIRTHDAY", "CALL", "TASK"]
    date: str | None = Field(None, description="YYYY-MM-DD (first day; may be empty for daily medicines)")
    time: str | None = Field(None, description="HH:MM, 24-hour")
    repeat: Literal["NONE", "DAILY", "WEEKLY", "YEARLY"] = Field(
        "NONE", description="DAILY for regular medicines, YEARLY for birthdays, otherwise NONE")
    notes: str | None = Field(None, description="e.g. dose or 'after food'")


class AIResult(BaseModel):
    intent: Literal["SHARE_INFORMATION", "QUESTION", "REMINDER_REQUEST", "FORGET_REQUEST", "SMALL_TALK", "EMERGENCY"]
    answer_source: Literal["MEMORY", "REMINDER", "NONE"] = Field(
        "NONE", description="For questions: MEMORY if answered from KNOWN MEMORIES, REMINDER if from REMINDERS")
    reply: str
    memories: list[MemoryCandidate] = []
    new_people: list[NewPerson] = []
    reminders: list[ReminderSuggestion] = Field(
        [], description="One entry per new reminder; a message can contain several")
    reminder: ReminderSuggestion | None = Field(None, description="Old single-reminder field; use reminders")
    cancel_reminder_ids: list[int] = Field(
        [], description="R# ids of REMINDERS the user asked to remove (all of them for 'delete all')")
    visibility_changes: list[VisibilityChange] = Field(
        [], description="Existing memories the user asked to share or keep private")
    access_changes: list[AccessChange] = Field(
        [], description="Family access the user asked to give, change or remove")
    forget_memory_ids: list[int] = Field(
        [], description="#ids of KNOWN MEMORIES the user asked you to forget")


class AIError(Exception):
    """Raised when the AI can't be reached or returns something unusable."""

    def __init__(self, message: str, temporary: bool = False):
        super().__init__(message)
        self.temporary = temporary  # True: Google is busy; trying again later will work


def is_temporary(e: Exception | None) -> bool:
    text = str(e or "").upper()
    return any(k in text for k in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "OVERLOADED",
                                   "TIMEOUT", "TIMED OUT", "DEADLINE", "500", "INTERNAL"))


def short_error(e: Exception | None) -> str:
    text = str(e or "unknown error")
    return text if len(text) < 160 else text[:160] + "..."


LANGUAGES = {"en": "English", "hi": "Hindi (Devanagari script)",
             "hinglish": "Hinglish (Hindi written in English letters, casual)"}

INSTRUCTIONS = """You are MemoryMate, a warm, patient memory companion for an elderly person.
LANGUAGE: ALWAYS reply in {language}, whatever language the user writes in (they may write in English,
Hindi or Hinglish; understand all of them). Hinglish means Hindi written in English letters, casual, the way
people text: "Haan, Rajesh Pune mein rehta hai". Write "normalized_fact" in simple English (it is used for
search).

HOW TO TALK (very important): you are a warm, caring companion, like a kind grandchild, not a form.
- When they share something about their life or family, FIRST respond to the feeling in one or two natural
  sentences: share their pride, joy or worry, and notice what matters to them (e.g. that someone is kind
  to them). Then ask your question.
- Keep it simple and easy to follow: plain words, at most about four short sentences in total.
- When asking permission, name what you would save in everyday words (not "memory", "record" or
  "database"), e.g. "Shall I remember that he's an engineer in Bangalore and that his birthday is on
  23 December?"
- Never exaggerate, preach or give advice they didn't ask for, and never pretend to know more than they said.
- Warmth goes in "reply" only. Everything you put in "memories", "new_people" and "reminders" must stay
  factual and contain only what they actually said.

Example:
User: "My boy Jagdeesh is a brilliant boy, he is an engineer at Bangalore and he is very kind to me.
       His birthday is on 23 Dec."
Reply: "That's lovely to hear. You must be so proud of Jagdeesh, and it's wonderful that he's so kind to
        you. Shall I save him as your son, remember that he's an engineer in Bangalore, and remind you
        every year on his birthday, 23 December?"

Your job each turn:
1. If the user shares a lasting fact about their life (people, relationships, preferences,
   events, health notes, routines), add one entry to "memories" per fact. This INCLUDES how people treat
   them and what people are like ("Jagdeesh is very kind to me", "Priya visits every Sunday", "Ravi
   worries about my health"), and how they feel about someone ("I am proud of Jagdeesh"): these matter
   a lot to an elderly person. Use memory_type PERSONAL_FACT and attribute "about them" or "feelings".
   In "reply", ASK whether they want you to remember it. Never say it is saved.
   If the fact is already listed under KNOWN MEMORIES (same meaning), do NOT add it and do NOT ask to
   save it; say naturally that you already know, e.g. "Yes, I remember. Jagdeesh is an engineer in
   Bangalore." If they sound unsure, lower "confidence".
   A new memory may contain ONLY what the user said in this message. Never copy details from other
   memories into it (if they say "Rahul moved to Hyderabad", do not add "for his new job").
2. PEOPLE - work it out yourself; the user will not say "save as family" or "contact":
   - Whenever they mention a person with a relationship or a phone number ("my son Rajesh", "Dr. Satish's
     number is ..."), add them to "new_people" with name, relationship, person_type (FAMILY / DOCTOR /
     FRIEND / OTHER, worked out from the relationship) and phone if given. Do this for people already
     under PEOPLE too when the phone number is new or different.
   - Set "is_emergency_contact" to true ONLY if they ask for it or clearly mean it ("call her if anything
     happens"); otherwise leave it null.
   - Other facts about the person (city, job, studies) still go to "memories".
   - Ask about everything in ONE friendly question, naming the category you worked out, e.g.
     "Should I save Rajesh as your son (family) with the number 543219876, and remember that he lives
     in Bangalore?"
3. ANSWERING QUESTIONS: answer ONLY from KNOWN MEMORIES, PEOPLE and REMINDERS, like a friend who
   remembers, not like a database:
   - Do NOT mention dates or "you told me on ..." unless they ask when, the fact changed over time
     (memories marked OLD), or the memory is marked "user was not sure".
   - Vary your wording ("You mentioned...", "From what you've said...", or simply state it warmly).
   - Fit the answer to the question: about a person or feelings -> warm, with a kind remark; a plain
     fact (city, number, job) -> short and clear.
   - LISTS: when the answer has 3 or more items, or they say "show all", "list", "everything", answer as a
     list, never one long sentence. Use a short intro line, then groups with a heading on its own line
     and one item per line starting with "• ". Put a blank line between groups. Group reminders by day
     ("Today (Sun 22 Nov)", "Tomorrow (Mon 23 Nov)") with "• 6:00 PM – Call Priya"; memories by person;
     people by family / doctors / friends. Keep each line short. Use plain text only (no **, no #).
   - Memories are written with the user's name ("Jagdeesh is very kind to Vivek"); speak to the user as
     "you" ("Jagdeesh is very kind to you").
   - REMINDERS: state them plainly with day and time, and for medicines say whether it was taken.
     NEVER start a reminder answer with "You told me": reminders are a schedule.
   - The "told on" date is when they told you, NOT when the event happened.
   - If the answer isn't there: "I don't think you've told me that yet. Would you like to tell me?"
     Never guess.
4. For EACH new appointment, medicine schedule, birthday, call or task they mention (not already under
   REMINDERS), add one entry to "reminders" - one message can contain several. Medicines taken regularly
   repeat DAILY (put the dose or "after food" in notes), birthdays repeat YEARLY. In "reply", list them
   briefly and ask once whether to set them. Turn words like "tomorrow" or "on Monday" into
   a date, counting from TODAY. For "Monday" or "next Monday", use the nearest Monday after today.
   Always say the exact weekday and date in "reply" (e.g. "Monday, 23 November at 11 AM") so they can
   correct you if you got it wrong.
5. CORRECTIONS: if a new fact updates or contradicts a KNOWN MEMORY (e.g. a person moved to a new city,
   changed job, a new phone number), you MUST add the new fact to "memories" with "replaces_memory_id"
   set to that memory's #id - even if the user said it before in RECENT CONVERSATION, because it is
   not saved until it is in KNOWN MEMORIES. Then ask: "I remembered that Rahul lives in Bangalore. Should I update it to Hyderabad?"
   Memories marked OLD are history: use them only for "before" / "used to" questions, and say clearly
   that it is no longer true and what replaced it, e.g. "Rahul used to live in Bangalore, but he has moved
   to Hyderabad now."
6. FORGETTING: if they ask you to forget something, set intent FORGET_REQUEST, put the matching #ids in
   "forget_memory_ids", and ask them to confirm ("Should I forget that Rahul lives in Bangalore?").
   Never say it is already forgotten.
7. UNSURE MEMORIES: when you use a memory marked "user was not sure", say so:
   "I think you mentioned Rahul moved around June, but you weren't sure. Would you like to confirm it?"
8. If they sound unwell, in danger or ask for help, set intent to EMERGENCY and tell them to press the
   red Help button or call a family member. Give no medical advice.

PRIVACY QUESTIONS ("who can see my information?"): answer from WHO CAN SEE THE USER'S INFORMATION, in
plain words, and reassure them that conversations and private memories are never shared. They can change
this at any time, just by telling you.

REMOVING REMINDERS: if they ask to delete, cancel or stop a reminder ("Call me dad wala reminder hata do",
"I don't need the Metformin reminder", "saare reminders delete kar do"), put the matching R# ids from
REMINDERS in "cancel_reminder_ids" ("all" = every R# id listed) and ask first, listing them briefly:
"Shall I remove these reminders?\n• Call me dad (today 6 PM)\n• Dentist (Wed 4 PM)". Never say they are
removed before the user says yes. Each REMINDERS line says who set it ("suggested by Priya" or "set by the
user"), so you can answer "who added this reminder?".

SHARING (who sees each memory). Work out a suggested "visibility" for every new memory:
- EMERGENCY: needed in an emergency - blood group, allergies, serious conditions, implants, daily medicines.
- CARE: health notes and doctor's advice ("Dr. Sharma told me to walk daily").
- SHARED_FAMILY: family news and happy events (moves, jobs, studies, weddings, births).
- PRIVATE: feelings, worries, preferences, money, complaints about people, anything personal or unclear.
If you suggest anything other than PRIVATE, you MUST say so in the same question, in plain words:
"Shall I remember that your blood group is B+, and show it to your family and doctors in an emergency?"
"...and share this news with your family?" / "...and let your family see this health note?"
If you don't mention sharing, use PRIVATE.
To change an EXISTING memory ("share with my family that Rahul moved", "keep my tea preference private",
"show my blood group in emergencies"), add an entry to "visibility_changes" with its #id and ask first.

FAMILY ACCESS: if they want someone to see (or stop seeing) their information - "let my son Rajesh see my
medicines", "my daughter should be able to check my appointments", "let Priya see everything", "don't let
Priya see my medicines any more", "stop Rajesh from seeing my information" - add an entry to
"access_changes": GRANT for someone not yet under WHO CAN SEE, UPDATE to change what someone sees, REVOKE to
remove all their access. Set only the parts they mentioned ("everything" = all true; "my health things",
"health/medical information" = medicines, appointments and emergency ONLY). Set shared_memories to true
only if they clearly mention memories, family news or "everything" - never for a doctor otherwise. If they just say "give Rajesh access", leave the parts empty and the
usual set is used (medicines, appointments, emergency contacts). Ask in plain words before anything
changes: "Shall I let Rajesh see your medicines and appointments?" NEVER give or change access unless they
clearly asked.

WHEN IT'S UNCLEAR WHO THEY MEAN: if "my son", "my daughter", "my doctor", "Rahul" etc. could be more than
one person under PEOPLE (or in KNOWN MEMORIES), do not guess. Ask which one, naming them, e.g.
"You have two sons, Rajesh and Jagdeesh. Which one would you like to hear about?" or, when they are
telling you something, "Which son moved to Pune, Rajesh or Jagdeesh?". In that case put NOTHING in
"memories", "new_people" or "reminders" yet. When their next message answers (just a name is enough),
use RECENT CONVERSATION to continue exactly where you left off. If only one person fits, just answer.

A SINGLE MESSAGE MAY MIX EVERYTHING (facts, people, phone numbers, reminders): handle every part,
putting each piece where it belongs, and ask about all of them together in one short reply.

IMPORTANT: whenever "reply" asks "Would you like me to remember...?" or "Should I update...?", the fact
MUST be in "memories". A question without a memory entry gives the user nothing to approve.

Examples of good answers:
- "What is Ananya studying?" -> answer_source MEMORY:
  "Ananya is studying Computer Engineering at NIT Kurukshetra."
- "How does Jagdeesh treat me?" -> answer_source MEMORY:
  "Jagdeesh is very kind to you. You've said he always takes care of you, which is lovely."
- "When did I tell you about Ananya's college?" -> answer_source MEMORY:
  "You told me on 22 November."
- "Where did Rahul live before?" -> answer_source MEMORY:
  "Rahul used to live in Bangalore. He moved to Hyderabad recently."
- "Did I take my Metformin today?" -> answer_source REMINDER:
  "Yes, you took your Metformin 500 mg today." (or "Not yet. It was due at 8:00 PM.")
- "What do I have tomorrow?" -> answer_source REMINDER:
  "Tomorrow, Monday 23 November, you see Dr. Sharma at 11 AM and take your Metformin at 8 PM."
- "Tell me something about my son" (two sons under PEOPLE) -> answer_source NONE:
  "You have two sons, Rajesh and Jagdeesh. Which one would you like to hear about?"
- then "Jagdeesh" -> answer_source MEMORY:
  "Jagdeesh is an engineer in Bangalore, and he's very kind to you. His birthday is on 23 December."
- "Show all my reminders" -> answer_source REMINDER:
  "Here's what's coming up:\n\nToday (Sun 22 Nov)\n• 6:00 PM – Call Priya\n\nTomorrow (Mon 23 Nov)\n• 12:47 AM – Metformin 500 mg (after food)\n• 11:00 AM – Dr. Sharma"
- "Tell me about my family" -> answer_source MEMORY:
  "Here's what you've told me:\n\nJagdeesh (son)\n• Engineer in Bangalore\n• Very kind to you\n• Birthday: 23 December\n\nAnanya (granddaughter)\n• Studies Computer Engineering at NIT Kurukshetra"
- "Where does my sister live?" (nothing known) -> answer_source NONE:
  "I don't think you've told me that yet. Would you like to tell me?"

Return ONLY a JSON object with exactly these keys, no other text:
{schema}"""


def _context(user_name: str, people: list[dict], memories: list[dict], history: list[dict],
             reminders: list[str], family_access: list[str] | None = None) -> str:
    people_lines = "\n".join(f"- {p['name']}: {p['relation'] or 'unknown relation'}" for p in people) or "(none yet)"
    memory_lines = "\n".join(
        f"- [#{m['id']}] {m['fact']} (told on {m['told_on']})"
        + (f" - OLD, replaced on {m['replaced_on']}" if m.get("replaced_on") else "")
        + (" - user was not sure" if m.get("unsure") else "")
        for m in memories) or "(none yet)"
    history_lines = "\n".join(f"{h['role']}: {h['text']}" for h in history) or "(start of conversation)"
    today = local_now().date()
    return (
        f"TODAY: {today.strftime('%A, %d %B %Y')} ({today.isoformat()})\n"
        f"USER'S NAME: {user_name}\n\nPEOPLE:\n{people_lines}\n\n"
        f"KNOWN MEMORIES:\n{memory_lines}\n\n"
        f"REMINDERS (today and the next 7 days, with what the user did):\n{chr(10).join(reminders) or '(none)'}\n\n"
        f"WHO CAN SEE THE USER'S INFORMATION (family links the user set up):\n"
        f"{chr(10).join(family_access or []) or '(nobody: everything is private)'}\n"
        f"Conversations and private memories are never shared with anyone.\n\n"
        f"RECENT CONVERSATION:\n{history_lines}\n"
    )


_TOLD_ME = re.compile(r"^\s*you told me(?:\s+on\s+.+?)?\s+that\s+|^\s*you told me[,:]?\s+", re.IGNORECASE)


def _fix_reminder_wording(result: AIResult) -> AIResult:
    """Safety net: reminders are a schedule, so never 'You told me...' for them."""
    if result.answer_source == "REMINDER" and _TOLD_ME.match(result.reply):
        rest = _TOLD_ME.sub("", result.reply, count=1)
        result.reply = rest[:1].upper() + rest[1:]
    return result


def _parse(text: str) -> AIResult:
    # Accept plain JSON, or JSON wrapped in ``` fences.
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise AIError("The AI did not return JSON.")
    try:
        result = AIResult.model_validate_json(match.group(0))
    except ValidationError as e:
        raise AIError(f"The AI's JSON didn't match the expected shape: {e.errors()[:2]}")
    if result.reminder is not None and not any(r.title == result.reminder.title for r in result.reminders):
        result.reminders.append(result.reminder)  # accept the old single field too
    result.reminder = None
    return _fix_reminder_wording(result)


def understand(message: str, *, user_name: str, language: str, people: list[dict],
               memories: list[dict], history: list[dict], reminders: list[str] | None = None,
               family_access: list[str] | None = None) -> AIResult:
    """Send one user message plus context to Gemini and get back an AIResult."""
    if not settings.gemini_api_key:
        raise AIError("GEMINI_API_KEY is missing from your .env file.")

    client = gemini_client()
    system = INSTRUCTIONS.format(
        language=LANGUAGES.get(language, "English"),
        schema=json.dumps(AIResult.model_json_schema()),
    )
    reply_language = language  # the language chosen in the user's settings, always
    prompt = _context(user_name, people, memories, history, reminders or [], family_access) + \
        f"\nUSER JUST SAID: {message}\n\n" \
        f"REPLY LANGUAGE: {LANGUAGE_NAMES.get(reply_language, 'English')}. Write \"reply\" in this language " \
        f"and script only (keep \"normalized_fact\" in English)."

    started = time.perf_counter()
    response = None
    last_error: Exception | None = None
    # Busy or rate-limited? Try again after a moment, then try the backup model.
    attempts = [(settings.gemini_model, 0), (settings.gemini_model, 1.5)]
    if settings.gemini_fallback_model and settings.gemini_fallback_model != settings.gemini_model:
        attempts.append((settings.gemini_fallback_model, 0))
    for model, wait in attempts:
        if wait:
            time.sleep(wait)
        try:
            response = client.models.generate_content(
                model=model, contents=prompt,
                config={"system_instruction": system, "response_mime_type": "application/json"})
            if model != settings.gemini_model:
                log.warning("Answered with the backup model %s", model)
            break
        except (TypeError, ValueError, ValidationError):
            # This SDK version doesn't accept those options: plain request with the instructions inline.
            try:
                response = client.models.generate_content(model=model, contents=system + "\n\n" + prompt)
                break
            except Exception as e:
                last_error = e
        except Exception as e:
            last_error = e
            if not is_temporary(e):
                break  # a bad key or unknown model won't fix itself by retrying
            log.warning("Gemini busy (%s), retrying...", short_error(e))
    if response is None:
        log.error("Gemini failed after %.1fs: %s", time.perf_counter() - started, last_error)
        raise AIError(f"Couldn't reach Gemini: {short_error(last_error)}", temporary=is_temporary(last_error))
    log.info("Gemini reply took %.1fs (prompt %d characters)", time.perf_counter() - started,
             len(system) + len(prompt))

    result = _parse(response.text)
    # Safety net: the reply must be in the chosen language and script.
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", result.reply))
    if (reply_language == "hi" and not has_devanagari) or (reply_language in ("en", "hinglish") and has_devanagari):
        result.reply = translate(result.reply, reply_language)
    return result


LANGUAGE_NAMES = {"en": "English", "hi": "Hindi (Devanagari script)",
                  "hinglish": "Hinglish (Hindi written in English letters, the way people text)"}


def translate(text: str, language: str) -> str:
    """Short, warm translation into the chosen language. Returns the original if anything goes wrong."""
    if not language or not text or not settings.gemini_api_key:
        return text
    try:
        response = gemini_client().models.generate_content(
            model=settings.gemini_model,
            contents=(f"Translate this message for an elderly person into {LANGUAGE_NAMES.get(language, language)}. "
                      f"Keep names, numbers, dates and times exactly. Reply with the translation only.\n\n{text}"))
        out = (response.text or "").strip()
        return out or text
    except Exception as e:
        log.warning("Translation failed, sending English: %s", short_error(e))
        return text


_HINGLISH = {"hai", "hain", "h", "mera", "meri", "mere", "mujhe", "mein", "me", "kya", "kahan", "kab", "kaun",
             "kaise", "kaisa", "kaisi", "kitna", "kitne", "nahi", "nahin", "nhi", "haan", "ha", "beta", "beti",
             "aur", "tha", "thi", "the", "kal", "aaj", "ko", "se", "ki", "ka", "ke", "baare", "bare", "liye", "lie",
             "batao", "bataiye", "bata", "bta", "bolo", "boliye", "rehta", "rehti", "rehte", "dawai", "dawa", "yaad",
             "dilana", "karna", "karo", "kar", "do", "hoon", "hu", "aap", "aapko", "tum", "acha", "accha", "achha",
             "sab", "theek", "thik", "sahi", "bhi", "abhi", "wala", "wali", "ji", "bhai", "didi", "papa", "mummy",
             "nana", "nani", "dada", "dadi", "pota", "poti", "chahiye", "lena", "khana", "woh", "wo", "yeh", "ye",
             "kuch", "uska", "uski", "uske", "unka", "unki", "unke", "iska", "iski", "apna", "apni", "kab", "kidhar",
             "idhar", "udhar", "jab", "tab", "phir", "fir", "toh", "to", "par", "pe", "wahan", "yahan", "naam"}
# "the" is also Hindi ("they were"), so it doesn't count as English below.
_ENGLISH = {"is", "are", "was", "were", "what", "where", "who", "when", "how", "why", "which", "my", "i", "you",
            "your", "about", "does", "did", "tell", "please", "can", "could", "would", "with", "and", "of", "in",
            "have", "has", "will", "show", "all", "remind", "remember", "take", "today", "tomorrow", "lives",
            "live", "works", "son", "daughter", "doctor", "medicine", "know", "this", "that", "it", "a", "an"}


def detect_language(message: str, fallback: str = "en") -> str:
    """Which language to reply in: Hindi (Devanagari), Hinglish or English.
    Script first; then whichever kind of common words is more frequent; if unclear, the fallback
    (the language of the conversation so far)."""
    if re.search(r"[\u0900-\u097F]", message):
        return "hi"
    words = re.findall(r"[a-z]+", message.lower())
    hinglish = sum(1 for w in words if w in _HINGLISH)
    english = sum(1 for w in words if w in _ENGLISH and w not in _HINGLISH)
    if hinglish > english and hinglish >= 1:
        return "hinglish"
    if english > hinglish:
        return "en"
    return fallback  # "Priya?", "Ravi", "8 PM": keep the conversation's language
