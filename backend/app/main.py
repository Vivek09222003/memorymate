"""MemoryMate API. Run from the backend folder with:  uvicorn app.main:app --reload"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine, get_db, init_db
from app.reminders import run_forever
from app.routers import auth, chat, emergency, family, memories, people, reminders, testpage

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup
    checker = asyncio.create_task(run_forever())  # rings reminders on time
    yield
    checker.cancel()


app = FastAPI(title="MemoryMate API", version="0.6.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(people.router)
app.include_router(people.rel_router)
app.include_router(chat.router)
app.include_router(memories.router)
app.include_router(reminders.router)
app.include_router(family.router)
app.include_router(emergency.router)
app.include_router(testpage.router)  # simple chat page at /test


@app.get("/", tags=["System"])
def root():
    return {"app": "MemoryMate", "docs": "/docs", "test_chat": "/test"}


@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)):
    """Checks the database connection and lists the tables that exist."""
    db.execute(text("SELECT 1"))
    vector_on = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar() is not None
    return {
        "status": "ok",
        "database": "connected",
        "pgvector": vector_on,
        "tables": sorted(inspect(engine).get_table_names()),
    }
