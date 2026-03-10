from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Float, desc

from app.database import get_db
from app import models

from app.security import get_current_user, require_api_key

from app.schemas.users import (
    UserOut,
    UserUpdate,
    WeighInCreate,
    WeighInOut,
    WeighInListOut,
    WeighInUpdate,
)
from app.schemas.training import (
    WorkoutCreate,
    WorkoutOut,
    WorkoutUpdate,
    ExerciseLogCreate,
    ExerciseLogOut,
    ExerciseLogUpdate,
    SetCreate,
    SetOut,
    SetUpdate,
)
from app.schemas.analytics import (
    WeeklyStreakOut,
    WorkoutsLast30DaysOut,
    LastSevenDayGapOut,
    ExerciseMaxSetVolumeOut,
    ExerciseBest1RMOut,
)
from app.schemas.insights import InsightsResponse, SignalsResponse
from app.services.insights.insights import get_insights_response, get_signals_response

router = APIRouter()


# ----------------------------
# Helpers: ownership checks
# ----------------------------

def _get_owned_workout_or_404(db: Session, *, workout_id: int, user_id: int) -> models.WorkoutLog:
    w = db.query(models.WorkoutLog).filter(models.WorkoutLog.id == workout_id).first()
    if not w or w.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    return w


def _get_owned_exercise_log_or_404(db: Session, *, exercise_log_id: int, user_id: int) -> models.ExerciseLog:
    log = (
        db.query(models.ExerciseLog)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.ExerciseLog.id == exercise_log_id)
        .options(
            joinedload(models.ExerciseLog.exercise)
            .joinedload(models.Exercise.primary_muscles),
            joinedload(models.ExerciseLog.exercise)
            .joinedload(models.Exercise.secondary_muscles),
            joinedload(models.ExerciseLog.exercise)
            .joinedload(models.Exercise.equipment),
        )
        .first()
    )
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise log not found")

    if log.workout.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise log not found")

    return log


