"""App settings, read from the .env file (or environment variables)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://memorymate:memorymate@localhost:5432/memorymate"
    embedding_dim: int = 1024

    # Login tokens (Step 2). The default only suits your own laptop; set JWT_SECRET in .env.
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # AI (Step 3). Get a key at https://aistudio.google.com/apikey
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    # Used automatically when the main model is busy (503). Leave empty to turn off.
    gemini_fallback_model: str = "gemini-3.6-flash"
    # Step 4b: multilingual text embeddings; its size must match EMBEDDING_DIM.
    embedding_model: str = "gemini-embedding-001"
    # A ringing reminder nobody answers becomes MISSED after this many minutes (set 2 for quick testing).
    missed_after_minutes: int = 60
    # Memory search "by meaning": ignore memories farther than this (cosine distance, 0 = same meaning).
    # Stops unrelated memories reaching the AI when nothing really matches. Tune it with
    # GET /memories/search?q=...&show_all=true, which shows each memory's distance.
    max_memory_distance: float = 0.5
    # Give up on a Gemini call after this many seconds, instead of waiting forever.
    ai_timeout_seconds: int = 25

    # Used for "today", "tomorrow" and the dates shown to the user.
    timezone: str = "Asia/Kolkata"


settings = Settings()
