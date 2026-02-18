from __future__ import annotations
from datetime import date, timedelta
from typing import Optional, Tuple, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import WorkoutLog, ExerciseLog, SetLog


def prs_last_21d(
    db: Session,
    user_id: int,
    end_date: date,
    pct_threshold: float = 0.015,
) -> Tuple[int, Optional[date]]:
    """
    Count PRs over last 21 days using e1RM per exercise.

    PR definition (per exercise):
      best_e1rm_in_window >= best_e1rm_before_window * (1 + pct_threshold)

    NOTE: We do NOT count exercises with no history before the window
          (prevents "new exercise = PR" spam).
    """
    window_start = end_date - timedelta(days=20)

    # Best e1RM per exercise in the window
    window_rows = (
        db.query(
            ExerciseLog.exercise_id.label("exercise_id"),
            func.max(SetLog.weight * (1 + (SetLog.reps / 30.0))).label("best_e1rm_window"),
            func.max(WorkoutLog.date).label("latest_date_in_window"),
        )
        .join(SetLog, SetLog.exercise_log_id == ExerciseLog.id)
        .join(WorkoutLog, ExerciseLog.workout_id == WorkoutLog.id)
        .filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.date >= window_start,
            WorkoutLog.date <= end_date,
        )
        .group_by(ExerciseLog.exercise_id)
        .all()
    )

    if not window_rows:
        return 0, None

    # Best e1RM per exercise before the window
    before_rows = (
        db.query(
            ExerciseLog.exercise_id.label("exercise_id"),
            func.max(SetLog.weight * (1 + (SetLog.reps / 30.0))).label("best_e1rm_before"),
        )
        .join(SetLog, SetLog.exercise_log_id == ExerciseLog.id)
        .join(WorkoutLog, ExerciseLog.workout_id == WorkoutLog.id)
        .filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.date < window_start,
        )
        .group_by(ExerciseLog.exercise_id)
        .all()
    )

    best_before: Dict[int, float] = {
        int(r.exercise_id): float(r.best_e1rm_before)
        for r in before_rows
        if r.best_e1rm_before is not None
    }

    pr_count = 0
    last_pr: Optional[date] = None

    for r in window_rows:
        ex_id = int(r.exercise_id)
        best_window = float(r.best_e1rm_window or 0.0)

        if ex_id not in best_before:
            continue  # no baseline before window

        baseline = best_before[ex_id]
        if baseline > 0 and best_window >= baseline * (1.0 + pct_threshold):
            pr_count += 1
            d = r.latest_date_in_window
            if d and (last_pr is None or d > last_pr):
                last_pr = d

    return pr_count, last_pr
