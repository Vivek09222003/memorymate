# MemoryMate: Project context for a new AI session

> **For the AI reading this:** this file brings you up to speed on the project. Read it fully before suggesting changes. Then read the files you need in `backend/app/`. The code is the source of truth if it disagrees with this file.

## About the developer
- Akash, a 3rd-semester student working on Windows in VS Code (PowerShell terminal), timezone IST (Asia/Kolkata).
- Project folder: `C:\Users\akash_s6h7xpa\Desktop\Project_3rd sem\memorymate-step1\memorymate-app`
- GitHub: private repo `Vivek09222003/memorymate`. Friends are added as collaborators.

**How to work with him:**
- Keep things **simple**. He said "don't make it complex".
- Explain in plain English. He often writes in **Hinglish**, so reply in Hinglish or simple English when he does.
- Go step by step and give exact commands. He tests in the browser at `/test` and sometimes uses Swagger at `/docs`.
- When editing code, give complete, working changes and tell him whether to restart the server.

## What MemoryMate is
A voice-first, conversational AI memory companion for elderly people.
- It remembers people, facts and feelings.
- It sets smart reminders.
- It lets family members and doctors see only what the elder allows.
- It works in English, Hindi and Hinglish.

## Tech stack
- **Language and API:** Python 3.14, FastAPI, Uvicorn (`--reload`), Pydantic v2, pydantic-settings (`.env`).
- **Database:** SQLAlchemy 2 ORM, PostgreSQL 16 with **pgvector**, running in Docker Compose (image `pgvector/pgvector:pg16`, user/password/db all `memorymate`, port 5432). Driver: psycopg3.
- **Auth:** PyJWT and bcrypt, using the OAuth2 password flow (`/auth/login`).
- **AI:** Google Gemini through `google-genai`.
  - Chat model `gemini-3.5-flash-lite`, with backup model `gemini-3.6-flash`.
  - Embeddings: `gemini-embedding-001` at **1024 dimensions** (normalized; task types RETRIEVAL_DOCUMENT and RETRIEVAL_QUERY).
  - The AI returns JSON, validated by the Pydantic `AIResult` model.
  - One shared client with a timeout. Retries on 503/429, then falls back to the backup model, then shows a friendly "busy" message.
- **Database changes:** no Alembic yet. `database.init_db()` runs `create_all` plus a list of `ALTER TABLE ... IF NOT EXISTS` upgrades.
- **Test UI:** one HTML page served at `/test` (`routers/testpage.py`).

## Running it
```powershell
docker compose up -d                 # from the project root
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
# http://localhost:8000/test   and   http://localhost:8000/docs
```
`backend/.env` holds `GEMINI_API_KEY` and `JWT_SECRET`. **Never commit it, print it, or ask for it to be pasted in chat.** Use `.env.example` as the template. `.env` is not hot-reloaded, so the server must be restarted after editing it.

## Code map (`backend/app/`)

**Core modules**
- `config.py`: settings: `gemini_model`, `gemini_fallback_model`, `embedding_dim=1024`, `missed_after_minutes=60`, `ai_timeout_seconds=25`, `timezone="Asia/Kolkata"`.
- `database.py`: engine, sessions, `init_db()` with the upgrades list.
- `models.py`:
  - **Enums:** UserRole (ELDER / FAMILY / DOCTOR) and `HELPER_ROLES = (FAMILY, DOCTOR)`. Also PersonType, MemoryType, MemoryStatus, Visibility, ReminderKind, Repeat, ReminderStatus, OccurrenceStatus, LinkStatus.
  - **Tables:** User, Person, Relationship, Message, Memory, Reminder, ReminderOccurrence, FamilyLink, AccessLog, ChatState.
  - Memory has two foreign keys to users (`owner_id`, `suggested_by_id`), so the relationships use `foreign_keys=` to avoid AmbiguousForeignKeysError.
- `security.py`: password hashing, JWT, `get_current_user`.
- `timeutil.py`: `local_now()`, `local_dt()`, `show()` (formats like "Mon 23 Nov, 11:00 AM").

**AI and search**
- `ai.py`: the big `INSTRUCTIONS` prompt and the `understand()` function.
  - **Response models:** MemoryCandidate, NewPerson, VisibilityChange, AccessChange, ReminderSuggestion, AIResult.
  - **Prompt rules:** warm tone; never invent details; don't mention dates unless asked; "show all" answers as "• " lists; ask "which one?" when unclear; one message can mix several things.
  - **Language:** the reply language is always the dropdown language (en / hi / hinglish). `translate()` is a safety net that checks for the Devanagari script.
- `embeddings.py`: `embed()` and `memory_text()`.
- `retrieval.py`: looks up people first, then runs a pgvector cosine search with a cut-off (`CLOSE_TO_BEST=0.10`).

