"""Database connection and session helper."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Every table model inherits from this."""


def get_db():
    """FastAPI dependency: gives each request its own session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Turn on pgvector and create any tables that don't exist yet."""
    from app import models  # noqa: F401  (importing registers the tables)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)

    # Columns added after a table already existed. Each line is safe to run every time.
    upgrades = [
        "ALTER TABLE memories ADD COLUMN IF NOT EXISTS replaces_id INTEGER "
        "REFERENCES memories(id) ON DELETE SET NULL",  # Step 4c
        "ALTER TABLE reminders ADD COLUMN IF NOT EXISTS suggested_by_id INTEGER "
        "REFERENCES users(id) ON DELETE SET NULL",  # Step 5
    ]
    with engine.begin() as conn:
        for sql in upgrades:
            conn.execute(text(sql))
