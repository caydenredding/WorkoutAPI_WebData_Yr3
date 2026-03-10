from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app import models
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, MeResponse
from app.security import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Default new accounts to role=user
    new_user = models.User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role="user",
        years_experience=0,
        goal_id=3,
        target_days_per_week=3,
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    db.refresh(new_user)

    token = create_access_token(user_id=new_user.id, username=new_user.username, role=new_user.role)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/password")

    token = create_access_token(user_id=user.id, username=user.username, role=user.role)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=MeResponse)
def me(current_user: models.User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}