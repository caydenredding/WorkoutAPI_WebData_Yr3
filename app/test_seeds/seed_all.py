from app.database import SessionLocal
from app.test_seeds.truncate_workouts import truncate_test_seed_tables
from app.test_seeds.seed_users import seed_users
from app.test_seeds.seed_weigh_ins import seed_weigh_ins
from app.test_seeds.seed_workouts import seed_workouts


def run():
    db = SessionLocal()
    try:
        truncate_test_seed_tables(db)

        seed_users(db)
        seed_weigh_ins(db, weeks=12, max_points=25)
        seed_workouts(db, weeks=12, allow_gaps=True)
    finally:
        db.close()


if __name__ == "__main__":
    run()
