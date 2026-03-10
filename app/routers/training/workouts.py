from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models
from app.schemas.training import WorkoutCreate, WorkoutOut, WorkoutUpdate
from app.security import require_self_or_admin, get_current_user

router = APIRouter(prefix="/workouts")


@router.post(
    "/users/{user_id}",
    response_model=WorkoutOut,
    status_code=status.HTTP_201_CREATED,
)
def create_workout(
    user_id: int,
    workout: WorkoutCreate,
    db: Session = Depends(get_db),
    _current=Depends(require_self_or_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_workout = models.WorkoutLog(user_id=user_id, date=workout.date)
    db.add(new_workout)
    db.commit()
    db.refresh(new_workout)
    return new_workout


@router.get(
    "/users/{user_id}",
    response_model=List[WorkoutOut],
    status_code=status.HTTP_200_OK,
)
def list_user_workouts(
    user_id: int,
    db: Session = Depends(get_db),
    _current=Depends(require_self_or_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    workouts = (
        db.query(models.WorkoutLog)
        .filter(models.WorkoutLog.user_id == user_id)
        .order_by(models.WorkoutLog.date.desc(), models.WorkoutLog.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return workouts


@router.get(
    "/{workout_id}",
    response_model=WorkoutOut,
    status_code=status.HTTP_200_OK,
)
def get_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    if current_user.role != "admin" and workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    return workout


@router.patch(
    "/{workout_id}",
    response_model=WorkoutOut,
    status_code=status.HTTP_200_OK,
)
def update_workout(
    workout_id: int,
    workout_update: WorkoutUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    if current_user.role != "admin" and workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    update_data = workout_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    for field, value in update_data.items():
        setattr(workout, field, value)

    db.commit()
    db.refresh(workout)
    return workout


@router.delete(
    "/{workout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    if current_user.role != "admin" and workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    db.delete(workout)
    db.commit()
    return