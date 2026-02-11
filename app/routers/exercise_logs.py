from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter()


# Create a new exercise log
@router.post(
    "/workouts/{workout_id}/exercise-logs",
    response_model=schemas.ExerciseLogOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Workout not found or Exercise not found"}
        },
)
def create_exercise_log(workout_id: int, payload: schemas.ExerciseLogCreate, db: Session = Depends(get_db)):
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    exercise = db.query(models.Exercise).filter(models.Exercise.id == payload.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    log = models.ExerciseLog(workout_id=workout_id, exercise_id=payload.exercise_id)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log



# Get all exercise logs from a workout
@router.get(
    "/workouts/{workout_id}/exercise-logs",
    response_model=List[schemas.ExerciseLogOut],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Workout not found"},
    },
)
def list_exercise_logs_for_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    # Ensure workout exists
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    logs = (
        db.query(models.ExerciseLog)
        .options(
        joinedload(models.ExerciseLog.exercise)
        .joinedload(models.Exercise.primary_muscles),
        joinedload(models.ExerciseLog.exercise)
        .joinedload(models.Exercise.secondary_muscles),
        joinedload(models.ExerciseLog.exercise)
        .joinedload(models.Exercise.equipment),
        )
        .filter(models.ExerciseLog.workout_id == workout_id)
        .order_by(models.ExerciseLog.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return logs

# Update an exercise log
@router.patch(
    "/exercise-logs/{exercise_log_id}",
    response_model=schemas.ExerciseLogOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided to update"},
        status.HTTP_404_NOT_FOUND: {"description": "Exercise log not found"},
    },
)
def update_exercise_log(
    exercise_log_id: int,
    payload: schemas.ExerciseLogUpdate,
    db: Session = Depends(get_db),
):
    log = db.query(models.ExerciseLog).filter(models.ExerciseLog.id == exercise_log_id).first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise log not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    for field, value in update_data.items():
        setattr(log, field, value)

    db.commit()
    db.refresh(log)
    return log


# Delete an exercise log
@router.delete(
    "/exercise-logs/{exercise_log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Exercise log not found"},
    },
)
def delete_exercise_log(exercise_log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.ExerciseLog).filter(models.ExerciseLog.id == exercise_log_id).first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise log not found")

    db.delete(log)
    db.commit()
    return
