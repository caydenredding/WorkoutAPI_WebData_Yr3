from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import Float, cast, func, desc
from sqlalchemy.orm import Session

from app import models


# ----------------------------
# Helpers / config
# ----------------------------

MetricType = Literal["e1rm", "max_set_volume"]
E1RMFormula = Literal["epley", "brzycki"]


def ensure_user(db: Session, user_id: int) -> None:
    """
    Small helper: we want to fail fast if user doesn't exist.
    """
    exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


def _date_range_prev_period(date_from: date, date_to: date) -> Tuple[date, date]:
    """
    Previous period of equal length:
    current: [date_from, date_to]
    prev:    [date_from - length, date_to - length]
    """
    length_days = (date_to - date_from).days
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=length_days)
    return prev_from, prev_to


def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0

def _top_prs(prs: List[Dict[str, Any]], n: int = 3) -> List[Dict[str, Any]]:
    """
    Returns top N PRs ranked by improvement amount (new - previous).

    If previous is None (first-ever PR for that metric/exercise),
    we treat improvement as 'new' so it still ranks reasonably.
    """
    def improvement(pr: Dict[str, Any]) -> float:
        new_val = _safe_float(pr.get("new"))
        prev_val = pr.get("previous")
        if prev_val is None:
            return new_val
        return new_val - _safe_float(prev_val)

    return sorted(prs, key=improvement, reverse=True)[:n]


# ----------------------------
# Core metrics (simple ones)
# ----------------------------

def get_sessions(db: Session, user_id: int, date_from: date, date_to: date) -> int:
    """
    Sessions = number of WorkoutLog rows in the period.
    """
    return int(
        db.query(func.count(models.WorkoutLog.id))
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0
    )


def get_unique_training_days(db: Session, user_id: int, date_from: date, date_to: date) -> int:
    """
    Unique training days = COUNT(DISTINCT WorkoutLog.date) within the period.

    If WorkoutLog.date is a DateTime instead of Date:
    - On SQLite you can use func.date(WorkoutLog.date)
    - On Postgres you can cast to DATE.
    """
    return int(
        db.query(func.count(func.distinct(models.WorkoutLog.date)))
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0
    )


def get_total_sets(db: Session, user_id: int, date_from: date, date_to: date) -> int:
    """
    Total sets = number of SetLog rows linked to workouts in the period.
    """
    return int(
        db.query(func.count(models.SetLog.id))
        .join(models.ExerciseLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.ExerciseLog.workout_id == models.WorkoutLog.id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0
    )


def get_total_volume(db: Session, user_id: int, date_from: date, date_to: date) -> float:
    """
    Total volume (tonnage) = SUM(reps * weight) across all sets in the period.

    Notes:
    - This assumes weight is the load you want to count.
    - For bodyweight movements, you may store weight differently (e.g. extra load only).
      If you want true tonnage including bodyweight, you'd need a bodyweight field somewhere.
    """
    volume_expr = cast(models.SetLog.reps, Float) * cast(models.SetLog.weight, Float)

    return _safe_float(
        db.query(func.sum(volume_expr))
        .join(models.ExerciseLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.ExerciseLog.workout_id == models.WorkoutLog.id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0.0
    )


# ----------------------------
# PR detection
# ----------------------------

def _e1rm_expr(formula: E1RMFormula):
    """
    Returns a SQLAlchemy expression computing e1RM from SetLog reps/weight.

    epley:   w * (1 + reps/30)
    brzycki: w * 36 / (37 - reps)

    If you want to ignore very high reps, filter in the query (see get_prs()).
    """
    reps_f = cast(models.SetLog.reps, Float)
    w = cast(models.SetLog.weight, Float)

    if formula == "epley":
        return w * (1.0 + (reps_f / 30.0))
    return w * 36.0 / (37.0 - reps_f)


def get_prs(
    db: Session,
    user_id: int,
    date_from: date,
    date_to: date,
    *,
    e1rm_formula: E1RMFormula = "epley",
    max_reps_for_e1rm: int = 12,
) -> List[Dict[str, Any]]:
    """
    PR logic:
    For each exercise, compare the best metric in the current period against the
    best metric BEFORE the period start (all-time prior).

    We return PR events for:
      - e1RM PR (best estimated 1RM)
      - max set volume PR (best reps*weight set)

    Complex bit:
    - We need "previous best before date_from" so we don't count current week data
      as the previous best. That avoids false PRs.
    """
    prs: List[Dict[str, Any]] = []

    # ---------- e1RM PRs ----------
    e1rm = _e1rm_expr(e1rm_formula)

    # Best e1RM per exercise in current period
    curr_e1rm = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            models.Exercise.name.label("exercise_name"),
            func.max(e1rm).label("best_e1rm"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .filter(models.SetLog.reps <= max_reps_for_e1rm)
        .group_by(models.Exercise.id, models.Exercise.name)
        .all()
    )

    # Best e1RM per exercise BEFORE the period start
    prev_e1rm = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            func.max(e1rm).label("prev_best_e1rm"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date < date_from)
        .filter(models.SetLog.reps <= max_reps_for_e1rm)
        .group_by(models.Exercise.id)
        .all()
    )
    prev_e1rm_map = {r.exercise_id: _safe_float(r.prev_best_e1rm) for r in prev_e1rm}

    for r in curr_e1rm:
        current = _safe_float(r.best_e1rm)
        previous = prev_e1rm_map.get(r.exercise_id, 0.0)
        if current > previous and current > 0:
            prs.append(
                {
                    "exercise_id": r.exercise_id,
                    "exercise_name": r.exercise_name,
                    "type": "e1rm",
                    "formula": e1rm_formula,
                    "new": round(current, 1),
                    "previous": round(previous, 1) if previous else None,
                }
            )

    # ---------- Max set volume PRs ----------
    set_volume = cast(models.SetLog.reps, Float) * cast(models.SetLog.weight, Float)

    curr_vol = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            models.Exercise.name.label("exercise_name"),
            func.max(set_volume).label("best_set_volume"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .group_by(models.Exercise.id, models.Exercise.name)
        .all()
    )

    prev_vol = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            func.max(set_volume).label("prev_best_set_volume"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date < date_from)
        .group_by(models.Exercise.id)
        .all()
    )
    prev_vol_map = {r.exercise_id: _safe_float(r.prev_best_set_volume) for r in prev_vol}

    for r in curr_vol:
        current = _safe_float(r.best_set_volume)
        previous = prev_vol_map.get(r.exercise_id, 0.0)
        if current > previous and current > 0:
            prs.append(
                {
                    "exercise_id": r.exercise_id,
                    "exercise_name": r.exercise_name,
                    "type": "max_set_volume",
                    "new": round(current, 1),
                    "previous": round(previous, 1) if previous else None,
                }
            )

    # Optional: sort PRs so summaries show the biggest wins first
    prs.sort(key=lambda x: (x["type"], x["new"]), reverse=True)
    return prs


