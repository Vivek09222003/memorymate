"""Turning text into vectors (lists of numbers) so memories can be searched by meaning.

Two sentences that mean similar things get vectors that point in similar directions,
even in different languages: "Rahul works in Bangalore" is close to "Where is my grandson's job?".
"""
import math
from typing import Literal

from app.ai import AIError
from app.config import settings
from app.models import Memory


def _normalize(v: list[float]) -> list[float]:
    # gemini-embedding-001 vectors must be scaled to length 1 when using fewer than 3072 numbers.
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def embed(texts: list[str], kind: Literal["document", "query"]) -> list[list[float]]:
    """Embed several texts in one call. 'document' = memories we store, 'query' = questions we search with."""
    if not texts:
        return []
    if not settings.gemini_api_key:
        raise AIError("GEMINI_API_KEY is missing from your .env file.")

    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=texts,
            config={
                "task_type": "RETRIEVAL_DOCUMENT" if kind == "document" else "RETRIEVAL_QUERY",
                "output_dimensionality": settings.embedding_dim,
            },
        )
    except Exception as e:
        raise AIError(f"Couldn't create embeddings: {e}")
    return [_normalize(list(e.values)) for e in result.embeddings]


def memory_text(memory: Memory) -> str:
    """What we embed for a memory: the English fact plus the user's own words (any language)."""
    who = ""
    if memory.person is not None:
        who = f"{memory.person.name} ({memory.person.relation_to_user or 'person'}): "
    return f"{who}{memory.normalized_fact}\nOriginal words: {memory.original_text}"
