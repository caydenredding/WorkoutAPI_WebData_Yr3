from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter()


# Create a new user
@router.post(
    "/",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_201_CREATED: {"description": "User successfully created"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid goal_id"},
        status.HTTP_409_CONFLICT: {"description": "Username already exists"},
    },
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    # Validate goal if provided
    if user.goal_id is not None:
        goal_exists = (
            db.query(models.Goal.id)
            .filter(models.Goal.id == user.goal_id)
            .first()
        )
        if not goal_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid goal_id",
            )

    new_user = models.User(
        username=user.username,
        years_experience=user.years_experience or 0,
        goal_id=user.goal_id,
    )

    db.add(new_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    db.refresh(new_user)
    return new_user



# Get list of users
@router.get(
    "/",
    response_model=List[schemas.UserOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "List of users returned"},
    },
)
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


# Get a specific user
@router.get(
    "/{user_id}",
    response_model=schemas.UserOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "User retrieved"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


# Update a user
@router.patch(
    "/{user_id}",
    response_model=schemas.UserOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "User successfully updated"},
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided to update / Invalid goal_id"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_409_CONFLICT: {"description": "Username already exists"},
    },
)
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_data = user_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    # Validate goal_id if it is explicitly provided and not null
    if "goal_id" in update_data and update_data["goal_id"] is not None:
        goal_exists = db.query(models.Goal.id).filter(models.Goal.id == update_data["goal_id"]).first()
        if not goal_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid goal_id",
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    db.refresh(user)
    return user



# Delete a user
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "User successfully deleted"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    db.delete(user)
    db.commit()