# ----------------------------
# Improvements vs previous period
# ----------------------------

def get_improvements_vs_previous_period(
    db: Session,
    user_id: int,
    date_from: date,
    date_to: date,
) -> Dict[str, Any]:
    """
    Compare current period metrics against the previous period of equal length.

    This is intentionally high-level and stable:
      - sessions
      - unique_training_days
      - total_sets
      - total_volume

    If you later want "top 3 exercise improvements", you can compute per-exercise best e1RM
    in each period and diff them.
    """
    prev_from, prev_to = _date_range_prev_period(date_from, date_to)

    cur_sessions = get_sessions(db, user_id, date_from, date_to)
    prev_sessions = get_sessions(db, user_id, prev_from, prev_to)

    cur_days = get_unique_training_days(db, user_id, date_from, date_to)
    prev_days = get_unique_training_days(db, user_id, prev_from, prev_to)

    cur_sets = get_total_sets(db, user_id, date_from, date_to)
    prev_sets = get_total_sets(db, user_id, prev_from, prev_to)

    cur_vol = get_total_volume(db, user_id, date_from, date_to)
    prev_vol = get_total_volume(db, user_id, prev_from, prev_to)

    def pct_change(cur: float, prev: float) -> Optional[float]:
        if prev <= 0:
            return None
        return round(((cur - prev) / prev) * 100.0, 1)

    return {
        "previous_period": {
            "from_date": prev_from,
            "to_date": prev_to,
        },
        "sessions": {"current": cur_sessions, "previous": prev_sessions, "delta": cur_sessions - prev_sessions},
        "unique_training_days": {"current": cur_days, "previous": prev_days, "delta": cur_days - prev_days},
        "total_sets": {"current": cur_sets, "previous": prev_sets, "delta": cur_sets - prev_sets},
        "total_volume": {
            "current": round(cur_vol, 1),
            "previous": round(prev_vol, 1),
            "delta": round(cur_vol - prev_vol, 1),
            "pct_change": pct_change(cur_vol, prev_vol),
        },
    }


# ----------------------------
# Weekly streak + last 7-day gap
# ----------------------------

