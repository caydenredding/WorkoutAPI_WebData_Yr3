from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List

from app.database import get_db
from app import models
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.security import require_admin, require_self_or_admin, hash_password

router = APIRouter()


@router.post(
    "/",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    responses={
        status.HTTP_201_CREATED: {"description": "User successfully created"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid goal_id"},
        status.HTTP_409_CONFLICT: {"description": "Username already exists"},
        status.HTTP_403_FORBIDDEN: {"description": "Admin role required"},
    },
)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    if user.role not in ("user", "admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be 'user' or 'admin'")

    if user.goal_id is not None:
        goal_exists = db.query(models.Goal.id).filter(models.Goal.id == user.goal_id).first()
        if not goal_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid goal_id")

    if user.target_days_per_week is not None and (user.target_days_per_week < 1 or user.target_days_per_week > 7):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_days_per_week must be between 1 and 7")

    new_user = models.User(
        username=user.username,
        hashed_password=hash_password(user.password),
        role=user.role or "user",
        years_experience=user.years_experience or 0,
        goal_id=user.goal_id or 3,
        target_days_per_week=user.target_days_per_week or 3,
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    db.refresh(new_user)
    return new_user


@router.get(
    "/",
    response_model=List[UserOut],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin)],
)
def list_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return (
        db.query(models.User)
        .order_by(models.User.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_403_FORBIDDEN: {"description": "Not permitted"},
    },
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _current=Depends(require_self_or_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided / Invalid goal_id"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_409_CONFLICT: {"description": "Username already exists"},
        status.HTTP_403_FORBIDDEN: {"description": "Not permitted"},
    },
)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_self_or_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = user_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    # Only admin can modify role
    if "role" in update_data:
        if current_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required to change role")
        if update_data["role"] not in ("user", "admin"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be 'user' or 'admin'")

    if "goal_id" in update_data and update_data["goal_id"] is not None:
        goal_exists = db.query(models.Goal.id).filter(models.Goal.id == update_data["goal_id"]).first()
        if not goal_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid goal_id")

    if "target_days_per_week" in update_data and update_data["target_days_per_week"] is not None:
        if update_data["target_days_per_week"] < 1 or update_data["target_days_per_week"] > 7:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_days_per_week must be between 1 and 7")

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_403_FORBIDDEN: {"description": "Admin role required"},
    },
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.delete(user)
    db.commit()
    return