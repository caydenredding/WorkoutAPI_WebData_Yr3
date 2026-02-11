from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter()


# Create a workout for a user
@router.post(
    "/users/{user_id}/workouts",
    response_model=schemas.WorkoutOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def create_workout(
    user_id: int,
    workout: schemas.WorkoutCreate,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_workout = models.WorkoutLog(user_id=user_id, date=workout.date)
    db.add(new_workout)
    db.commit()
    db.refresh(new_workout)
    return new_workout


# List workouts for a user (with pagination)
@router.get(
    "/users/{user_id}/workouts",
    response_model=List[schemas.WorkoutOut],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def list_user_workouts(
    user_id: int,
    db: Session = Depends(get_db),
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


# Get one workout
@router.get(
    "/workouts/{workout_id}",
    response_model=schemas.WorkoutOut,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Workout not found"},
    },
)
def get_workout(workout_id: int, db: Session = Depends(get_db)):
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    return workout


# Update a workout (PATCH)
@router.patch(
    "/workouts/{workout_id}",
    response_model=schemas.WorkoutOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "No fields provided to update"},
        status.HTTP_404_NOT_FOUND: {"description": "Workout not found"},
    },
)
def update_workout(
    workout_id: int,
    workout_update: schemas.WorkoutUpdate,
    db: Session = Depends(get_db),
):
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    update_data = workout_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")
    for field, value in update_data.items():
        setattr(workout, field, value)

    db.commit()
    db.refresh(workout)
    return workout


# Delete a workout
@router.delete(
    "/workouts/{workout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Workout not found"},
    },
)
def delete_workout(workout_id: int, db: Session = Depends(get_db)):
    workout = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    db.delete(workout)
    db.commit()
    return
