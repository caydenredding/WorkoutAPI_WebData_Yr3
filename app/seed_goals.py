# seed_goals.py

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models

# Hardcoded goal names
GOALS = [
    "Strength",
    "Hypertrophy",
    "General Fitness",
    "Fat Loss",
    "Endurance",
    "Athletic Performance",
]


def seed_goals():
    db: Session = SessionLocal()

    try:
        existing_goal_names = {
            goal.name for goal in db.query(models.Goal).all()
        }

        created_count = 0

        for goal_name in GOALS:
            if goal_name not in existing_goal_names:
                db.add(models.Goal(name=goal_name))
                created_count += 1

        if created_count > 0:
            db.commit()
            print(f"✅ Seeded {created_count} new goals.")
        else:
            print("ℹ️ Goals already seeded. Nothing to do.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_goals()
