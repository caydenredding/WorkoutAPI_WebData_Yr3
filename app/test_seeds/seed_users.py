from datetime import date
from sqlalchemy.orm import Session

from app import models
from app.security import hash_password


def seed_users(db: Session) -> None:
    goals = db.query(models.Goal).all()
    goal_by_name = {g.name: g.id for g in goals}

    # IMPORTANT: change these if you want
    users = [
        models.User(
            username="admin01",
            hashed_password=hash_password("AdminPass123!"),
            role="admin",
            years_experience=10,
            goal_id=goal_by_name.get("General Fitness", 3),
            target_days_per_week=4,
            account_created=date.today(),
        ),
        models.User(
            username="cayden01",
            hashed_password=hash_password("UserPass123!"),
            role="user",
            years_experience=3,
            goal_id=goal_by_name.get("General Fitness", 3),
            target_days_per_week=4,
            account_created=date.today(),
        ),
        models.User(
            username="alice01",
            hashed_password=hash_password("UserPass123!"),
            role="user",
            years_experience=1,
            goal_id=goal_by_name.get("Fat Loss", 3),
            target_days_per_week=5,
            account_created=date.today(),
        ),
        models.User(
            username="bobby01",
            hashed_password=hash_password("UserPass123!"),
            role="user",
            years_experience=6,
            goal_id=goal_by_name.get("Strength", 3),
            target_days_per_week=3,
            account_created=date.today(),
        ),
    ]

    # Idempotent-ish: skip usernames that already exist
    existing = {u.username for u in db.query(models.User.username).all()}
    to_add = [u for u in users if u.username not in existing]

    if not to_add:
        print("ℹ️ Users already seeded. Nothing to do.")
        return

    db.add_all(to_add)
    db.commit()
    print(f"✅ Users seeded: {', '.join([u.username for u in to_add])}")