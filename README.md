# MemoryMate

An AI memory companion for elderly people. You talk to it in plain English, Hindi or Hinglish. It remembers people, facts and feelings, sets reminders for medicines, appointments and birthdays, and lets family members and doctors see only what the elder allows.

**Live version:** https://memorymate-grie.onrender.com/test (test page) · https://memorymate-grie.onrender.com/docs (API). The free server sleeps when idle, so the first visit can take about a minute.

This manual takes you from a fresh Windows laptop to MemoryMate running in your browser and on your phone. Expect about 30–45 minutes the first time, mostly spent on downloads.

**Already set up? Start everything with one command:** open Docker Desktop, then run `.\start.ps1` in the `memorymate-app` folder (see [Part 4](#part-4-every-day-after-the-first-time)).

---

## What's inside

| Feature | What it does |
|---|---|
| Chat with memory | "My son Rajesh lives in Bangalore, his number is 98xxxxxx". MemoryMate asks before saving anything, then remembers it. |
| People | Works out family, friends, doctors and emergency contacts from normal sentences. |
| Smart reminders | Medicines (daily or weekly), appointments (it reminds you an hour before and the evening before), birthdays (yearly), calls and tasks. Shows desktop pop-ups. |
| Family and doctor accounts | The elder gives access from chat ("let my daughter Priya see my medicines") and gets a code. The family member or doctor signs up with that code. |
| Privacy | Every memory is Private, Shared with family, Care (doctor) or Emergency. Doctors see medical information only, by default. |
| Suggestions | Family and doctors can suggest reminders and health notes. The elder accepts or declines. |
| Languages | English, हिन्दी and Hinglish. The dropdown at the top picks the reply language. |
| Emergency help | A Help button (or "help", "bachao", "I fell" in chat) alerts family and doctors at once, even if the AI is down, with call buttons and 108. |
| Missed-medicine alerts | If a dose isn't marked taken within an hour, family who may see medicines are told. |
| Overview for family and doctors | Everyone you look after on one screen, most urgent first. |
| Mobile app | An Expo (React Native) app for elders, family and doctors. Reminders ring from the phone itself, even when the app is closed. |

**Tech stack:**
- Backend: Python, FastAPI and SQLAlchemy
- Database: PostgreSQL with pgvector (Docker on your laptop, Neon online)
- AI: Google Gemini for chat and embeddings
- Mobile app: React Native with Expo (in `mobile/`)
- Test UI: one HTML page at `/test`
- Hosting: Render (backend) + Neon (database)
- Tests: pytest (backend) and Jest (mobile)

---

## Part 1: Install the tools (one time only)

Install these in order. Restart the laptop after Docker.

### 1. Git
Downloads the code from GitHub.
- Download: https://git-scm.com/downloads/win
- Run the installer and keep all the default options.
- Check it worked. Open **PowerShell** (Start menu → type "PowerShell") and run:
  ```powershell
  git --version
  ```
  You should see something like `git version 2.x`.

### 2. Python (3.12 or newer)
Runs the backend.
- Download: https://www.python.org/downloads/
- **IMPORTANT:** on the first installer screen, tick **"Add python.exe to PATH"**, then click *Install Now*.
- Check it worked. Close and reopen PowerShell, then run:
  ```powershell
  python --version
  ```
  You should see `Python 3.12.x` or newer. If you get *"python is not recognized"*, run the installer again and tick the PATH box.

### 3. Docker Desktop
Runs the database, so you don't have to install PostgreSQL yourself.
- Docker on Windows needs WSL 2. Open PowerShell **as Administrator** (right-click → *Run as administrator*) and run:
  ```powershell
  wsl --install
  ```
  Restart the laptop when it finishes. If it says WSL is already installed, that's fine.
- Download Docker Desktop: https://www.docker.com/products/docker-desktop/
- Install it with the default options (keep **"Use WSL 2"** ticked), then **restart** the laptop.
- Open **Docker Desktop** from the Start menu. Accept the terms; you can skip sign-in. Wait until the bottom-left corner shows **"Engine running"** (green).
- Check it worked:
  ```powershell
  docker --version
  docker compose version
  ```

> If Docker says *"virtualization is not enabled"*, turn on **Virtualization (VT-x / AMD-V / SVM)** in your laptop's BIOS settings. Search "enable virtualization" plus your laptop brand for the exact steps.

### 4. VS Code (recommended editor)
- Download: https://code.visualstudio.com/
- After installing, open VS Code → Extensions (`Ctrl+Shift+X`) → install **Python** (by Microsoft).

### 5. A Google Gemini API key (free)
The AI part. **Everyone uses their own key. Never share yours.**
1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Click **Create API key** and copy it. It starts with `AIza...`.
3. Keep it somewhere safe. You'll paste it in Part 2, Step 5.

---

## Part 2: Get MemoryMate running (first time)

All commands go in a terminal. In VS Code, open one with **Terminal → New Terminal** (it's PowerShell on Windows).

### Step 1: Accept the GitHub invite
If the repo is private, the owner must add you as a collaborator first. Open the invitation email from GitHub (or go to https://github.com/notifications) and click **Accept**.

### Step 2: Download the code
Pick a folder, for example your Desktop:
```powershell
cd $HOME\Desktop
git clone https://github.com/<owner-username>/memorymate.git
cd memorymate
```
Replace `<owner-username>` with the repo owner's GitHub username. For a private repo, a browser window opens the first time and asks you to sign in to GitHub. Sign in and come back.

Then open the folder in VS Code:
```powershell
code .
```

### Step 3: Start the database
Make sure **Docker Desktop is open** and shows *Engine running*. Then, in the `memorymate` folder:
```powershell
docker compose up -d
```
The first run downloads the database image (about 150 MB). Check it's running:
```powershell
docker ps
```
You should see a container named **memorymate-db** with status `Up ... (healthy)`.

### Step 4: Set up Python
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
Your prompt should now start with **(.venv)**.

> **Error "running scripts is disabled on this system"?** Run this once, then try `Activate.ps1` again:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

Install the packages:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

In VS Code, press `Ctrl+Shift+P` → **Python: Select Interpreter** → choose the one with `.venv` in it.

### Step 5: Create your `.env` file (settings and secrets)
```powershell
Copy-Item .env.example .env
code .env
```
In the `.env` file that opens, change two lines:
```
GEMINI_API_KEY=AIzaSy...your-own-key...
JWT_SECRET=any-long-random-text-you-like-1234567890
```
- No quotes, no spaces around `=`, and no `#` in front.
- Save the file (`Ctrl+S`).
- **Never commit or share `.env`.** It's already listed in `.gitignore`, so Git ignores it.

### Step 6: Start the server
Still inside `backend`, with `(.venv)` showing:
```powershell
uvicorn app.main:app --reload
```
When it's ready, you'll see:
```
Uvicorn running on http://127.0.0.1:8000
Application startup complete.
```
Leave this terminal open. The server stops when you close it.

### Step 7: Open it in the browser

| Link | What it is |
|---|---|
| http://localhost:8000/test | **The app.** Chat, reminders and the family/doctor dashboard. Start here. |
| http://localhost:8000/docs | Swagger page with every API endpoint, for testing and debugging. |

---

## Part 3: Try it out

1. **Create an elder account.** On http://localhost:8000/test, choose *Sign up as elder*, pick a language, and sign up.
2. Click **Turn on desktop alerts** and allow notifications, so reminders pop up.
3. **Chat**, for example:
   - `My son Rajesh lives in Bangalore and his number is 9876543210` → reply **Yes** to save it.
   - `Remind me to take BP medicine every day at 9 pm`
   - `Doctor Satish appointment on Friday at 11 am`
   - `Show all reminders` / `What do you know about Rajesh?`
4. **Give a family member access.** Type `Let my daughter Priya see my medicines and appointments` and reply **Yes**. MemoryMate shows an **8-letter code**.
5. **Sign in as the family member.** Open the same link in another browser, or an Incognito window (`Ctrl+Shift+N`). Choose *Sign up as family / doctor*, enter the code, and Priya's dashboard opens.
6. **Doctor:** the same as family. Type `Give Dr. Satish access` in the elder's chat and use that code. Doctors only see medicines, appointments and health notes by default.

> **Quick reminder testing:** set `MISSED_AFTER_MINUTES=2` in `.env` and restart the server, so missed reminders show up fast. **Set it back to 60** when you're done.

---

## Part 4: Every day after the first time

**The easy way:** open Docker Desktop, wait for *Engine running*, then in the `memorymate-app` folder:
```powershell
.\start.ps1
```
It starts the database and opens two windows: the backend (on port 8000, reachable from your phone) and the mobile app server (Expo). Close those two windows to stop.

**Or by hand:**
```powershell
# 1. Open Docker Desktop and wait for "Engine running"
# 2. In a terminal, in the memorymate folder:
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
# 3. Open http://localhost:8000/test
```

**To stop:**
```powershell
# In the server terminal press Ctrl+C, then:
cd ..
docker compose down      # stops the database (your data is kept)
```

**To get your friends' latest changes:**
```powershell
git pull
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # in case new packages were added
cd ..\mobile
npm install                       # in case the app got new packages
```

**To send your changes to GitHub:**
```powershell
git add .
git commit -m "Short description of what you changed"
git push
```
Run `git pull` before you start working, so you don't overwrite each other's work.

---

## Part 5: The mobile app (on your phone)

The app is in the `mobile/` folder. During development, your phone runs it inside the free **Expo Go** app.
Full step-by-step guide: `docs/MemoryMate_Mobile_App_Setup.pdf`.

**One time:**
1. Install **Node.js LTS** (22.13 or newer) from https://nodejs.org, then reopen VS Code. Check with `node -v`.
2. Install the app's packages:
   ```powershell
   cd mobile
   npm install
   ```
3. On your phone, install **Expo Go** (App Store / Play Store) and sign up (free).
4. On the laptop, log in with the same Expo account:
   ```powershell
   npx expo login
   ```

**Every time:**
1. Laptop and phone on the **same Wi-Fi** (or both on your phone hotspot).
2. Run `.\start.ps1` (Part 4), or by hand: backend with `uvicorn app.main:app --reload --host 0.0.0.0`, and in `mobile`: `npx expo start`.
3. In Expo Go, tap **MemoryMate** (or scan the QR code). The server address fills itself in.
4. Log in, or choose **Create account** and pick who it's for (me / a family member / a doctor).

**Use the online server instead of your laptop:** create `mobile\.env` with
```
EXPO_PUBLIC_SERVER_URL=https://memorymate-grie.onrender.com
```
and restart with `npx expo start --clear`. (This file is not uploaded to GitHub; delete it to use your laptop again.)

**Installable Android app (APK):** needs an Expo account and `npm install -g eas-cli`, then in `mobile`:
```powershell
eas login
eas build -p android --profile preview
```
Expo builds it online (10–30 minutes) and gives a download link. Open it on any Android phone to install. The APK uses the online server, so it works without the laptop.

---

## Automatic tests (pytest)

The tests check login, the chat's "ask before saving" flow, emergency mode, family permissions, reminders and memory search.
They use a separate **test database** (`memorymate_test`), created automatically, so your real data is never touched.
They also use a **fake AI**, so they need no Gemini key and run in a few seconds.

```powershell
# once: install the test tools (venv active, in the backend folder)
pip install -r requirements-dev.txt

# every time: Docker running, in the backend folder
pytest
```
You should see something like `88 passed`. If a test fails, pytest shows which one and why.

**Mobile app tests (Jest):** they check the app's own logic: the server address, login and errors, and the phone alarms.
```powershell
# once, in the mobile folder (needs internet)
npx expo install jest-expo jest -- --save-dev
# every time
npm test
```

---

## Online version (Render + Neon)

MemoryMate's backend runs online at **https://memorymate-grie.onrender.com**, with the database on **Neon**.

- **Updating it:** just `git push` to `main`. Render rebuilds and restarts automatically (a few minutes). Settings are in `render.yaml`.
- **Secrets** are set in the Render dashboard (Environment), never in GitHub: `DATABASE_URL` (Neon, non-pooled connection string), `GEMINI_API_KEY`, and `JWT_SECRET` (generated by Render).
- **Free plan limits:** the server sleeps after 15 minutes without visitors (the first request then takes about a minute), and the database has 1 GB.
- **Setting it up from scratch:** create a Neon project (Singapore region) and copy its connection string with pooling turned off. Then in Render choose **New → Blueprint**, pick this repo, and paste `DATABASE_URL` and `GEMINI_API_KEY` when asked.
- **Copy your laptop data online (optional, before the first deploy):**
  ```powershell
  docker compose exec db sh -c "pg_dump -U memorymate --no-owner --no-acl memorymate | psql 'NEON-CONNECTION-STRING'"
  ```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python is not recognized` | Reinstall Python with **"Add python.exe to PATH"** ticked, then reopen the terminal. |
| `running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `docker: error during connect` / `cannot find the file specified` | Docker Desktop isn't running. Open it and wait for *Engine running*. |
| `port 5432 is already allocated` | Another PostgreSQL is using that port. Stop it (Windows Services → postgresql → Stop), or change `"5432:5432"` to `"5433:5432"` in `docker-compose.yml` and `localhost:5432` to `localhost:5433` in `.env`. |
| `connection refused` on startup | The database isn't up. Run `docker compose up -d` and check `docker ps`. |
| AI reply: **401 / API key not valid** | Check `GEMINI_API_KEY` in `.env` (it should start with `AIza`, with no quotes and no `#`), then **restart** the server. The `.env` file isn't reloaded automatically. |
| AI reply: **"busy, try again"** (503 / 429) | Google's servers are busy or you hit the free limit. Wait a minute and try again. |
| `ModuleNotFoundError` | The venv isn't active (no `(.venv)` in the prompt). Run `.\.venv\Scripts\Activate.ps1` and then `pip install -r requirements.txt`. |
| Changes don't show in the browser | Restart the server (`Ctrl+C`, then run `uvicorn` again) and hard-refresh with `Ctrl+Shift+R`. |
| Pop-ups are late when the tab is in the background | In Chrome, Settings → Performance → turn off **Memory Saver** for localhost, or keep the tab open. |
| Want a fresh, empty database | `docker compose down -v` deletes **all** data, then run `docker compose up -d`. |
| `ECONNRESET` during `npm` / `npx` | Your network blocks npm. Switch the laptop to a phone hotspot and try again. |
| Expo Go: "signed in to Expo Go … but not signed in to Expo CLI" | Run `npx expo login` with the same account as Expo Go. |
| App: "Unable to resolve module …" | In `mobile`: `npm install`, then `npx expo start --clear`. |
| App: "Can't reach MemoryMate" | The backend must run with `--host 0.0.0.0`, phone and laptop on the same Wi-Fi, and the Windows Firewall must allow Python on private networks. Test `http://YOUR-IP:8000/docs` in the phone's browser. College Wi-Fi often blocks this: use a hotspot. |
| Online site is slow the first time | The free Render server was asleep. Wait about a minute. |

---

## Project structure

```
memorymate/
├── docker-compose.yml        # PostgreSQL + pgvector database
├── start.ps1                 # starts database, backend and Expo with one command
├── render.yaml               # how Render runs the backend online
├── README.md                 # this manual
├── docs/                     # PDF reports and the mobile setup guide
├── mobile/                   # the Expo (React Native) phone app
│   ├── App.js                # app frame: login, elder tabs or family screens
│   ├── src/api.js            # talks to the backend
│   ├── src/notify.js         # reminder alarms on the phone
│   ├── src/screens/          # elder screens: Talk, Today, Help, Me, welcome
│   ├── src/family/           # family and doctor screens
│   ├── src/components/       # shared buttons, options, header and tabs
│   ├── __tests__/            # Jest tests
│   └── eas.json              # Android build settings
└── backend/
    ├── requirements.txt      # Python packages
    ├── .env.example          # settings template (copy to .env)
    └── app/
        ├── main.py           # starts the app and the reminder background job
        ├── config.py         # reads settings from .env
        ├── database.py       # database connection and tables setup
        ├── models.py         # tables: users, people, memories, reminders, family links...
        ├── security.py       # passwords and login tokens
        ├── ai.py             # Gemini prompt: understands each message
        ├── embeddings.py     # turns memories into vectors for search by meaning
        ├── retrieval.py      # finds the right memories for a question
        ├── reminders.py      # reminder timing, alerts, missed/done
        ├── confirmations.py  # handles "yes / no / haan / nahi" replies
        ├── family_access.py  # family and doctor permissions and invite codes
        ├── timeutil.py       # Indian time (Asia/Kolkata) helpers
        ├── emergency.py      # spots "help!" and raises emergency alerts
        └── routers/          # API endpoints: auth, people, chat, memories, reminders, family, emergency, /test page
    └── tests/                # pytest tests (separate test database, fake AI)
```

## Security rules
- `.env` holds your Gemini key and JWT secret. **Never commit it and never paste it in chat.** If a key leaks, delete it at https://aistudio.google.com/apikey and make a new one.
- Each developer uses their **own** Gemini key.
- The database password in `docker-compose.yml` is for local development only.
- The online server is public. Test accounts with simple passwords (like `test1234`) must only hold **made-up demo data**.
- The free Gemini API may use what you send to improve Google's products, so don't put real people's private or health information through it. Real users would need a paid Gemini key.
