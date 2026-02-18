from datetime import date
from sqlalchemy.orm import Session
from app import models


def seed_users(db: Session) -> None:
    goals = db.query(models.Goal).all()
    goal_by_name = {g.name: g.id for g in goals}

    users = [
        models.User(
            username="cayden01",
            years_experience=3,
            goal_id=goal_by_name["General Fitness"],
            target_days_per_week=4,
            account_created=date.today(),
        ),
        models.User(
            username="alice01",
            years_experience=1,
            goal_id=goal_by_name["Fat Loss"],
            target_days_per_week=5,
            account_created=date.today(),
        ),
        models.User(
            username="bobby01",
            years_experience=6,
            goal_id=goal_by_name["Strength"],
            target_days_per_week=3,
            account_created=date.today(),
        ),
    ]

    db.add_all(users)
    db.commit()
    print("✅ Users seeded (with goal_id).")
