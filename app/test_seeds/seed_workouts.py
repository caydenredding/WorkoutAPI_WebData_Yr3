import random
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import models


# ----------------------------
# RIR sampling (optional)
# ----------------------------

def _sample_rir() -> Optional[int]:
    """
    RIR is optional.
    - ~30% not logged (None)
    - otherwise 0–5 with realistic distribution (mostly 1–3)
    """
    if random.random() < 0.30:
        return None
    return random.choices(
        population=[0, 1, 2, 3, 4, 5],
        weights=[0.08, 0.22, 0.28, 0.22, 0.14, 0.06],
        k=1,
    )[0]


# ----------------------------
# Exercise selection helpers
# ----------------------------

def _name_contains(ex: models.Exercise, keywords: List[str]) -> bool:
    n = (ex.name or "").lower()
    return any(k in n for k in keywords)


def _pick_by_keywords(exercises: List[models.Exercise], keywords: List[str], k: int) -> List[models.Exercise]:
    """
    Try to pick exercises that match name keywords. If not enough matches, fallback to random.
    """
    matches = [e for e in exercises if _name_contains(e, keywords)]
    if len(matches) >= k:
        return random.sample(matches, k=k)
    # fallback: include what we found + random rest
    remaining = [e for e in exercises if e not in matches]
    take_more = max(0, k - len(matches))
    return matches + random.sample(remaining, k=min(take_more, len(remaining)))


def _unique(seq: List[models.Exercise]) -> List[models.Exercise]:
    seen = set()
    out = []
    for e in seq:
        if e.id not in seen:
            out.append(e)
            seen.add(e.id)
    return out


# ----------------------------
# Training template generation
# ----------------------------

def _choose_split(days_per_week: int) -> List[str]:
    """
    Returns a list of day-types (strings) to cycle through.
    """
    if days_per_week <= 3:
        return ["fullA", "fullB", "fullC"][:days_per_week]
    if days_per_week == 4:
        return ["upper", "lower", "upper", "lower"]
    # 5+ days: push/pull/legs + upper/lower
    return ["push", "pull", "legs", "upper", "lower"][:days_per_week]


