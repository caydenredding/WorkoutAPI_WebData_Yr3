from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app import models, schemas

router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.ExerciseOut],
    responses={
        200: {"description": "List of exercises"},
    },
)
def list_exercises(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None, description="Search by exercise name (case-insensitive)"),
    equipment: Optional[str] = Query(None, description="Filter by equipment (exact match)"),
    primary_muscle: Optional[str] = Query(None, description="Filter by primary muscle (exact match)"),
):
    query = db.query(models.Exercise)

    if q:
        query = query.filter(models.Exercise.name.ilike(f"%{q}%"))

    if equipment:
        query = query.filter(models.Exercise.equipment == equipment)

    if primary_muscle:
        query = query.filter(models.Exercise.primary_muscle == primary_muscle)

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
        404: {"description": "Exercise not found"},
    },
)
def get_exercise(exercise_id: int, db: Session = Depends(get_db)):
    exercise = db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise
