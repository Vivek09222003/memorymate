"""The memory vault: approve, reject, list, search, share and forget memories."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import AIError
from app.database import get_db
from app.embeddings import embed, memory_text
from app.models import Memory, MemoryStatus, Person, User
from app.retrieval import search
from app.schemas import MemoryHit, MemoryOut, VisibilityUpdate
from app.security import get_current_user
from app.timeutil import local_now

router = APIRouter(prefix="/memories", tags=["Memories"])
log = logging.getLogger("memorymate.memories")


def _embed_memories(memories: list[Memory]) -> int:
    """Give memories their search vectors. Returns how many succeeded (0 if the AI is unreachable)."""
    if not memories:
        return 0
    try:
        vectors = embed([memory_text(m) for m in memories], "document")
    except AIError as e:
        log.warning("Could not embed memories: %s", e)
        return 0
    for m, v in zip(memories, vectors):
        m.embedding = v
    return len(vectors)


def _get_own_memory(db: Session, user: User, memory_id: int) -> Memory:
    memory = db.get(Memory, memory_id)
    if memory is None or memory.owner_id != user.id or memory.status == MemoryStatus.DELETED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found.")
    return memory


def activate(db: Session, memory: Memory) -> None:
    """Make a pending memory permanent (used by the approve button and by a "yes" in the chat).
    If it corrects an older memory, the older one becomes HISTORICAL instead of being deleted."""
    memory.status = MemoryStatus.ACTIVE
    memory.approved_at = datetime.now(timezone.utc)
    if memory.replaces_id:
        old = db.get(Memory, memory.replaces_id)
        if old is not None and old.owner_id == memory.owner_id and old.status == MemoryStatus.ACTIVE:
            old.status = MemoryStatus.HISTORICAL
            old.valid_to = local_now().date()
    _embed_memories([memory])  # if this fails, POST /memories/reindex can fill it in later


@router.get("", response_model=list[MemoryOut])
def list_memories(
    status_filter: MemoryStatus = Query(MemoryStatus.ACTIVE, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ACTIVE = approved memories, PENDING = waiting for yes/no, HISTORICAL = replaced by newer facts."""
    if status_filter == MemoryStatus.DELETED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Forgotten memories can't be listed.")
    return db.scalars(
        select(Memory)
        .where(Memory.owner_id == user.id, Memory.status == status_filter)
        .order_by(Memory.created_at.desc())
    ).all()


@router.get("/search", response_model=list[MemoryHit])
def search_memories(q: str = Query(min_length=1, examples=["Where does my grandson work?"]),
                    show_all: bool = Query(False, description="Also show weak matches, with their distance"),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Search approved memories by meaning, not just matching words. This is what the chat uses."""
    people = db.scalars(select(Person).where(Person.owner_id == user.id)).all()
    return [MemoryHit(memory=MemoryOut.model_validate(h.memory), matched_by=h.matched_by, distance=h.distance)
            for h in search(db, user.id, q, people, close_only=not show_all)]


@router.post("/reindex")
def reindex(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create search vectors for approved memories that don't have one yet
    (e.g. memories approved before Step 4b, or while the AI was unreachable)."""
    missing = db.scalars(select(Memory).where(Memory.owner_id == user.id,
                                              Memory.status == MemoryStatus.ACTIVE,
                                              Memory.embedding.is_(None))).all()
    done = 0
    for i in range(0, len(missing), 50):  # 50 per request
        done += _embed_memories(missing[i:i + 50])
    db.commit()
    return {"needed": len(missing), "embedded": done}


@router.post("/{memory_id}/approve", response_model=MemoryOut)
def approve(memory_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The user said yes: the memory becomes permanent. If it corrects an older memory,
    the older one becomes HISTORICAL (kept for the timeline, no longer treated as true)."""
    memory = _get_own_memory(db, user, memory_id)
    if memory.status != MemoryStatus.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only pending memories can be approved.")
    activate(db, memory)
    db.commit()
    db.refresh(memory)
    return memory


@router.post("/{memory_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject(memory_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The user said no: it is never kept."""
    memory = _get_own_memory(db, user, memory_id)
    if memory.status != MemoryStatus.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only pending memories can be rejected.")
    memory.status = MemoryStatus.DELETED
    db.commit()


@router.patch("/{memory_id}/visibility", response_model=MemoryOut)
def set_visibility(memory_id: int, data: VisibilityUpdate,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Choose who may see this memory: PRIVATE, SHARED_FAMILY, CARE or EMERGENCY."""
    memory = _get_own_memory(db, user, memory_id)
    memory.visibility = data.visibility
    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget(memory_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """'Forget this': hidden everywhere, and its search vector is removed."""
    memory = _get_own_memory(db, user, memory_id)
    memory.status = MemoryStatus.DELETED
    memory.embedding = None
    db.commit()
