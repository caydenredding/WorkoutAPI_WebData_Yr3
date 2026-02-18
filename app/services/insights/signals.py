from __future__ import annotations
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import WorkoutLog, User
from app.services.insights.load import (
    training_load_for_range,
    fatigue_trend_14d,
    rir_stats_last_7d,
)
from app.services.insights.performance import prs_last_21d


def count_workouts(db: Session, user_id: int, d_from: date, d_to: date) -> int:
    return (
        db.query(WorkoutLog.id)
        .filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.date >= d_from,
            WorkoutLog.date <= d_to,
        )
        .count()
    )


def get_user_goal_name(db: Session, user_id: int) -> Optional[str]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.goal:
        return None
    return user.goal.name


def get_user_target_days_per_week(db: Session, user_id: int) -> int:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.target_days_per_week is None:
        return 3  # fallback default
    return int(user.target_days_per_week)


def build_signals(db: Session, user_id: int, as_of: date) -> dict:
    """
    Build rolling signals relative to a single timepoint (as_of).
    """

    # Rolling windows
    acute_start = as_of - timedelta(days=6)
    chronic_start = as_of - timedelta(days=27)
    prev_30_start = as_of - timedelta(days=29)

    # Workload
    acute_7d = training_load_for_range(db, user_id, acute_start, as_of)
    chronic_28d = training_load_for_range(db, user_id, chronic_start, as_of)

    # Compare acute to average week in chronic block (cleaner than raw ACWR)
    avg_weekly_chronic = chronic_28d / 4 if chronic_28d > 0 else 0
    acwr = (acute_7d / avg_weekly_chronic) if avg_weekly_chronic > 0 else None

    trend_14d = fatigue_trend_14d(db, user_id, as_of)

    # Attendance
    workouts_last_7d = count_workouts(db, user_id, acute_start, as_of)
    workouts_last_30d = count_workouts(db, user_id, prev_30_start, as_of)

    target_days_per_week = get_user_target_days_per_week(db, user_id)
    monthly_target = target_days_per_week * 4
    adherence_ratio_30d = workouts_last_30d / monthly_target if monthly_target else None

    # Effort
    avg_rir_7d, hard_rate_7d = rir_stats_last_7d(db, user_id, as_of)

    # Performance
    pr_count_21d, last_pr_date = prs_last_21d(db, user_id, as_of)

    return {
        "date_from": chronic_start,  # still useful for transparency
        "date_to": as_of,

        "session_load_total": acute_7d,
        "acute_load_7d": acute_7d,
        "chronic_load_28d": chronic_28d,
        "acwr": acwr,
        "fatigue_trend_14d": trend_14d,

        "workouts_last_7d": workouts_last_7d,
        "workouts_last_30d": workouts_last_30d,
        "adherence_ratio_30d": adherence_ratio_30d,
        "target_days_per_week": target_days_per_week,

        "avg_rir_last_7d": avg_rir_7d,
        "hard_sets_rate_7d": hard_rate_7d,

        "prs_last_21d": pr_count_21d,
        "last_pr_date": last_pr_date,

        "goal_name": get_user_goal_name(db, user_id),
    }
