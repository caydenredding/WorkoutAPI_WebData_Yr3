from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter()

# Used for creating a user
@router.post(
    "",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided to update"},
        status.HTTP_409_CONFLICT: {"description": "Username already exists"},
    }
)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    new_user = models.User(username=user.username)
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Unique username violation
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )

    db.refresh(new_user)
    return new_user

# Used for getting a list of users
@router.get("", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    users = (
        db.query(models.User)
        .order_by(models.User.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return users

# Used for getting a specific user
@router.get(
    "/{user_id}",
    response_model=schemas.UserOut,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    }
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

# Used for updating a user
@router.patch(
    "/{user_id}",
    response_model=schemas.UserOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided to update"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_409_CONFLICT: {"description": "Username already exists"},
    }
)
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    update_data = user_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No field provided"
        )

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )

    db.refresh(user)
    return user

# Used to delete a user
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"}
    }
)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()
    return


