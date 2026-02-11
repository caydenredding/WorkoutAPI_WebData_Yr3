from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date, timedelta

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/users/{user_id}")


def ensure_user(db: Session, user_id: int) -> None:
    exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.get(
    "/weekly-streak",
    response_model=schemas.WeeklyStreakOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Weekly streak returned"},
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

    workout_dates = (
        db.query(models.WorkoutLog.date)
        .filter(models.WorkoutLog.user_id == user_id)
        .distinct()
        .all()
    )
    dates = sorted([row[0] for row in workout_dates])

    if not dates:
        return {"user_id": user_id, "weekly_goal": weekly_goal, "current_weekly_streak": 0}

    counts = {}
    for d in dates:
        iso_year, iso_week, _ = d.isocalendar()
        counts[(iso_year, iso_week)] = counts.get((iso_year, iso_week), 0) + 1

    today = date.today()
    current_key = (today.isocalendar().year, today.isocalendar().week)

    streak = 0
    key = current_key

    while True:
        if counts.get(key, 0) >= weekly_goal:
            streak += 1
        else:
            break

        iso_year, iso_week = key
        monday = date.fromisocalendar(iso_year, iso_week, 1)
        prev_monday = monday - timedelta(days=7)
        key = (prev_monday.isocalendar().year, prev_monday.isocalendar().week)

    return {"user_id": user_id, "weekly_goal": weekly_goal, "current_weekly_streak": streak}


@router.get(
    "/workouts-last-30-days",
    response_model=schemas.WorkoutsLast30DaysOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Workouts in the last 30 days returned"},
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
    "/last-week-missed",
    response_model=schemas.LastSevenDayGapOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"description": "Most recent 7-day gap returned (or nulls if none)"},
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

    workout_dates = (
        db.query(models.WorkoutLog.date)
        .filter(models.WorkoutLog.user_id == user_id)
        .distinct()
        .order_by(models.WorkoutLog.date.asc())
        .all()
    )
    dates = [row[0] for row in workout_dates]

    today = date.today()

    if not dates:
        start = today - timedelta(days=6)
        return {"user_id": user_id, "last_gap_start_date": start, "last_gap_end_date": today}

    last_gap_start: Optional[date] = None
    last_gap_end: Optional[date] = None

    for i in range(len(dates) - 1):
        a = dates[i]
        b = dates[i + 1]
        gap_days = (b - a).days - 1
        if gap_days >= 7:
            start = a + timedelta(days=1)
            end = start + timedelta(days=6)
            last_gap_start, last_gap_end = start, end

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
