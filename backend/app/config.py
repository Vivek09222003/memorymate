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
    # Step 4b: multilingual text embeddings; its size must match EMBEDDING_DIM.
    embedding_model: str = "gemini-embedding-001"

    # Used for "today", "tomorrow" and the dates shown to the user.
    timezone: str = "Asia/Kolkata"


settings = Settings()
