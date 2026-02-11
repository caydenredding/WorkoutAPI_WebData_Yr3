from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.database import get_db
from app import models, schemas

router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.ExerciseOut],
    responses={
        status.HTTP_200_OK: {"description": "List of exercises"},
    },
)
def list_exercises(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None, description="Search by exercise name (case-insensitive)"),
    equipment_id: Optional[int] = Query(None, description="Filter by equipment (id)"),
    primary_muscle_id: Optional[int] = Query(None, description="Filter by primary muscle (id)"),
):
    query = db.query(models.Exercise).options(
    joinedload(models.Exercise.primary_muscles),
    joinedload(models.Exercise.secondary_muscles),
    joinedload(models.Exercise.equipment),
    )

    if q:
        query = query.filter(models.Exercise.name.ilike(f"%{q}%"))

    if equipment_id:
        query = query.filter(models.Exercise.equipment_id == equipment_id)

    if primary_muscle_id:
        query = query.filter(models.Exercise.primary_muscles.any(models.Muscle.id == primary_muscle_id))


    exercises = (
        query.order_by(models.Exercise.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return exercises


@router.get(
    "/{exercise_id}",
    response_model=schemas.ExerciseOut,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Exercise not found"},
    },
)
def get_exercise(exercise_id: int, db: Session = Depends(get_db)):
    exercise = db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return exercise
