from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models
from app.schemas.training import SetCreate, SetOut, SetUpdate
from app.security import get_current_user

router = APIRouter(prefix="/sets")


def _require_can_access_exercise_log(db: Session, exercise_log_id: int, current_user: models.User) -> None:
    log = db.query(models.ExerciseLog).filter(models.ExerciseLog.id == exercise_log_id).first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise log not found")

    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == log.workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    if current_user.role != "admin" and workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")


def _require_can_access_set(db: Session, set_id: int, current_user: models.User) -> models.SetLog:
    s = db.query(models.SetLog).filter(models.SetLog.id == set_id).first()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")

    log = db.query(models.ExerciseLog).filter(models.ExerciseLog.id == s.exercise_log_id).first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise log not found")

    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == log.workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    if current_user.role != "admin" and workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    return s


@router.post(
    "/exercise-logs/{exercise_log_id}",
    response_model=SetOut,
    status_code=status.HTTP_201_CREATED,
)
def create_set(
    exercise_log_id: int,
    payload: SetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_can_access_exercise_log(db, exercise_log_id, current_user)

    s = models.SetLog(
        exercise_log_id=exercise_log_id,
        reps=payload.reps,
        weight=payload.weight,
        rir=payload.rir,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get(
    "/exercise-logs/{exercise_log_id}",
    response_model=List[SetOut],
    status_code=status.HTTP_200_OK,
)
def list_sets(
    exercise_log_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_can_access_exercise_log(db, exercise_log_id, current_user)

    return (
        db.query(models.SetLog)
        .filter(models.SetLog.exercise_log_id == exercise_log_id)
        .order_by(models.SetLog.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.patch(
    "/{set_id}",
    response_model=SetOut,
    status_code=status.HTTP_200_OK,
)
def update_set(
    set_id: int,
    payload: SetUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    s = _require_can_access_set(db, set_id, current_user)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    for field, value in update_data.items():
        setattr(s, field, value)

    db.commit()
    db.refresh(s)
    return s


@router.delete(
    "/{set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_set(
    set_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    s = _require_can_access_set(db, set_id, current_user)
    db.delete(s)
    db.commit()
    return