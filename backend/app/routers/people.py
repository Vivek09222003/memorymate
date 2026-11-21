"""People in the user's life, and the relationships between them.

Every query is filtered by owner_id, so a user can only ever see their own people.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Person, Relationship, User
from app.schemas import PersonCreate, PersonOut, PersonUpdate, RelationshipCreate, RelationshipOut
from app.security import get_current_user

router = APIRouter(prefix="/people", tags=["People"])
rel_router = APIRouter(prefix="/relationships", tags=["Relationships"])


def _get_own_person(db: Session, user: User, person_id: int) -> Person:
    person = db.get(Person, person_id)
    if person is None or person.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found.")
    return person


# ---------- people ----------
@router.get("", response_model=list[PersonOut])
def list_people(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Person).where(Person.owner_id == user.id).order_by(Person.name)).all()


@router.get("/search", response_model=list[PersonOut])
def search_people(
    q: str = Query(min_length=1, examples=["granddaughter"]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find people by name or by how they're related to you, e.g. 'Ananya' or 'granddaughter'.
    The AI will use this in Step 3 to work out who 'my granddaughter' means."""
    pattern = f"%{q.strip()}%"
    return db.scalars(
        select(Person)
        .where(Person.owner_id == user.id)
        .where(or_(Person.name.ilike(pattern), Person.relation_to_user.ilike(pattern)))
        .order_by(Person.name)
    ).all()


@router.get("/emergency", response_model=list[PersonOut])
def emergency_contacts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Person).where(Person.owner_id == user.id, Person.is_emergency_contact.is_(True)).order_by(Person.name)
    ).all()


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def add_person(data: PersonCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    person = Person(owner_id=user.id, **data.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_own_person(db, user, person_id)


@router.patch("/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int, data: PersonUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    person = _get_own_person(db, user, person_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    person = _get_own_person(db, user, person_id)
    db.delete(person)  # their relationships are removed too; memories about them are kept
    db.commit()


# ---------- relationships ----------
@rel_router.get("", response_model=list[RelationshipOut])
def list_relationships(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Relationship).where(Relationship.owner_id == user.id)).all()


@rel_router.post("", response_model=RelationshipOut, status_code=status.HTTP_201_CREATED)
def add_relationship(data: RelationshipCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Example: Priya (from) --daughter--> Ananya (to) means Ananya is Priya's daughter."""
    if data.from_person_id == data.to_person_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A person can't be related to themselves.")
    _get_own_person(db, user, data.from_person_id)
    _get_own_person(db, user, data.to_person_id)
    rel = Relationship(owner_id=user.id, **data.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@rel_router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(relationship_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rel = db.get(Relationship, relationship_id)
    if rel is None or rel.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found.")
    db.delete(rel)
    db.commit()
