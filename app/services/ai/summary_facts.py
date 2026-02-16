from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import Float, case, cast, desc, func
from sqlalchemy.orm import Session

from app import models


# ----------------------------
# Small helpers
# ----------------------------

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _pct_change(current: float, previous: float) -> Optional[float]:
    # Avoid division-by-zero and meaningless % changes.
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100.0, 1)


def ensure_user_exists(db: Session, user_id: int) -> None:
    exists = db.query(models.User.id).filter(models.User.id == user_id).first()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


# ----------------------------
# New: user goal + recent weigh-ins
# ----------------------------

def get_user_goal(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Returns user's goal info. If no goal_id, returns {"goal_id": None, "goal_name": None}.
    """
    row = (
        db.query(models.User.goal_id, models.Goal.name)
        .outerjoin(models.Goal, models.Goal.id == models.User.goal_id)
        .filter(models.User.id == user_id)
        .first()
    )

    # ensure_user_exists() should already have run, but keep safe.
    if not row:
        return {"goal_id": None, "goal_name": None}

    goal_id, goal_name = row
    return {"goal_id": goal_id, "goal_name": goal_name}


def get_recent_weigh_ins(db: Session, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Returns last `limit` weigh-ins (chronological order). If none, returns [].

    Complex bit: We query DESC to get the newest quickly, then reverse to make frontend charts nicer.
    """
    rows = (
        db.query(models.WeighIn)
        .filter(models.WeighIn.user_id == user_id)
        .order_by(models.WeighIn.date.desc(), models.WeighIn.id.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return [{"id": r.id, "date": r.date, "weight": float(r.weight)} for r in rows]


# ----------------------------
# Existing: core period metrics
# ----------------------------

def get_sessions_in_period(db: Session, user_id: int, date_from: date, date_to: date) -> int:
    return int(
        db.query(func.count(models.WorkoutLog.id))
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0
    )


def get_unique_training_days(db: Session, user_id: int, date_from: date, date_to: date) -> int:
    # DISTINCT workout dates for that user in range
    return int(
        db.query(func.count(func.distinct(models.WorkoutLog.date)))
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0
    )


def get_total_sets_in_period(db: Session, user_id: int, date_from: date, date_to: date) -> int:
    # Join through workout -> exercise log -> set log
    return int(
        db.query(func.count(models.SetLog.id))
        .join(models.ExerciseLog, models.ExerciseLog.id == models.SetLog.exercise_log_id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0
    )


def get_total_volume_in_period(db: Session, user_id: int, date_from: date, date_to: date) -> float:
    # volume = reps * weight
    volume_expr = cast(models.SetLog.reps, Float) * cast(models.SetLog.weight, Float)

    total = (
        db.query(func.coalesce(func.sum(volume_expr), 0.0))
        .join(models.ExerciseLog, models.ExerciseLog.id == models.SetLog.exercise_log_id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
    )
    return float(total or 0.0)


# ----------------------------
# New: RIR metrics
# ----------------------------

def get_rir_summary(db: Session, user_id: int, date_from: date, date_to: date) -> Dict[str, Any]:
    """
    Summarise RIR for sets in the period.

    Notes:
    - rir is optional -> many rows may have NULL; we compute stats only on non-null rows.
    - "hard sets" is a useful derived metric: sets with rir <= 2 (common coaching heuristic).
    """
    # Base query for sets in period for the user
    base = (
        db.query(models.SetLog.rir)
        .join(models.ExerciseLog, models.ExerciseLog.id == models.SetLog.exercise_log_id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
    )

    # Count all sets in period (even those without RIR logged)
    total_sets = int(
        db.query(func.count(models.SetLog.id))
        .join(models.ExerciseLog, models.ExerciseLog.id == models.SetLog.exercise_log_id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date >= date_from)
        .filter(models.WorkoutLog.date <= date_to)
        .scalar()
        or 0
    )

    # Count sets where RIR is present
    logged_sets = int(
        base.filter(models.SetLog.rir.isnot(None))
        .with_entities(func.count())
        .scalar()
        or 0
    )

    if logged_sets == 0:
        return {
            "total_sets": total_sets,
            "rir_logged_sets": 0,
            "rir_logged_pct": 0.0,
            "avg_rir": None,
            "min_rir": None,
            "max_rir": None,
            "hard_sets_rir_le_2": 0,
        }

    avg_rir = (
        base.filter(models.SetLog.rir.isnot(None))
        .with_entities(func.avg(cast(models.SetLog.rir, Float)))
        .scalar()
    )
    min_rir = (
        base.filter(models.SetLog.rir.isnot(None))
        .with_entities(func.min(models.SetLog.rir))
        .scalar()
    )
    max_rir = (
        base.filter(models.SetLog.rir.isnot(None))
        .with_entities(func.max(models.SetLog.rir))
        .scalar()
    )

    # hard sets <= 2
    hard_sets = int(
        base.filter(models.SetLog.rir.isnot(None))
        .filter(models.SetLog.rir <= 2)
        .with_entities(func.count())
        .scalar()
        or 0
    )

    return {
        "total_sets": total_sets,
        "rir_logged_sets": logged_sets,
        "rir_logged_pct": round((logged_sets / max(total_sets, 1)) * 100.0, 1),
        "avg_rir": round(float(avg_rir), 2) if avg_rir is not None else None,
        "min_rir": int(min_rir) if min_rir is not None else None,
        "max_rir": int(max_rir) if max_rir is not None else None,
        "hard_sets_rir_le_2": hard_sets,
    }


# ----------------------------
# PR detection (kept similar to before)
# ----------------------------

def _compute_e1rm(weight: float, reps: int, formula: Literal["epley", "brzycki"]) -> float:
    reps_f = float(reps)
    w = float(weight)
    if formula == "epley":
        return w * (1.0 + reps_f / 30.0)
    # brzycki
    return w * 36.0 / (37.0 - reps_f)


def _top_prs(prs: List[Dict[str, Any]], n: int = 3) -> List[Dict[str, Any]]:
    """
    Top N PRs ranked by improvement amount (new - previous).
    If previous is None, treat improvement as new.
    """
    def improvement(pr: Dict[str, Any]) -> float:
        new_val = _safe_float(pr.get("new"))
        prev_val = pr.get("previous")
        if prev_val is None:
            return new_val
        return new_val - _safe_float(prev_val)

    return sorted(prs, key=improvement, reverse=True)[:n]


def get_prs(
    db: Session,
    user_id: int,
    date_from: date,
    date_to: date,
    *,
    e1rm_formula: Literal["epley", "brzycki"] = "epley",
    max_reps_for_e1rm: int = 12,
) -> List[Dict[str, Any]]:
    """
    Detect PRs hit within period for each exercise for:
      - best e1RM
      - max set volume

    Complex bit:
    We compare "best within period" vs "best strictly before period".
    If period best > previous best -> PR event.
    """

    # --- Base query for sets with exercise + workout date
    volume_expr = cast(models.SetLog.reps, Float) * cast(models.SetLog.weight, Float)

    # e1rm expression in SQL (matches _compute_e1rm)
    reps_f = cast(models.SetLog.reps, Float)
    w = cast(models.SetLog.weight, Float)
    if e1rm_formula == "epley":
        e1rm_expr = w * (1.0 + (reps_f / 30.0))
    else:
        e1rm_expr = w * 36.0 / (37.0 - reps_f)

    # Bests in the period per exercise
    period_bests = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            models.Exercise.name.label("exercise_name"),
            func.max(volume_expr).label("period_max_volume"),
            func.max(
                case(
                    (models.SetLog.reps <= max_reps_for_e1rm, e1rm_expr),
                    else_=None,
                )
            ).label("period_best_e1rm"),
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

    # Bests before the period per exercise
    prev_bests = (
        db.query(
            models.Exercise.id.label("exercise_id"),
            func.max(volume_expr).label("prev_max_volume"),
            func.max(
                case(
                    (models.SetLog.reps <= max_reps_for_e1rm, e1rm_expr),
                    else_=None,
                )
            ).label("prev_best_e1rm"),
        )
        .join(models.ExerciseLog, models.ExerciseLog.exercise_id == models.Exercise.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.WorkoutLog.user_id == user_id)
        .filter(models.WorkoutLog.date < date_from)
        .group_by(models.Exercise.id)
        .all()
    )

    prev_map = {r.exercise_id: r for r in prev_bests}

    prs: List[Dict[str, Any]] = []

    for r in period_bests:
        prev = prev_map.get(r.exercise_id)

        # max set volume PR
        if r.period_max_volume is not None:
            prev_val = float(prev.prev_max_volume) if (prev and prev.prev_max_volume is not None) else None
            new_val = float(r.period_max_volume)
            if prev_val is None or new_val > prev_val:
                prs.append(
                    {
                        "exercise_id": r.exercise_id,
                        "exercise_name": r.exercise_name,
                        "type": "max_set_volume",
                        "new": round(new_val, 1),
                        "previous": round(prev_val, 1) if prev_val is not None else None,
                    }
                )

        # e1RM PR
        if r.period_best_e1rm is not None:
            prev_val = float(prev.prev_best_e1rm) if (prev and prev.prev_best_e1rm is not None) else None
            new_val = float(r.period_best_e1rm)
            if prev_val is None or new_val > prev_val:
                prs.append(
                    {
                        "exercise_id": r.exercise_id,
                        "exercise_name": r.exercise_name,
                        "type": "e1rm",
                        "formula": e1rm_formula,
                        "new": round(new_val, 1),
                        "previous": round(prev_val, 1) if prev_val is not None else None,
                    }
                )

    return prs


# ----------------------------
# Existing: streak + last 7-day gap
# ----------------------------

def get_weekly_streak(db: Session, user_id: int, weekly_goal: int = 3) -> Dict[str, Any]:
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
    current_key = (today.isocalendar().year, today.isocalendar().week)

    # If current week doesn't meet goal, start from previous week (so it doesn't "break" the streak prematurely)
    if counts.get(current_key, 0) >= weekly_goal:
        key = current_key
    else:
        monday = date.fromisocalendar(current_key[0], current_key[1], 1)
        prev_monday = monday - timedelta(days=7)
        key = (prev_monday.isocalendar().year, prev_monday.isocalendar().week)

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
    workout_dates = (
        db.query(models.WorkoutLog.date)
        .filter(models.WorkoutLog.user_id == user_id)
        .distinct()
        .order_by(models.WorkoutLog.date.asc())
        .all()
    )
    dates = [row[0] for row in workout_dates]

    if not dates:
        today = date.today()
        start = today - timedelta(days=6)
        return {"last_gap_start_date": start, "last_gap_end_date": today}

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

    today = date.today()
    gap_after_last = (today - dates[-1]).days
    if gap_after_last >= 7:
        start = dates[-1] + timedelta(days=1)
        end = start + timedelta(days=6)
        last_gap_start, last_gap_end = start, end

    return {"last_gap_start_date": last_gap_start, "last_gap_end_date": last_gap_end}


# ----------------------------
# Improvements vs previous period (extended with RIR)
# ----------------------------

def _metric_comparison(current: float, previous: float) -> Dict[str, Any]:
    delta = round(current - previous, 1)
    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "pct_change": _pct_change(current, previous),
    }


def get_improvements_vs_previous_period(
    db: Session,
    user_id: int,
    date_from: date,
    date_to: date,
) -> Dict[str, Any]:
    """
    Compares this period vs the previous period of equal length.
    Now includes avg_rir and hard_sets comparisons (when RIR exists).
    """
    days = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=days - 1)

    current_sessions = get_sessions_in_period(db, user_id, date_from, date_to)
    prev_sessions = get_sessions_in_period(db, user_id, prev_from, prev_to)

    current_days = get_unique_training_days(db, user_id, date_from, date_to)
    prev_days = get_unique_training_days(db, user_id, prev_from, prev_to)

    current_sets = get_total_sets_in_period(db, user_id, date_from, date_to)
    prev_sets = get_total_sets_in_period(db, user_id, prev_from, prev_to)

    current_vol = round(get_total_volume_in_period(db, user_id, date_from, date_to), 1)
    prev_vol = round(get_total_volume_in_period(db, user_id, prev_from, prev_to), 1)

    current_rir = get_rir_summary(db, user_id, date_from, date_to)
    prev_rir = get_rir_summary(db, user_id, prev_from, prev_to)

    # Compare only when avg_rir exists for both periods
    avg_rir_comp = None
    if current_rir["avg_rir"] is not None and prev_rir["avg_rir"] is not None:
        avg_rir_comp = _metric_comparison(float(current_rir["avg_rir"]), float(prev_rir["avg_rir"]))

    hard_sets_comp = _metric_comparison(
        float(current_rir["hard_sets_rir_le_2"]),
        float(prev_rir["hard_sets_rir_le_2"]),
    )

    return {
        "previous_period": {"from_date": prev_from, "to_date": prev_to},
        "sessions": _metric_comparison(float(current_sessions), float(prev_sessions)),
        "unique_training_days": _metric_comparison(float(current_days), float(prev_days)),
        "total_sets": _metric_comparison(float(current_sets), float(prev_sets)),
        "total_volume": _metric_comparison(float(current_vol), float(prev_vol)),
        "avg_rir": avg_rir_comp,
        "hard_sets_rir_le_2": hard_sets_comp,
    }


# ----------------------------
# Main facts builder (now includes goal, RIR, weigh-ins)
# ----------------------------

def build_weekly_facts(
    db: Session,
    user_id: int,
    date_from: date,
    date_to: date,
    *,
    e1rm_formula: Literal["epley", "brzycki"] = "epley",
    max_reps_for_e1rm: int = 12,
    weekly_goal: int = 3,
    pr_count = 5,
    weigh_ins_limit: int = 10,
) -> Dict[str, Any]:
    ensure_user_exists(db, user_id)

    sessions = get_sessions_in_period(db, user_id, date_from, date_to)
    unique_days = get_unique_training_days(db, user_id, date_from, date_to)
    total_sets = get_total_sets_in_period(db, user_id, date_from, date_to)
    total_volume = get_total_volume_in_period(db, user_id, date_from, date_to)

    # PRs: return only top 3
    prs_all = get_prs(
        db,
        user_id,
        date_from,
        date_to,
        e1rm_formula=e1rm_formula,
        max_reps_for_e1rm=max_reps_for_e1rm,
    )
    prs = _top_prs(prs_all, n=pr_count)

    # New: goal, RIR summary, weigh-ins
    goal = get_user_goal(db, user_id)
    rir_summary = get_rir_summary(db, user_id, date_from, date_to)
    recent_weigh_ins = get_recent_weigh_ins(db, user_id, limit=weigh_ins_limit)

    improvements = get_improvements_vs_previous_period(db, user_id, date_from, date_to)
    weekly_streak = get_weekly_streak(db, user_id, weekly_goal=weekly_goal)
    last_gap = get_last_7_day_gap(db, user_id)

    return {
        "user_id": user_id,
        "period": {"from_date": date_from, "to_date": date_to},

        # New: user context
        "user_goal": goal,  # {"goal_id": ..., "goal_name": ...}

        # New: weight context (last 10)
        "recent_weigh_ins": recent_weigh_ins,  # [{"id":..,"date":..,"weight":..}, ...]

        # Core period metrics
        "sessions": sessions,
        "unique_training_days": unique_days,
        "total_sets": total_sets,
        "total_volume": round(float(total_volume), 1),

        # New: RIR stats for the period
        "rir_summary": rir_summary,

        # PRs (top 3)
        "prs": prs,

        # comparisons + streak + gap
        "improvements_vs_previous_period": improvements,
        "weekly_streak": weekly_streak,
        "last_7_day_gap": last_gap,
    }
