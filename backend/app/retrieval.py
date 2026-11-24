"""Finding the memories that matter for a question (the "R" in RAG).

1. People first: if the question names someone ("Ananya") or a relation ("my granddaughter"),
   take all approved memories about that person.
2. Then by meaning: embed the question and ask pgvector for the closest approved memories.
3. Permission filter: only visibility levels the asker may see are ever searched.
"""
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import AIError
from app.config import settings
from app.embeddings import embed
from app.models import Memory, MemoryStatus, Person, Visibility

log = logging.getLogger("memorymate.retrieval")

ALL_LEVELS = list(Visibility)

# Keep "by meaning" results only if they are about as close as the best one.
# Example: best 0.28 → keep up to 0.38, so unrelated memories at 0.42+ are dropped.
CLOSE_TO_BEST = 0.10
# ...and never one farther than settings.max_memory_distance, even if it is the best:
# when nothing really matches, the AI gets no memory and says "you haven't told me that yet".


@dataclass
class Hit:
    memory: Memory
    matched_by: str               # "person", "meaning" or "recent"
    distance: float | None = None  # 0 = same meaning, 2 = opposite (cosine distance)


def _word_in(word: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(word.lower())}\b", text) is not None


def people_mentioned(question: str, people: list[Person]) -> list[Person]:
    """'What is my granddaughter studying?' → [Ananya]. 'Call my doctor' → [Dr. Sharma]."""
    q = question.lower()
    found = []
    for p in people:
        relation = (p.relation_to_user or "").lower().strip()
        head_word = relation.split()[-1] if relation else ""  # "family doctor" → "doctor"
        first_name = p.name.lower().replace("dr.", "").split()[0] if p.name.strip() else ""
        if (_word_in(p.name, q) or (first_name and _word_in(first_name, q))
                or (relation and _word_in(relation, q)) or (head_word and _word_in(head_word, q))):
            found.append(p)
    return found


def search(db: Session, owner_id: int, question: str, people: list[Person],
           visibilities: list[Visibility] = ALL_LEVELS, k: int = 8, close_only: bool = True,
           statuses: tuple[MemoryStatus, ...] = (MemoryStatus.ACTIVE,)) -> list[Hit]:
    """statuses: ACTIVE only by default; the chat also passes HISTORICAL for "where did he live before?"."""
    base = (select(Memory)
            .where(Memory.owner_id == owner_id,
                   Memory.status.in_(statuses),
                   Memory.visibility.in_(visibilities)))
    hits: dict[int, Hit] = {}

    # 1. People first.
    mentioned = people_mentioned(question, people)
    if mentioned:
        for m in db.scalars(base.where(Memory.person_id.in_([p.id for p in mentioned]))).all():
            hits[m.id] = Hit(m, "person")

    # 2. By meaning.
    try:
        [query_vector] = embed([question], "query")
        distance = Memory.embedding.cosine_distance(query_vector).label("distance")
        rows = db.execute(
            select(Memory, distance)
            .where(Memory.owner_id == owner_id,
                   Memory.status.in_(statuses),
                   Memory.visibility.in_(visibilities),
                   Memory.embedding.is_not(None))
            .order_by(distance)
            .limit(k)
        ).all()
        if rows:
            log.info("Closest memory distances: %s", ", ".join(f"{float(d):.2f}" for _, d in rows[:5]))
        if close_only and rows:
            best = float(rows[0][1])
            limit = min(best + CLOSE_TO_BEST, settings.max_memory_distance)
            rows = [(m, d) for m, d in rows if float(d) <= limit]
        for m, d in rows:
            if m.id in hits:
                hits[m.id].distance = float(d)
            else:
                hits[m.id] = Hit(m, "meaning", float(d))
    except AIError as e:
        # 3. If embeddings aren't available, fall back to the newest memories so chat still works.
        log.warning("Vector search unavailable, using recent memories: %s", e)
        for m in db.scalars(base.order_by(Memory.created_at.desc()).limit(20)).all():
            hits.setdefault(m.id, Hit(m, "recent"))

    # Person matches first, then closest meaning.
    return sorted(hits.values(), key=lambda h: (h.matched_by != "person", h.distance if h.distance is not None else 9))
