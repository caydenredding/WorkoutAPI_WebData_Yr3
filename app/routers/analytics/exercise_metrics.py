from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Float, desc
from typing import List, Literal, Optional

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/users/{user_id}/exercises")


def ensure_user(db: Session, user_id: int) -> None:
    exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.get(
    "/max-set-volume",
    response_model=List[schemas.ExerciseMaxSetVolumeOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Max set volume per exercise returned"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def max_set_volume_by_exercise(
    user_id: int,
    db: Session = Depends(get_db),
    exercise_id: Optional[int] = Query(None, ge=1),
):
    ensure_user(db, user_id)

    volume_expr = cast(models.SetLog.reps, Float) * cast(models.SetLog.weight, Float)

    rn = func.row_number().over(
        partition_by=models.Exercise.id,
        order_by=[
            desc(volume_expr),
            desc(models.SetLog.weight),
            desc(models.SetLog.reps),
            desc(models.WorkoutLog.date),
            desc(models.SetLog.id),
        ],
    ).label("rn")

    q = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            models.Exercise.name.label("exercise_name"),
            volume_expr.label("max_set_volume"),
            models.SetLog.reps.label("reps"),
            models.SetLog.weight.label("weight"),
            models.WorkoutLog.date.label("date"),
            rn,
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
    )

    if exercise_id:
        q = q.filter(models.Exercise.id == exercise_id)

    rows = q.subquery()

    best = (
        db.query(
            rows.c.exercise_id,
            rows.c.exercise_name,
            rows.c.max_set_volume,
            rows.c.reps,
            rows.c.weight,
            rows.c.date,
        )
        .filter(rows.c.rn == 1)
        .order_by(rows.c.exercise_name.asc())
        .all()
    )

    return [
        {
            "exercise_id": r.exercise_id,
            "exercise_name": r.exercise_name,
            "max_set_volume": round(float(r.max_set_volume), 1),
            "reps": r.reps,
            "weight": float(r.weight),
            "date": r.date,
        }
        for r in best
    ]


@router.get(
    "/best-1rm",
    response_model=List[schemas.ExerciseBest1RMOut],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Best estimated 1RM per exercise returned"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def best_1rm_by_exercise(
    user_id: int,
    db: Session = Depends(get_db),
    formula: Literal["epley", "brzycki"] = Query("epley"),
    exercise_id: Optional[int] = Query(None, ge=1),
    max_reps: int = Query(12, ge=1, le=30),
):
    ensure_user(db, user_id)

    reps_f = cast(models.SetLog.reps, Float)
    w = cast(models.SetLog.weight, Float)

    if formula == "epley":
        e1rm_expr = w * (1.0 + (reps_f / 30.0))
    else:
        e1rm_expr = w * 36.0 / (37.0 - reps_f)

    q = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            models.Exercise.name.label("exercise_name"),
            func.max(e1rm_expr).label("best_e1rm"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.SetLog.reps <= max_reps)
        .group_by(models.Exercise.id, models.Exercise.name)
        .order_by(models.Exercise.name.asc())
    )

    if exercise_id:
        q = q.filter(models.Exercise.id == exercise_id)

    rows = q.all()

    return [
        {
            "exercise_id": r.exercise_id,
            "exercise_name": r.exercise_name,
            "formula": formula,
            "best_e1rm": round(float(r.best_e1rm), 1),
        }
        for r in rows
    ]
