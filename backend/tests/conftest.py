"""Shared setup for the automatic tests.

- Uses its OWN database, "memorymate_test", on the same Docker PostgreSQL, so your real data is never touched.
  (Override with the TEST_DATABASE_URL environment variable.)
- The AI and the embeddings are FAKE: no Gemini calls, no API key needed, tests run in seconds.
- Every test starts with empty tables.

Run from the backend folder (Docker running, venv active):   pytest
"""
import hashlib
import math
import os
import re

# Point the app at the test database BEFORE any app module is imported.
TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://memorymate:memorymate@localhost:5432/memorymate_test")
os.environ["DATABASE_URL"] = TEST_URL
os.environ["GEMINI_API_KEY"] = "test-key-not-used"   # the real AI is replaced below
os.environ["MISSED_AFTER_MINUTES"] = "60"
os.environ["JWT_SECRET"] = "test-secret-only-for-pytest-not-for-real-use"

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402


def _create_test_database() -> None:
    """Create memorymate_test the first time, by connecting to the normal 'memorymate' database."""
    url = make_url(TEST_URL)
    admin = create_engine(url.set(database="memorymate"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


_create_test_database()

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402
from app.ai import AIResult  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine, init_db  # noqa: E402


# ---------- fake embeddings: same words -> similar vectors ----------
def fake_vector(text_: str) -> list[float]:
    v = [0.0] * settings.embedding_dim
    for word in re.findall(r"\w+", text_.lower()):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        v[h % settings.embedding_dim] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def fake_embed(texts, kind):
    return [fake_vector(t) for t in texts]


class FakeAI:
    """Tests set .result to the AIResult the 'AI' should return; .calls counts how often it was asked."""

    def __init__(self):
        self.result = AIResult(intent="SMALL_TALK", reply="Okay.")
        self.calls = 0
        self.last_memories = []

    def __call__(self, message, **kwargs):
        self.calls += 1
        self.last_memories = kwargs.get("memories", [])
        return self.result


@pytest.fixture(scope="session", autouse=True)
def _schema():
    init_db()  # pgvector + all tables + upgrades, exactly like the real server
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def fake_ai(monkeypatch):
    ai = FakeAI()
    monkeypatch.setattr("app.routers.chat.understand", ai)
    monkeypatch.setattr("app.routers.memories.embed", fake_embed)
    monkeypatch.setattr("app.retrieval.embed", fake_embed)
    return ai


@pytest.fixture
def client(fake_ai, monkeypatch):
    async def no_scheduler():  # tests run the reminder check themselves (POST /reminders/check-now)
        return None
    monkeypatch.setattr(main, "run_forever", no_scheduler)
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


# ---------- small helpers used by many tests ----------
def signup(client, name, email, role="ELDER", code=None, phone=None, password="test1234"):
    body = {"name": name, "email": email, "password": password, "role": role, "preferred_language": "en"}
    if code:
        body["invite_code"] = code
    if phone:
        body["phone"] = phone
    r = client.post("/auth/register", json=body)
    assert r.status_code == 201, r.text
    t = client.post("/auth/login", data={"username": email, "password": password})
    assert t.status_code == 200, t.text
    return {"Authorization": "Bearer " + t.json()["access_token"]}


def linked_family(client, elder_headers, name="Priya", email="priya@test.com", **scopes):
    """The elder invites a helper; the helper signs up with the code. Returns the helper's headers."""
    r = client.post("/family/invites", headers=elder_headers, json={"name": name, **scopes})
    assert r.status_code == 201, r.text
    return signup(client, name, email, role="FAMILY", code=r.json()["invite_code"])
