from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Float, desc
from typing import List, Literal, Optional
from datetime import date, timedelta

from app.database import get_db
from app import models, schemas

router = APIRouter()

def ensure_user(db: Session, user_id: int) -> None:
    exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

# -- max set volume and best 1RM by exercise for a user (optionally filtered to a specific exercise) --
@router.get(
    "/users/{user_id}/analytics/exercises/max-set-volume",
    response_model=List[schemas.ExerciseMaxSetVolumeOut],
    responses={status.HTTP_404_NOT_FOUND: {"description": "User not found"}},
)
def max_set_volume_by_exercise(
    user_id: int,
    db: Session = Depends(get_db),
    exercise_id: Optional[int] = Query(None, ge=1),
):
    # ensure user exists
    ensure_user(db, user_id)

    # compute per-set volume
    volume_expr = cast(models.SetLog.reps, Float) * cast(models.SetLog.weight, Float)

    base = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            models.Exercise.name.label("exercise_name"),
            volume_expr.label("set_volume"),
            models.SetLog.reps.label("reps"),
            models.SetLog.weight.label("weight"),
            models.WorkoutLog.date.label("date"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
    )

    if exercise_id:
        base = base.filter(models.Exercise.id == exercise_id)

    # window function approach is ideal, but to keep it simple:
    # 1) get max volume per exercise
    subq = (
        base.with_entities(
            models.Exercise.id.label("exercise_id"),
            func.max(volume_expr).label("max_set_volume"),
        )
        .group_by(models.Exercise.id)
        .subquery()
    )

    # 2) join back to grab reps/weight/date that achieved it (ties possible -> returns multiple)
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
            "max_set_volume": float(r.max_set_volume),
            "reps": r.reps,
            "weight": float(r.weight),
            "date": r.date,
        }
        for r in best
    ]