def _build_user_program(exercises: List[models.Exercise], days_per_week: int) -> Dict[str, Dict[str, List[models.Exercise]]]:
    """
    Build a stable program for a user:
      - mains_by_daytype: stable small set of main lifts per day type
      - accessories_pool_by_daytype: rotating pool per day type

    Complex bit:
    We use name heuristics to approximate realistic exercise selection without adding DB fields.
    If name matching is weak, we fallback to random.
    """
    day_types = _choose_split(days_per_week)

    # candidate pools by intent (name-based heuristics)
    upper_push = _pick_by_keywords(exercises, ["bench", "press", "dip"], k=10)
    upper_pull = _pick_by_keywords(exercises, ["row", "pull", "chin", "lat"], k=12)
    lower_squat = _pick_by_keywords(exercises, ["squat", "leg press", "hack", "lunge"], k=10)
    lower_hinge = _pick_by_keywords(exercises, ["deadlift", "rdl", "hinge", "good morning"], k=10)

    shoulders = _pick_by_keywords(exercises, ["shoulder", "lateral", "rear delt", "ohp", "overhead"], k=10)
    arms = _pick_by_keywords(exercises, ["curl", "tricep", "extension", "pushdown"], k=12)
    calves_core = _pick_by_keywords(exercises, ["calf", "abs", "core", "crunch", "plank"], k=10)

    # fallback: if your naming is sparse, make sure pools aren't empty
    if len(exercises) < 20:
        # tiny DB => just use everything
        upper_push = exercises
        upper_pull = exercises
        lower_squat = exercises
        lower_hinge = exercises
        shoulders = exercises
        arms = exercises
        calves_core = exercises

    mains_by_daytype: Dict[str, List[models.Exercise]] = {}
    accessories_by_daytype: Dict[str, List[models.Exercise]] = {}

    for dt in set(day_types):
        if dt == "upper":
            mains = _unique(
                _pick_by_keywords(exercises, ["bench", "press"], 1)
                + _pick_by_keywords(exercises, ["row"], 1)
                + _pick_by_keywords(exercises, ["pull", "lat"], 1)
                + _pick_by_keywords(exercises, ["overhead", "ohp"], 1)
            )
            accessory_pool = _unique(upper_pull + shoulders + arms)
        elif dt == "lower":
            mains = _unique(
                _pick_by_keywords(exercises, ["squat", "leg press", "hack"], 1)
                + _pick_by_keywords(exercises, ["deadlift", "rdl"], 1)
                + _pick_by_keywords(exercises, ["lunge"], 1)
            )
            accessory_pool = _unique(lower_squat + lower_hinge + calves_core)
        elif dt == "push":
            mains = _unique(
                _pick_by_keywords(exercises, ["bench", "press"], 1)
                + _pick_by_keywords(exercises, ["overhead", "ohp"], 1)
                + _pick_by_keywords(exercises, ["dip"], 1)
            )
            accessory_pool = _unique(upper_push + shoulders + arms)
        elif dt == "pull":
            mains = _unique(
                _pick_by_keywords(exercises, ["row"], 1)
                + _pick_by_keywords(exercises, ["pull", "lat", "chin"], 1)
                + _pick_by_keywords(exercises, ["deadlift", "rdl"], 1)
            )
            accessory_pool = _unique(upper_pull + arms + calves_core)
        elif dt == "legs":
            mains = _unique(
                _pick_by_keywords(exercises, ["squat", "leg press", "hack"], 1)
                + _pick_by_keywords(exercises, ["rdl", "deadlift"], 1)
                + _pick_by_keywords(exercises, ["lunge"], 1)
            )
            accessory_pool = _unique(lower_squat + lower_hinge + calves_core)
        else:
            # full body variants (A/B/C)
            # Use a mix of patterns
            mains = _unique(
                _pick_by_keywords(exercises, ["squat", "leg press"], 1)
                + _pick_by_keywords(exercises, ["bench", "press"], 1)
                + _pick_by_keywords(exercises, ["row", "pull"], 1)
                + _pick_by_keywords(exercises, ["deadlift", "rdl"], 1)
            )
            accessory_pool = _unique(upper_pull + upper_push + calves_core + arms)

        # ensure we have at least 3 mains
        if len(mains) < 3:
            mains = _unique(mains + random.sample(exercises, k=min(3 - len(mains), len(exercises))))

        mains_by_daytype[dt] = mains
        accessories_by_daytype[dt] = accessory_pool if accessory_pool else exercises

    return {
        "day_types": day_types,  # type: ignore[dict-item]
        "mains_by_daytype": mains_by_daytype,
        "accessories_by_daytype": accessories_by_daytype,
    }


# ----------------------------
# Progression model
# ----------------------------

def _block_multiplier(week_index: int) -> float:
    """
    4-week block:
      week 0: base
      week 1: + small
      week 2: + medium
      week 3: deload (lower)

    Complex bit:
    This is the easiest way to stop "PR every week".
    """
    mod = week_index % 4
    if mod == 0:
        return 1.00
    if mod == 1:
        return 1.02
    if mod == 2:
        return 1.04
    # deload
    return 0.92


def _session_probability(days_per_week: int) -> float:
    # Simple: user aims for days_per_week, so daily probability is that/7, slightly jittered
    return min(max((days_per_week / 7.0) + 0.02, 0.08), 0.9)


# ----------------------------
# Main seeder
# ----------------------------

