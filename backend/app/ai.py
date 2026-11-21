"""Talking to Gemini.

The AI never writes to the database itself. It returns structured JSON
(an AIResult), and our code decides what to store, always as PENDING
until the user says yes.
"""
import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.timeutil import local_now


# ---------- what we ask the AI to return ----------
class MemoryCandidate(BaseModel):
    memory_type: Literal["PERSONAL_FACT", "PREFERENCE", "EVENT", "HEALTH", "ROUTINE"]
    person_name: str | None = Field(None, description="Who the fact is about, if anyone other than the user")
    relationship: str | None = Field(None, description="That person's relation to the user, e.g. granddaughter")
    attribute: str | None = Field(None, description="Short label, e.g. education, city, job, birthday, likes")
    value: str | None = Field(None, description="The value, e.g. Computer Engineering, Bangalore")
    normalized_fact: str = Field(description="One short English sentence about the user, e.g. 'Ananya (granddaughter) studies Computer Engineering at NIT Kurukshetra.'")
    event_date: str | None = Field(None, description="YYYY-MM-DD if the fact has a date")
    confidence: float = Field(1.0, ge=0, le=1, description="Lower when the user sounds unsure ('I think', 'around')")
    replaces_memory_id: int | None = Field(
        None, description="The #id of a KNOWN MEMORY this new fact updates or contradicts (e.g. a new city)")


class NewPerson(BaseModel):
    name: str
    relationship: str | None = None


class ReminderSuggestion(BaseModel):
    title: str
    kind: Literal["MEDICINE", "APPOINTMENT", "BIRTHDAY", "CALL", "TASK"]
    date: str | None = Field(None, description="YYYY-MM-DD")
    time: str | None = Field(None, description="HH:MM, 24-hour")


class AIResult(BaseModel):
    intent: Literal["SHARE_INFORMATION", "QUESTION", "REMINDER_REQUEST", "FORGET_REQUEST", "SMALL_TALK", "EMERGENCY"]
    answer_source: Literal["MEMORY", "REMINDER", "NONE"] = Field(
        "NONE", description="For questions: MEMORY if answered from KNOWN MEMORIES, REMINDER if from REMINDERS")
    reply: str
    memories: list[MemoryCandidate] = []
    new_people: list[NewPerson] = []
    reminder: ReminderSuggestion | None = None
    forget_memory_ids: list[int] = Field(
        [], description="#ids of KNOWN MEMORIES the user asked you to forget")


class AIError(Exception):
    """Raised when the AI can't be reached or returns something unusable."""


LANGUAGES = {"en": "English", "hi": "Hindi (Devanagari script)", "te": "Telugu (Telugu script)"}