def _get_owned_set_or_404(db: Session, *, set_id: int, user_id: int) -> models.SetLog:
    s = (
        db.query(models.SetLog)
        .join(models.ExerciseLog, models.ExerciseLog.id == models.SetLog.exercise_log_id)
        .join(models.WorkoutLog, models.WorkoutLog.id == models.ExerciseLog.workout_id)
        .filter(models.SetLog.id == set_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")

    # Verify ownership via joins
    # (We re-fetch minimal info to avoid relying on lazy relationships.)
    owner = (
        db.query(models.WorkoutLog.user_id)
        .join(models.ExerciseLog, models.ExerciseLog.workout_id == models.WorkoutLog.id)
        .join(models.SetLog, models.SetLog.exercise_log_id == models.ExerciseLog.id)
        .filter(models.SetLog.id == set_id)
        .scalar()
    )
    if owner != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")

    return s


def _get_owned_weigh_in_or_404(db: Session, *, weigh_in_id: int, user_id: int) -> models.WeighIn:
    w = db.query(models.WeighIn).filter(models.WeighIn.id == weigh_in_id).first()
    if not w or w.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weigh-in not found")
    return w


# ----------------------------
# Profile
# ----------------------------

@router.get("/", response_model=UserOut, status_code=status.HTTP_200_OK)
def me_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch("/", response_model=UserOut, status_code=status.HTTP_200_OK)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    # users cannot change role via /me
    if "role" in update_data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot change role")

    # validate goal_id if set
    if "goal_id" in update_data and update_data["goal_id"] is not None:
        goal_exists = db.query(models.Goal.id).filter(models.Goal.id == update_data["goal_id"]).first()
        if not goal_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid goal_id")

    # validate target_days_per_week
    if "target_days_per_week" in update_data and update_data["target_days_per_week"] is not None:
        if update_data["target_days_per_week"] < 1 or update_data["target_days_per_week"] > 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_days_per_week must be between 1 and 7",
            )

    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


# ----------------------------
# Workouts (user-scoped)
# ----------------------------

@router.get("/workouts", response_model=List[WorkoutOut], status_code=status.HTTP_200_OK)
def list_my_workouts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return (
        db.query(models.WorkoutLog)
        .filter(models.WorkoutLog.user_id == current_user.id)
        .order_by(models.WorkoutLog.date.desc(), models.WorkoutLog.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/workouts/{workout_id}", response_model=WorkoutOut, status_code=status.HTTP_200_OK)
def get_my_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_workout_or_404(db, workout_id=workout_id, user_id=current_user.id)


@router.post("/workouts", response_model=WorkoutOut, status_code=status.HTTP_201_CREATED)
def create_my_workout(
    payload: WorkoutCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    w = models.WorkoutLog(user_id=current_user.id, date=payload.date)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


@router.patch("/workouts/{workout_id}", response_model=WorkoutOut, status_code=status.HTTP_200_OK)
def update_my_workout(
    workout_id: int,
    payload: WorkoutUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    workout = _get_owned_workout_or_404(db, workout_id=workout_id, user_id=current_user.id)

    for field, value in update_data.items():
        setattr(workout, field, value)

    db.commit()
    db.refresh(workout)
    return workout


@router.delete("/workouts/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    workout = _get_owned_workout_or_404(db, workout_id=workout_id, user_id=current_user.id)

    # Will cascade delete ExerciseLog + SetLog because of your relationship config
    db.delete(workout)
    db.commit()
    return


# ----------------------------
# Exercise logs (user-scoped)
# Mirrors training/exercise_logs endpoints but scoped to current_user
# ----------------------------

@router.get("/workouts/{workout_id}/exercise-logs", response_model=List[ExerciseLogOut], status_code=status.HTTP_200_OK)
def list_my_exercise_logs_for_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    # Ensure workout belongs to user
    _ = _get_owned_workout_or_404(db, workout_id=workout_id, user_id=current_user.id)

    logs = (
        db.query(models.ExerciseLog)
        .options(
            joinedload(models.ExerciseLog.exercise)
            .joinedload(models.Exercise.primary_muscles),
            joinedload(models.ExerciseLog.exercise)
            .joinedload(models.Exercise.secondary_muscles),
            joinedload(models.ExerciseLog.exercise)
            .joinedload(models.Exercise.equipment),
        )
        .filter(models.ExerciseLog.workout_id == workout_id)
        .order_by(models.ExerciseLog.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return logs


@router.post("/workouts/{workout_id}/exercise-logs", response_model=ExerciseLogOut, status_code=status.HTTP_201_CREATED)
def create_my_exercise_log(
    workout_id: int,
    payload: ExerciseLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Ensure workout belongs to user
    _ = _get_owned_workout_or_404(db, workout_id=workout_id, user_id=current_user.id)

    exercise = db.query(models.Exercise).filter(models.Exercise.id == payload.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    log = models.ExerciseLog(workout_id=workout_id, exercise_id=payload.exercise_id)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/exercise-logs/{exercise_log_id}", response_model=ExerciseLogOut, status_code=status.HTTP_200_OK)
def get_my_exercise_log(
    exercise_log_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_exercise_log_or_404(db, exercise_log_id=exercise_log_id, user_id=current_user.id)


@router.patch("/exercise-logs/{exercise_log_id}", response_model=ExerciseLogOut, status_code=status.HTTP_200_OK)
def update_my_exercise_log(
    exercise_log_id: int,
    payload: ExerciseLogUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    log = _get_owned_exercise_log_or_404(db, exercise_log_id=exercise_log_id, user_id=current_user.id)

    for field, value in update_data.items():
        setattr(log, field, value)

    db.commit()
    db.refresh(log)
    return log


@router.delete("/exercise-logs/{exercise_log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_exercise_log(
    exercise_log_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    log = _get_owned_exercise_log_or_404(db, exercise_log_id=exercise_log_id, user_id=current_user.id)
    # Cascades delete sets because ExerciseLog.sets relationship has delete-orphan
    db.delete(log)
    db.commit()
    return


# ----------------------------
# Sets (user-scoped)
# ----------------------------

@router.get("/exercise-logs/{exercise_log_id}/sets", response_model=List[SetOut], status_code=status.HTTP_200_OK)
def list_my_sets(
    exercise_log_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _ = _get_owned_exercise_log_or_404(db, exercise_log_id=exercise_log_id, user_id=current_user.id)

    return (
        db.query(models.SetLog)
        .filter(models.SetLog.exercise_log_id == exercise_log_id)
        .order_by(models.SetLog.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/exercise-logs/{exercise_log_id}/sets", response_model=SetOut, status_code=status.HTTP_201_CREATED)
def create_my_set(
    exercise_log_id: int,
    payload: SetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ = _get_owned_exercise_log_or_404(db, exercise_log_id=exercise_log_id, user_id=current_user.id)

    s = models.SetLog(
        exercise_log_id=exercise_log_id,
        reps=payload.reps,
        weight=payload.weight,
        rir=payload.rir,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/sets/{set_id}", response_model=SetOut, status_code=status.HTTP_200_OK)
def get_my_set(
    set_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_set_or_404(db, set_id=set_id, user_id=current_user.id)


@router.patch("/sets/{set_id}", response_model=SetOut, status_code=status.HTTP_200_OK)
def update_my_set(
    set_id: int,
    payload: SetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    s = _get_owned_set_or_404(db, set_id=set_id, user_id=current_user.id)

    for field, value in update_data.items():
        setattr(s, field, value)

    db.commit()
    db.refresh(s)
    return s


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_set(
    set_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    s = _get_owned_set_or_404(db, set_id=set_id, user_id=current_user.id)
    db.delete(s)
    db.commit()
    return


# ----------------------------
# Weigh-ins (user-scoped)
# ----------------------------

@router.get("/weigh-ins", response_model=WeighInListOut, status_code=status.HTTP_200_OK)
def list_my_weigh_ins(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: int = Query(5, ge=1, le=100),
):
    weigh_ins = (
        db.query(models.WeighIn)
        .filter(models.WeighIn.user_id == current_user.id)
        .order_by(models.WeighIn.date.desc())
        .limit(limit)
        .all()
    )
    weigh_ins = list(reversed(weigh_ins))
    return {"user_id": current_user.id, "count": len(weigh_ins), "weigh_ins": weigh_ins}


@router.post("/weigh-ins", response_model=WeighInOut, status_code=status.HTTP_201_CREATED)
def create_my_weigh_in(
    payload: WeighInCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    weigh_in = models.WeighIn(user_id=current_user.id, weight=payload.weight, date=payload.date)
    db.add(weigh_in)
    db.commit()
    db.refresh(weigh_in)
    return weigh_in


@router.get("/weigh-ins/{weigh_in_id}", response_model=WeighInOut, status_code=status.HTTP_200_OK)
def get_my_weigh_in(
    weigh_in_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_weigh_in_or_404(db, weigh_in_id=weigh_in_id, user_id=current_user.id)


@router.patch("/weigh-ins/{weigh_in_id}", response_model=WeighInOut, status_code=status.HTTP_200_OK)
def update_my_weigh_in(
    weigh_in_id: int,
    payload: WeighInUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    w = _get_owned_weigh_in_or_404(db, weigh_in_id=weigh_in_id, user_id=current_user.id)

    for field, value in update_data.items():
        setattr(w, field, value)

    db.commit()
    db.refresh(w)
    return w


@router.delete("/weigh-ins/{weigh_in_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_weigh_in(
    weigh_in_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    w = _get_owned_weigh_in_or_404(db, weigh_in_id=weigh_in_id, user_id=current_user.id)
    db.delete(w)
    db.commit()
    return


# ----------------------------
# Analytics (user-scoped)
# ----------------------------

@router.get("/analytics/weekly-streak", response_model=WeeklyStreakOut, status_code=status.HTTP_200_OK)
def my_weekly_streak(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    weekly_goal: int = Query(3, ge=1, le=14),
):
    user_id = current_user.id

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


@router.get("/analytics/workouts-last-30-days", response_model=WorkoutsLast30DaysOut, status_code=status.HTTP_200_OK)
def my_workouts_last_30_days(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_id = current_user.id
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


@router.get("/analytics/last-week-missed", response_model=LastSevenDayGapOut, status_code=status.HTTP_200_OK)
def my_last_week_missed(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_id = current_user.id

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


@router.get(
    "/analytics/exercises/max-set-volume",
    response_model=List[ExerciseMaxSetVolumeOut],
    status_code=status.HTTP_200_OK,
)
def my_max_set_volume(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    exercise_id: Optional[int] = Query(None, ge=1),
):
    user_id = current_user.id

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
    "/analytics/exercises/best-1rm",
    response_model=List[ExerciseBest1RMOut],
    status_code=status.HTTP_200_OK,
)
def my_best_1rm(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    formula: Literal["epley", "brzycki"] = Query("epley"),
    exercise_id: Optional[int] = Query(None, ge=1),
    max_reps: int = Query(12, ge=1, le=30),
):
    user_id = current_user.id

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


# ----------------------------
# Insights + signals (requires API key)
# ----------------------------

@router.get(
    "/insights",
    response_model=InsightsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_api_key)],
)
def my_insights(
    as_of: date = Query(..., description="Evaluate state as of this date"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_insights_response(db, current_user.id, as_of)


@router.get(
    "/signals",
    response_model=SignalsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_api_key)],
)
def my_signals(
    as_of: date = Query(..., description="Evaluate state as of this date"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_signals_response(db, current_user.id, as_of)