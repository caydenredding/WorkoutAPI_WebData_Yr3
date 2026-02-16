import random
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app import models


def seed_workouts(
    db: Session,
    *,
    weeks: int = 12,
    avg_sessions_per_week: float = 3.5,
    allow_gaps: bool = True,
) -> None:
    """
    Random-but-realistic workout generator.

    Creates:
      WorkoutLog -> ExerciseLog -> SetLog

    Realism choices:
    - ~avg_sessions_per_week frequency
    - 4–6 exercises per session
    - 3–5 sets per exercise
    - reps mostly 5–12
    - slow progression over the date range
    - optional 1-week gap per user
    """
    users = db.query(models.User).all()
    exercises = db.query(models.Exercise).all()

    if not exercises:
        raise RuntimeError("No exercises found. Seed exercises first.")

    today = date.today()
    start_date = today - timedelta(weeks=weeks)

    daily_p = min(max(avg_sessions_per_week / 7.0, 0.05), 0.95)

    for user in users:
        base = 35.0 + (user.years_experience * 10.0)

        # pick a stable subset to repeat (more realistic than pure random each time)
        main_lifts = random.sample(exercises, k=min(10, len(exercises)))

        # optional 1-week gap
        gap_start = gap_end = None
        if allow_gaps and weeks >= 6 and random.random() < 0.7:
            gap_week = random.randint(2, weeks - 2)
            gap_start = start_date + timedelta(weeks=gap_week)
            gap_end = gap_start + timedelta(days=6)

        d = start_date
        while d <= today:
            if gap_start and gap_end and gap_start <= d <= gap_end:
                d += timedelta(days=1)
                continue

            if random.random() < daily_p:
                workout = models.WorkoutLog(user_id=user.id, date=d)
                db.add(workout)
                db.flush()

                # 4–6 exercises per workout, mostly from main_lifts
                exercise_count = random.randint(4, 6)
                chosen = []
                for _ in range(exercise_count):
                    chosen.append(random.choice(main_lifts if random.random() < 0.8 else exercises))

                # de-dup exercises in same workout
                seen = set()
                chosen_unique = []
                for ex in chosen:
                    if ex.id not in seen:
                        chosen_unique.append(ex)
                        seen.add(ex.id)

                # progression factor across the full period (gentle)
                prog = ((d - start_date).days / max((today - start_date).days, 1)) * 7.0

                for ex in chosen_unique:
                    ex_log = models.ExerciseLog(workout_id=workout.id, exercise_id=ex.id)
                    db.add(ex_log)
                    db.flush()

                    sets_n = random.randint(3, 5)
                    exercise_bias = random.uniform(-5.0, 8.0)

                    for _ in range(sets_n):
                        reps = random.choice([5, 6, 8, 8, 10, 10, 12])
                        weight = base + prog + exercise_bias + random.uniform(-3.0, 6.0)
                        weight = round(max(weight, 2.5), 1)

                        db.add(
                            models.SetLog(
                                exercise_log_id=ex_log.id,
                                reps=reps,
                                weight=weight,
                            )
                        )

                base += 0.08  # tiny improvement per workout

            d += timedelta(days=1)

    db.commit()
    print(f"✅ Workouts seeded for {len(users)} users over ~{weeks} weeks.")
