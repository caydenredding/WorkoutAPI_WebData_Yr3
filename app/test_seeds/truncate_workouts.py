from sqlalchemy import text
from sqlalchemy.orm import Session


def truncate_test_seed_tables(db: Session) -> None:
    """
    Postgres-only.

    Wipes tables that we seed so we can re-run seeds repeatedly.
    Does NOT touch exercises/muscles/equipment (catalog).
    """
    # Adjust table names if your __tablename__ differs.
    db.execute(text("TRUNCATE TABLE set_logs RESTART IDENTITY CASCADE;"))
    db.execute(text("TRUNCATE TABLE exercise_logs RESTART IDENTITY CASCADE;"))
    db.execute(text("TRUNCATE TABLE workout_logs RESTART IDENTITY CASCADE;"))
    db.execute(text("TRUNCATE TABLE weigh_ins RESTART IDENTITY CASCADE;"))
    db.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE;"))
    db.commit()
    print("🧹 Truncated goals/users/weigh_ins/workout tables (ready to reseed).")