INSTRUCTIONS = """You are MemoryMate, a warm, patient memory companion for an elderly person.
Reply in {language}. Use short, simple sentences (at most three).

Your job each turn:
1. If the user shares a lasting fact about their life (people, relationships, preferences,
   events, health notes, routines), add one entry to "memories" per fact, and in "reply" ASK whether
   they want you to remember it ("Would you like me to remember that ...?"). Never say it is saved.
   Skip facts already listed under KNOWN MEMORIES. If they sound unsure, lower "confidence".
   A new memory may contain ONLY what the user said in this message. Never copy details from other
   memories into it (if they say "Rahul moved to Hyderabad", do not add "for his new job").
2. If they mention someone not listed under PEOPLE, add them to "new_people".
3. If they ask a question, answer ONLY from KNOWN MEMORIES, PEOPLE and REMINDERS
   (e.g. "Did I take my 8 PM medicine?" or "What do I have tomorrow?").
   For KNOWN MEMORIES, say when they told you, in this form: "You told me on 21 November that ...".
   For REMINDERS, just state them plainly with day and time (e.g. "Tomorrow, Monday 23 November, you have
   your Metformin at 12:50 AM and Dr. Sharma at 11 AM."), and for medicines say whether it was taken.
   NEVER start a reminder answer with "You told me": reminders are a schedule, not something they told you.
   Good: "Yes, you took your Metformin 500 mg today." Bad: "You told me on 22 November that you took...". The "told on" date is when they told you, NOT when the
   event happened, so never use it as the event's date. If the answer isn't there, say kindly that you
   don't know yet and that they can tell you. Never guess.
4. If they mention a NEW appointment, medicine, birthday, call or task in the future (not already
   under REMINDERS), fill "reminder"
   and ask in "reply" whether they would like a reminder. Turn words like "tomorrow" or "on Monday" into
   a date, counting from TODAY. For "Monday" or "next Monday", use the nearest Monday after today.
   Always say the exact weekday and date in "reply" (e.g. "Monday, 23 November at 11 AM") so they can
   correct you if you got it wrong.
5. CORRECTIONS: if a new fact updates or contradicts a KNOWN MEMORY (e.g. a person moved to a new city,
   changed job, a new phone number), you MUST add the new fact to "memories" with "replaces_memory_id"
   set to that memory's #id - even if the user said it before in RECENT CONVERSATION, because it is
   not saved until it is in KNOWN MEMORIES. Then ask: "I remembered that Rahul lives in Bangalore. Should I update it to Hyderabad?"
   Memories marked OLD are history: use them only for "before" / "used to" questions, and say clearly
   that it is no longer true and what replaced it, e.g. "Rahul used to live in Bangalore. On 22 November
   you told me he moved to Hyderabad."
6. FORGETTING: if they ask you to forget something, set intent FORGET_REQUEST, put the matching #ids in
   "forget_memory_ids", and ask them to confirm ("Should I forget that Rahul lives in Bangalore?").
   Never say it is already forgotten.
7. UNSURE MEMORIES: when you use a memory marked "user was not sure", say so:
   "I think you mentioned Rahul moved around June, but you weren't sure. Would you like to confirm it?"
8. If they sound unwell, in danger or ask for help, set intent to EMERGENCY and tell them to press the
   red Help button or call a family member. Give no medical advice.

IMPORTANT: whenever "reply" asks "Would you like me to remember...?" or "Should I update...?", the fact
MUST be in "memories". A question without a memory entry gives the user nothing to approve.

Examples of good answers:
- "What is Ananya studying?" -> answer_source MEMORY:
  "You told me on 22 November that Ananya is studying Computer Engineering at NIT Kurukshetra."
- "Did I take my Metformin today?" -> answer_source REMINDER:
  "Yes, you took your Metformin 500 mg today." (or "Not yet. It was due at 8:00 PM.")
- "What do I have tomorrow?" -> answer_source REMINDER:
  "Tomorrow, Monday 23 November, you see Dr. Sharma at 11 AM and take your Metformin at 8 PM."

Return ONLY a JSON object with exactly these keys, no other text:
{schema}"""


def _context(user_name: str, people: list[dict], memories: list[dict], history: list[dict],
             reminders: list[str]) -> str:
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
        return _fix_reminder_wording(AIResult.model_validate_json(match.group(0)))
    except ValidationError as e:
        raise AIError(f"The AI's JSON didn't match the expected shape: {e.errors()[:2]}")


def understand(message: str, *, user_name: str, language: str, people: list[dict],
               memories: list[dict], history: list[dict], reminders: list[str] | None = None) -> AIResult:
    """Send one user message plus context to Gemini and get back an AIResult."""
    if not settings.gemini_api_key:
        raise AIError("GEMINI_API_KEY is missing from your .env file.")

    from google import genai  # imported here so the rest of the app runs without the key

    client = genai.Client(api_key=settings.gemini_api_key)
    system = INSTRUCTIONS.format(
        language=LANGUAGES.get(language, "English"),
        schema=json.dumps(AIResult.model_json_schema()),
    )
    prompt = _context(user_name, people, memories, history, reminders or []) + f"\nUSER JUST SAID: {message}"

    try:
        # Ask for JSON directly (supported by most Gemini models and SDK versions).
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"system_instruction": system, "response_mime_type": "application/json"},
        )
    except Exception:
        # Fallback: plain request with the instructions in the prompt. If this fails too,
        # the problem is the key, the model name, the quota or the network.
        try:
            response = client.models.generate_content(model=settings.gemini_model, contents=system + "\n\n" + prompt)
        except Exception as e:
            raise AIError(f"Couldn't reach Gemini: {e}")

    return _parse(response.text)