def seed_workouts(
    db: Session,
    *,
    weeks: int = 12,
    default_days_per_week: int = 4,
    allow_gaps: bool = True,
) -> None:
    """
    Seeds workouts with a repeating program rhythm.

    Key differences vs your old version:
    - Users repeat main lifts week-to-week (stops constant PR spam)
    - Accessories rotate from a pool (variety without "new lift PR every session")
    - 4-week block progression + deload (more lifelike)
    - RIR sometimes logged, sometimes None
    """
    users = db.query(models.User).all()
    exercises = db.query(models.Exercise).all()

    if not exercises:
        raise RuntimeError("No exercises found. Seed exercises first.")

    today = date.today()
    start_date = today - timedelta(weeks=weeks)

    for user in users:
        # If you later store days_per_week on the user or active plan, swap here.
        days_per_week = default_days_per_week
        day_types = _choose_split(days_per_week)
        daily_p = _session_probability(days_per_week)

        program = _build_user_program(exercises, days_per_week)
        mains_by_daytype = program["mains_by_daytype"]
        accessories_by_daytype = program["accessories_by_daytype"]

        # base "strength level" scales with experience
        base = 35.0 + (user.years_experience * 10.0)

        # optional 1-week gap to test streak/gap logic
        gap_start = gap_end = None
        if allow_gaps and weeks >= 8 and random.random() < 0.6:
            gap_week = random.randint(2, weeks - 2)
            gap_start = start_date + timedelta(weeks=gap_week)
            gap_end = gap_start + timedelta(days=6)

        # cycle through the split pattern
        split_index = 0

        d = start_date
        while d <= today:
            if gap_start and gap_end and gap_start <= d <= gap_end:
                d += timedelta(days=1)
                continue

            if random.random() < daily_p:
                day_type = day_types[split_index % len(day_types)]
                split_index += 1

                # compute which training week we're in
                week_index = (d - start_date).days // 7
                mult = _block_multiplier(week_index)

                workout = models.WorkoutLog(user_id=user.id, date=d)
                db.add(workout)
                db.flush()

                # ---- Exercise selection for this session ----
                mains = mains_by_daytype.get(day_type, [])
                accessory_pool = accessories_by_daytype.get(day_type, exercises)

                # Always do most mains; accessories rotate
                mains_to_do = random.sample(mains, k=min(len(mains), random.randint(3, 4)))

                # 2–3 accessories, rotate
                accessories_to_do = random.sample(accessory_pool, k=min(len(accessory_pool), random.randint(2, 3)))

                chosen = _unique(mains_to_do + accessories_to_do)

                # ---- Log exercises + sets ----
                # Key idea:
                # - mains: slightly heavier + lower reps
                # - accessories: lighter + higher reps
                for ex in chosen:
                    ex_log = models.ExerciseLog(workout_id=workout.id, exercise_id=ex.id)
                    db.add(ex_log)
                    db.flush()

                    is_main = ex.id in {m.id for m in mains}

                    sets_n = random.randint(3, 5) if is_main else random.randint(2, 4)

                    # reps distribution depends on main vs accessory
                    if is_main:
                        reps_choices = [4, 5, 6, 8]
                    else:
                        reps_choices = [8, 10, 12, 15]

                    # per-exercise variation
                    exercise_bias = random.uniform(-6.0, 10.0)

                    # IMPORTANT:
                    # "PR gate" via limited heavy jumps:
                    # Most sessions are stable; sometimes user pushes harder.
                    push_hard = random.random() < (0.25 if is_main else 0.15)

                    for set_idx in range(sets_n):
                        reps = random.choice(reps_choices)

                        # Small within-session fatigue: later sets slightly lighter
                        fatigue = 1.0 - (0.02 * set_idx)

                        # Main lifts are heavier
                        main_factor = 1.15 if is_main else 0.95

                        # Push-hard bump (occasional)
                        push_factor = 1.03 if push_hard else 1.00

                        # Weight calculation:
                        # base * progression * type * occasional push * fatigue + bias + noise
                        weight = (
                            base
                            * mult
                            * main_factor
                            * push_factor
                            * fatigue
                            + exercise_bias
                            + random.uniform(-2.5, 5.0)
                        )

                        weight = round(max(weight, 2.5), 1)

                        db.add(
                            models.SetLog(
                                exercise_log_id=ex_log.id,
                                reps=reps,
                                weight=weight,
                                rir=_sample_rir(),
                            )
                        )

                # slow long-term improvement (very small)
                base += 0.06

            d += timedelta(days=1)

    db.commit()
    print("✅ Workouts seeded with split rhythm + rotating accessories + RIR.")
