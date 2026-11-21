# MemoryMate

An AI personal memory companion for elderly users. This is **Step 1: the project foundation.**

## What you need installed (once)

- **Python 3.11 or newer**: https://www.python.org/downloads/ (on Windows, tick "Add Python to PATH")
- **Docker Desktop**: https://www.docker.com/products/docker-desktop/ (keep it running)
- **VS Code**. When you open this folder it suggests the Python and Docker extensions; click **Install**.

## Run it in VS Code

1. **File → Open Folder…** and choose this `memorymate-app` folder.
2. Open a terminal: **Terminal → New Terminal**.
3. Start the database:
   ```
   docker compose up -d
   ```
4. Go into the backend folder and create a virtual environment:
   ```
   cd backend
   python -m venv .venv
   ```
5. Activate it:
   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
     (If you get a "scripts disabled" error, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.)
   - Mac / Linux: `source .venv/bin/activate`
6. Tell VS Code to use it: press **Ctrl+Shift+P** (Cmd+Shift+P on Mac) → **Python: Select Interpreter** → pick the one in `backend/.venv`.
7. Install the packages:
   ```
   pip install -r requirements.txt
   ```
8. Create your settings file by copying `.env.example` to `.env`:
   - Windows: `copy .env.example .env`
   - Mac / Linux: `cp .env.example .env`
9. Start the API:
   ```
   uvicorn app.main:app --reload
   ```
   Or press **F5** in VS Code and choose **MemoryMate API** to run it with the debugger.
10. Open http://localhost:8000/docs in your browser. Click **GET /health → Try it out → Execute**.

You should see something like:
```json
{
  "status": "ok",
  "database": "connected",
  "pgvector": true,
  "tables": ["memories", "messages", "people", "relationships", "users"]
}
```

## Project layout

```
memorymate-app/
├── docker-compose.yml     PostgreSQL + pgvector
├── backend/
│   ├── requirements.txt   Python packages
│   ├── .env.example       settings template (copy to .env)
│   └── app/
│       ├── main.py        FastAPI app and the /health endpoint
│       ├── config.py      reads settings from .env
│       ├── database.py    database connection; creates tables on startup
│       └── models.py      tables: users, people, relationships, messages, memories
└── .vscode/               run/debug setup and recommended extensions
```

## If something goes wrong

- **"connection refused" on /health**: Docker Desktop isn't running, or the database is still starting. Run `docker compose ps` and wait until it says `healthy`.
- **Port 5432 already in use**: another PostgreSQL is installed on your computer. Stop it, or change `"5432:5432"` to `"5433:5432"` in docker-compose.yml and `5432` to `5433` in `.env`.
- **`uvicorn` not found**: the virtual environment isn't active. Repeat step 5.

## Coming next

- Step 2: login (JWT) and adding people
- Step 3: AI chat that pulls out facts as structured JSON
- Step 4: memory approval and vector search