def get_weekly_streak(db: Session, user_id: int, weekly_goal: int = 3) -> Dict[str, Any]:
    """
    Current consecutive ISO-week streak where workouts/week >= weekly_goal.
    ISO week is Mon-Sun.

    Complex bit:
    We count workouts per ISO week using distinct dates of workouts (so multiple workouts in
    the same day don't inflate the count). If you want 'sessions' instead of 'days', remove distinct.
    """
    workout_dates = (
        db.query(models.WorkoutLog.date)
        .filter(models.WorkoutLog.user_id == user_id)
        .distinct()
        .all()
    )
    dates = sorted([row[0] for row in workout_dates])

    if not dates:
        return {"weekly_goal": weekly_goal, "current_weekly_streak": 0}

    counts: Dict[Tuple[int, int], int] = {}
    for d in dates:
        iso_year, iso_week, _ = d.isocalendar()
        counts[(iso_year, iso_week)] = counts.get((iso_year, iso_week), 0) + 1

    today = date.today()
    key = (today.isocalendar().year, today.isocalendar().week)

    streak = 0
    while True:
        if counts.get(key, 0) >= weekly_goal:
            streak += 1
        else:
            break

        iso_year, iso_week = key
        monday = date.fromisocalendar(iso_year, iso_week, 1)
        prev_monday = monday - timedelta(days=7)
        key = (prev_monday.isocalendar().year, prev_monday.isocalendar().week)

    return {"weekly_goal": weekly_goal, "current_weekly_streak": streak}


def get_last_7_day_gap(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Most recent 7-day window with NO workout logged (based on distinct workout dates).

    Returns:
      - last_gap_start_date
      - last_gap_end_date
    If none exists, returns nulls.

    Complex bit:
    We scan gaps between workout dates, and also between last workout date and today.
    """
    workout_dates = (
        db.query(models.WorkoutLog.date)
        .filter(models.WorkoutLog.user_id == user_id)
        .distinct()
        .order_by(models.WorkoutLog.date.asc())
        .all()
    )
    dates: List[date] = [row[0] for row in workout_dates]

    today = date.today()

    if not dates:
        # If user never worked out, "last 7 days ending today" is a reasonable interpretation
        start = today - timedelta(days=6)
        return {"last_gap_start_date": start, "last_gap_end_date": today}

    last_gap_start: Optional[date] = None
    last_gap_end: Optional[date] = None

    # gaps between consecutive workout days
    for i in range(len(dates) - 1):
        a = dates[i]
        b = dates[i + 1]
        gap_days = (b - a).days - 1
        if gap_days >= 7:
            start = a + timedelta(days=1)
            end = start + timedelta(days=6)
            last_gap_start, last_gap_end = start, end

    # gap from last workout to today
    gap_after_last = (today - dates[-1]).days
    if gap_after_last >= 7:
        start = dates[-1] + timedelta(days=1)
        end = start + timedelta(days=6)
        last_gap_start, last_gap_end = start, end

    return {"last_gap_start_date": last_gap_start, "last_gap_end_date": last_gap_end}


# ----------------------------
# Main "facts builder"
# ----------------------------

def build_weekly_facts(
    db: Session,
    user_id: int,
    date_from: date,
    date_to: date,
    *,
    weekly_goal: int = 3,
    top_prs_count: int = 3,
    e1rm_formula: E1RMFormula = "epley",
    max_reps_for_e1rm: int = 12,
) -> Dict[str, Any]:
    """
    This is the one function your router calls.

    It returns a single JSON-friendly dict you can:
      - return directly (debug endpoint)
      - store in SummaryLog.facts_json
      - feed into an LLM to generate summary text

    You can expand this over time with:
      - per muscle group volume
      - top exercises trained
      - longest streak ever
      - etc.
    """
    ensure_user(db, user_id)

    sessions = get_sessions(db, user_id, date_from, date_to)
    unique_days = get_unique_training_days(db, user_id, date_from, date_to)
    total_sets = get_total_sets(db, user_id, date_from, date_to)
    total_volume = get_total_volume(db, user_id, date_from, date_to)

    prs_all = get_prs(
    db,
    user_id,
    date_from,
    date_to,
    e1rm_formula=e1rm_formula,
    max_reps_for_e1rm=max_reps_for_e1rm,
    )

    prs = _top_prs(prs_all, n=top_prs_count)


    improvements = get_improvements_vs_previous_period(db, user_id, date_from, date_to)
    streak = get_weekly_streak(db, user_id, weekly_goal=weekly_goal)
    last_gap = get_last_7_day_gap(db, user_id)

    return {
        "user_id": user_id,
        "period": {
            "from_date": date_from,
            "to_date": date_to,
        },
        "sessions": sessions,
        "unique_training_days": unique_days,
        "total_sets": total_sets,
        "total_volume": round(total_volume, 1),
        "prs": prs,
        "improvements_vs_previous_period": improvements,
        "weekly_streak": streak,
        "last_7_day_gap": last_gap,
    }
