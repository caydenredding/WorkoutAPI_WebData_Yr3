from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app import models
from app.schemas.training import ExerciseLogCreate, ExerciseLogOut, ExerciseLogUpdate
from app.security import get_current_user

router = APIRouter(prefix="/exercise-logs")


def _require_can_access_workout(db: Session, workout_id: int, current_user: models.User) -> models.WorkoutLog:
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    if current_user.role != "admin" and workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    return workout


def _require_can_access_exercise_log(db: Session, exercise_log_id: int, current_user: models.User) -> models.ExerciseLog:
    log = (
        db.query(models.ExerciseLog)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.ExerciseLog.id == exercise_log_id)
        .first()
    )
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise log not found")

    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == log.workout_id).first()
    if workout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    if current_user.role != "admin" and workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    return log


@router.post(
    "/workouts/{workout_id}",
    response_model=ExerciseLogOut,
    status_code=status.HTTP_201_CREATED,
)
def create_exercise_log(
    workout_id: int,
    payload: ExerciseLogCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_can_access_workout(db, workout_id, current_user)

    exercise = db.query(models.Exercise).filter(models.Exercise.id == payload.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    log = models.ExerciseLog(workout_id=workout_id, exercise_id=payload.exercise_id)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get(
    "/workouts/{workout_id}",
    response_model=List[ExerciseLogOut],
    status_code=status.HTTP_200_OK,
)
def list_exercise_logs_for_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_can_access_workout(db, workout_id, current_user)

    logs = (
        db.query(models.ExerciseLog)
        .options(
            joinedload(models.ExerciseLog.exercise).joinedload(models.Exercise.primary_muscles),
            joinedload(models.ExerciseLog.exercise).joinedload(models.Exercise.secondary_muscles),
            joinedload(models.ExerciseLog.exercise).joinedload(models.Exercise.equipment),
        )
        .filter(models.ExerciseLog.workout_id == workout_id)
        .order_by(models.ExerciseLog.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return logs


@router.patch(
    "/{exercise_log_id}",
    response_model=ExerciseLogOut,
    status_code=status.HTTP_200_OK,
)
def update_exercise_log(
    exercise_log_id: int,
    payload: ExerciseLogUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    log = _require_can_access_exercise_log(db, exercise_log_id, current_user)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    for field, value in update_data.items():
        setattr(log, field, value)

    db.commit()
    db.refresh(log)
    return log


@router.delete(
    "/{exercise_log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_exercise_log(
    exercise_log_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    log = _require_can_access_exercise_log(db, exercise_log_id, current_user)
    db.delete(log)
    db.commit()
    return