@router.get(
    "/users/{user_id}/analytics/exercises/best-1rm",
    response_model=List[schemas.ExerciseBest1RMOut],
    responses={status.HTTP_404_NOT_FOUND: {"description": "User not found"}},
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
        # brzycki: weight * 36 / (37 - reps)
        e1rm_expr = w * 36.0 / (37.0 - reps_f)

    base = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            models.Exercise.name.label("exercise_name"),
            e1rm_expr.label("e1rm"),
            models.SetLog.reps.label("reps"),
            models.SetLog.weight.label("weight"),
            models.WorkoutLog.date.label("date"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.SetLog.reps <= max_reps)
    )

    if exercise_id:
        base = base.filter(models.Exercise.id == exercise_id)

    subq = (
        base.with_entities(
            models.Exercise.id.label("exercise_id"),
            func.max(e1rm_expr).label("best_e1rm"),
        )
        .group_by(models.Exercise.id)
        .subquery()
    )

    rows = (
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
        rows = rows.filter(models.Exercise.id == exercise_id)

    rows = rows.all()

    return [
        {
            "exercise_id": r.exercise_id,
            "exercise_name": r.exercise_name,
            "formula": formula,
            "best_e1rm": round(float(r.best_e1rm), 1),
        }
        for r in rows
    ]
    
# -- Additional endpoints for weekly streaks, workouts in last 30 days, and last 7 day gap could be implemented similarly --

@router.get(
    "/users/{user_id}/analytics/weekly-streak",
    response_model=schemas.WeeklyStreakOut,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def get_weekly_streak(
    user_id: int,
    db: Session = Depends(get_db),
    weekly_goal: int = Query(3, ge=1, le=14),
):
    """
    Current consecutive-week streak where workouts in the ISO week >= weekly_goal.
    Week is ISO week (Mon-Sun).
    """
    ensure_user(db, user_id)

    # Get distinct workout dates (avoid double-counting same-day multiple workouts)
    workout_dates = (
        db.query(models.WorkoutLog.date)
        .filter(models.WorkoutLog.user_id == user_id)
        .distinct()
        .all()
    )
    dates = sorted([row[0] for row in workout_dates])

    if not dates:
        return {"user_id": user_id, "weekly_goal": weekly_goal, "current_weekly_streak": 0}

    # Count workouts per ISO week
    # key: (iso_year, iso_week) -> count
    counts = {}
    for d in dates:
        iso_year, iso_week, _ = d.isocalendar()
        counts[(iso_year, iso_week)] = counts.get((iso_year, iso_week), 0) + 1

    # Current week key based on today
    today = date.today()
    current_key = (today.isocalendar().year, today.isocalendar().week)

    today = date.today()
    current_key = (today.isocalendar().year, today.isocalendar().week)

    # If current week meets goal, include it; otherwise start from previous week
    if counts.get(current_key, 0) >= weekly_goal:
        key = current_key
    else:
        # previous week (robust across year boundaries)
        monday = date.fromisocalendar(current_key[0], current_key[1], 1)
        prev_monday = monday - timedelta(days=7)
        key = (prev_monday.isocalendar().year, prev_monday.isocalendar().week)

    streak = 0
    while True:
        if counts.get(key, 0) >= weekly_goal:
            streak += 1
        else:
            break

    monday = date.fromisocalendar(key[0], key[1], 1)
    prev_monday = monday - timedelta(days=7)
    key = (prev_monday.isocalendar().year, prev_monday.isocalendar().week)

    streak = 0
    key = current_key

    # Walk backward week-by-week
    while True:
        if counts.get(key, 0) >= weekly_goal:
            streak += 1
        else:
            break

        # Move to previous ISO week:
        # Go to Monday of this ISO week, subtract 7 days, recompute ISO week
        # (robust across year boundaries)
        iso_year, iso_week = key
        # Find a date inside that ISO week (Monday)
        # Monday = iso calendar day 1
        monday = date.fromisocalendar(iso_year, iso_week, 1)
        prev_monday = monday - timedelta(days=7)
        key = (prev_monday.isocalendar().year, prev_monday.isocalendar().week)

    return {"user_id": user_id, "weekly_goal": weekly_goal, "current_weekly_streak": streak}

@router.get(
    "/users/{user_id}/analytics/workouts-last-30-days",
    response_model=schemas.WorkoutsLast30DaysOut,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def workouts_last_30_days(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Number of workouts (WorkoutLog rows) in the last 30 days.
    (Counts workouts, not unique days.)
    """
    ensure_user(db, user_id)

    today = date.today()
    start = today - timedelta(days=30)

    count = (
        db.query(func.count(models.WorkoutLog.id))
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= start)
        .filter(models.WorkoutLog.date <= today)
        .scalar()
    )

    return {"user_id": user_id, "days": 30, "workouts_count": int(count or 0)}


@router.get(
    "/users/{user_id}/analytics/last-week-missed",
    response_model=schemas.LastSevenDayGapOut,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def last_week_missed(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns the most recent 7-day window (start..start+6) with NO workout logged.
    If user has never had a 7-day gap, returns nulls.
    """
    ensure_user(db, user_id)

    # We use DISTINCT dates so multiple workouts in a day don't matter
    workout_dates = (
        db.query(models.WorkoutLog.date)
        .filter(models.WorkoutLog.user_id == user_id)
        .distinct()
        .order_by(models.WorkoutLog.date.asc())
        .all()
    )
    dates = [row[0] for row in workout_dates]

    if not dates:
        # No workouts at all => infinite gaps; pick "last 7 days" ending today
        today = date.today()
        start = today - timedelta(days=6)
        return {"user_id": user_id, "last_gap_start_date": start, "last_gap_end_date": today}

    last_gap_start: Optional[date] = None
    last_gap_end: Optional[date] = None

    # Check gaps between consecutive workout days
    for i in range(len(dates) - 1):
        a = dates[i]
        b = dates[i + 1]
        # number of days between them
        gap_days = (b - a).days - 1
        if gap_days >= 7:
            # There exists a 7-day window with no workouts starting at a+1
            start = a + timedelta(days=1)
            end = start + timedelta(days=6)
            last_gap_start, last_gap_end = start, end

    # Also consider gap from last workout date to today
    today = date.today()
    gap_after_last = (today - dates[-1]).days
    if gap_after_last >= 7:
        start = dates[-1] + timedelta(days=1)
        end = start + timedelta(days=6)
        last_gap_start, last_gap_end = start, end

    return {
        "user_id": user_id,
        "last_gap_start_date": last_gap_start,
        "last_gap_end_date": last_gap_end,
    }