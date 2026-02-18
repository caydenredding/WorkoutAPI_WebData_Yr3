from __future__ import annotations
from datetime import date, timedelta
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from app.models import WorkoutLog, ExerciseLog, SetLog


def estimate_e1rm_epley(weight: float, reps: int) -> float:
    return float(weight) * (1.0 + float(reps) / 30.0)


def proximity_factor_from_rir(rir: Optional[int]) -> float:
    if rir is None:
        return 1.0
    if rir >= 4:
        return 0.7
    if rir == 3:
        return 0.85
    if rir == 2:
        return 1.0
    if rir == 1:
        return 1.15
    return 1.3  # rir <= 0 (failure)


def set_stress(weight: float, reps: int, rir: Optional[int]) -> float:
    """
    Stress model:
      volume = weight * reps
      intensity factor = (%1RM)^2 using per-set e1RM proxy
      proximity factor from RIR if present
    """
    w = float(weight)
    r = int(reps)
    volume = w * r

    e1rm = estimate_e1rm_epley(w, r)
    pct = (w / e1rm) if e1rm > 0 else 0.0
    intensity_factor = (pct * pct) if pct > 0 else 1.0

    proximity = proximity_factor_from_rir(rir)
    return volume * intensity_factor * proximity


def fetch_sets_in_range(
    db: Session, user_id: int, d_from: date, d_to: date
) -> List[Tuple[float, int, Optional[int]]]:
    """
    Returns (weight, reps, rir) for all sets by user in [d_from, d_to].
    """
    return (
        db.query(SetLog.weight, SetLog.reps, SetLog.rir)
        .join(ExerciseLog, SetLog.exercise_log_id == ExerciseLog.id)
        .join(WorkoutLog, ExerciseLog.workout_id == WorkoutLog.id)
        .filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.date >= d_from,
            WorkoutLog.date <= d_to,
        )
        .all()
    )


def training_load_for_range(db: Session, user_id: int, d_from: date, d_to: date) -> float:
    total = 0.0
    for weight, reps, rir in fetch_sets_in_range(db, user_id, d_from, d_to):
        total += set_stress(weight, reps, rir)
    return float(total)


def rir_stats_last_7d(db: Session, user_id: int, end_date: date) -> tuple[Optional[float], Optional[float]]:
    """
    avg_rir, hard_sets_rate among non-null RIR sets in last 7 days.
    hard_sets_rate = fraction with rir <= 1.
    """
    start = end_date - timedelta(days=6)

    rows = (
        db.query(SetLog.rir)
        .join(ExerciseLog, SetLog.exercise_log_id == ExerciseLog.id)
        .join(WorkoutLog, ExerciseLog.workout_id == WorkoutLog.id)
        .filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.date >= start,
            WorkoutLog.date <= end_date,
            SetLog.rir.isnot(None),
        )
        .all()
    )

    rirs = [int(r[0]) for r in rows if r[0] is not None]
    if not rirs:
        return None, None

    avg = sum(rirs) / len(rirs)
    hard = sum(1 for x in rirs if x <= 1) / len(rirs)
    return float(avg), float(hard)


def fatigue_trend_14d(db: Session, user_id: int, end_date: date) -> float:
    """
    Normalised delta between last 7d load and previous 7d load.
    >0 means rising load/fatigue.
    """
    last7_start = end_date - timedelta(days=6)
    prev7_end = end_date - timedelta(days=7)
    prev7_start = end_date - timedelta(days=13)

    last7 = training_load_for_range(db, user_id, last7_start, end_date)
    prev7 = training_load_for_range(db, user_id, prev7_start, prev7_end)

    denom = max(prev7, 1.0)
    return float((last7 - prev7) / denom)
