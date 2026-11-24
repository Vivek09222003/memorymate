"""Register, log in, and see who is logged in."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.family_access import join
from app.models import User
from app.schemas import DeleteAccountIn, Token, UserCreate, UserOut, UserUpdate
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Login"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        role=data.role,
        preferred_language=data.preferred_language,
        phone=data.phone.strip() if data.phone else None,
    )
    db.add(user)
    db.flush()
    if data.invite_code:  # family member signing up with the code their relative gave them
        join(db, user, data.invite_code)  # an invalid code cancels the whole sign-up
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Log in with your email (in the 'username' box) and password."""
    email = form.username.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change your name, language (en, hi, hinglish) or phone number."""
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(data: DeleteAccountIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete your account and everything in it, for good: memories, chats, reminders, people, emergency
    alerts, access logs and family links. Needs your password, so nobody can do it from an unlocked phone by
    accident. Notes and reminders you sent to others stay with them, without your name.
    The database removes the linked rows itself (ON DELETE CASCADE / SET NULL on every link to users)."""
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That password isn't right, so nothing was deleted.")
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
