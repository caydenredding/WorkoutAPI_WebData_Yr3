from datetime import date
from sqlalchemy.orm import Session
from app import models


def seed_users(db: Session) -> None:
    """
    Assumes goals are seeded and tables are empty.
    """
    goals = db.query(models.Goal).order_by(models.Goal.id.asc()).all()
    goal_by_name = {g.name: g.id for g in goals}

    users = [
        models.User(
            username="cayden",
            years_experience=3,
            goal_id=goal_by_name.get("General Fitness"),
            account_created=date.today(),
        ),
        models.User(
            username="GymBro123",
            years_experience=1,
            goal_id=goal_by_name.get("Hypertrophy"),
            account_created=date.today(),
        ),
        models.User(
            username="FitChick",
            years_experience=6,
            goal_id=goal_by_name.get("Strength"),
            account_created=date.today(),
        ),
    ]

    db.add_all(users)
    db.commit()
    print("✅ Users seeded.")
