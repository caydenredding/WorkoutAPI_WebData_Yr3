from app.database import SessionLocal
from app.test_seeds.seed_users import seed_users
from app.test_seeds.seed_workouts import seed_workouts
from app.test_seeds.truncate_workouts import truncate_workout_data


def run():
    db = SessionLocal()
    try:
        # Wipe dynamic tables so this can be re-run safely
        truncate_workout_data(db)

        # Seed reference + users + workout history
        seed_users(db)
        seed_workouts(db, weeks=12, avg_sessions_per_week=3.5, allow_gaps=True)
    finally:
        db.close()


if __name__ == "__main__":
    run()