**Reminders, confirmations and access**
- `reminders.py`:
  - Computes the next due time and plans alerts. Appointments get an alert 60 minutes before plus one the evening before.
  - A background `tick` runs every 30 seconds and marks DUE, then MISSED after `missed_after_minutes`.
  - `run_forever` is started in the `main.py` lifespan.
- `confirmations.py`: plain yes/no detection (English, Hindi and Hinglish, e.g. haan, nhi, "sab acha", "rehne do").
  - Ignores messages containing "?", messages longer than 6 words, and messages with extra non-filler words.
  - `ChatState` stores what was asked, so `apply()` can save people, memories, reminders, access changes and so on without calling the AI.
- `family_access.py`:
  - **Scopes:** medicines / appointments / emergency / shared_memories / suggest_reminders.
  - **Defaults:** `DEFAULTS`, and `DOCTOR_DEFAULTS`, which never include shared memories unless explicitly asked.
  - **Functions:** `is_doctor()`, 8-character invite codes, and `grant` / `update` / `revoke` / `join`.

**Routers (`routers/`)**
- `auth.py`: register (optional `invite_code`), login, `GET /me`, `PATCH /me` (name, preferred_language).
- `people.py`: people CRUD, search, emergency contacts, relationships.
- `chat.py`: the main flow:
  1. Run the yes/no shortcut.
  2. Otherwise build context: retrieved memories, reminders (including SUGGESTED ones with "suggested by X"), and who has access.
  3. Call the AI.
  4. Remove duplicates of things already known.
  5. Store pending questions in ChatState.
- `memories.py`: list, search, `/from-others` (notes from doctors/family waiting for approval), approve, reject, visibility, forget, reindex.
- `reminders.py`: create, `/suggestions` (accept/decline; accept works up to 12 hours late), due, today, done, snooze, cancel, check-now.
- `family.py`:
  - **Elder side:** links, invites, revoke, access log.
  - **Helper side:** join with a code, `my-elders`, dashboard, suggesting reminders, adding health notes (these become PENDING CARE memories).
  - **Dashboard sections:** medicines today, missed count, upcoming appointments and tasks, health notes, shared memories, emergency contacts, hidden sections.
- `testpage.py`: the `/test` HTML page.
  - Login, plus sign-up for elders and for family/doctors with a code.
  - Language dropdown, chat with Yes/No buttons, notes and suggestions panels.
  - Silent desktop pop-ups, driven by a worker-based 20-second ticker.
  - The helper dashboard has a Relative/Patient dropdown and refreshes every 60 seconds.

## Key design decisions (keep these)
1. **Nothing is saved without asking.** The AI proposes, the user says yes or no, then `apply()` saves.
2. **Memory lifecycle:** PENDING → ACTIVE → HISTORICAL (replaced) / DELETED. Uses `replaces_id`, `valid_from`/`valid_to` and confidence.
3. **Visibility:** PRIVATE / SHARED_FAMILY / CARE / EMERGENCY. Memories stay private unless the user mentions sharing; code enforces this with `SHARE_WORDS`.
4. **Doctors and family sign up the same way.** Both use role FAMILY at sign-up with a code. If the elder's Person entry is a doctor, the doctor defaults apply.
5. **One helper can have many elders, and one elder many helpers.** The dashboard has a dropdown to pick the person.
6. **The reply language is forced by the dropdown**, whatever language the user types in.
7. **No invented details** in AI replies, and no "You told me on <date>" phrasing.

## Done so far (backend about 80%)
Auth, people, chat with memory and RAG, the confirmation flow, reminders with a background job and pop-ups, family and doctor accounts with scopes and invite codes, suggestions and health notes, three languages, the test page, and the README setup manual.

## Still to do (in suggested order)
1. **Emergency mode.** The elder says "help" or presses a button, and emergency contacts and family see an alert.
2. **Missed-medicine alerts to family** (MISSED occurrence → notify linked family).
3. Optional: an "overview" screen for doctors/family listing all their patients/elders with alerts.
4. **pytest tests** for the main flows.
5. **Alembic migrations** to replace the ALTER-TABLE list.
6. **Push notifications** (Firebase) and later a mobile/frontend app.

## Lessons learned / gotchas
- **401 from Gemini:** the key must be an `AIza…` key from AI Studio, with no quotes or `#`. Restart the server after changing `.env`.
- **503/429** means Gemini is busy. Retries and the backup model already handle it.
- **Pydantic:** don't name a field `date` and also use the type `date`. Use `dt.date`.
- **Stale code after edits:** restart uvicorn and hard-refresh with `Ctrl+Shift+R`.
- **Background tabs delay timers:** that's why the ticker runs in a worker. Chrome Memory Saver can still delay it.
- **Testing missed reminders:** `MISSED_AFTER_MINUTES=2` for quick testing; set it back to 60 afterwards.
