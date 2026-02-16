import random
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app import models


def seed_weigh_ins(db: Session, weeks: int = 12, max_points: int = 25) -> None:
    """
    Seeds weigh-ins for each user.

    - Not daily (more realistic)
    - Adds a mild trend depending on goal:
        Fat Loss  -> slight downward drift
        Strength/Hypertrophy -> slight upward drift
        Otherwise -> mostly stable
    """
    users = db.query(models.User).all()
    goals = {g.id: g.name for g in db.query(models.Goal).all()}

    today = date.today()
    start = today - timedelta(weeks=weeks)

    for u in users:
        goal_name = goals.get(u.goal_id)
        # base weight
        base = random.uniform(65, 95)

        # weekly drift in kg-ish terms (tweak if you use lbs)
        if goal_name == "Fat Loss":
            weekly_drift = random.uniform(-0.35, -0.10)
        elif goal_name in ("Strength", "Hypertrophy"):
            weekly_drift = random.uniform(0.05, 0.20)
        else:
            weekly_drift = random.uniform(-0.05, 0.05)

        # choose weigh-in dates (2–max_points across the period)
        total_days = (today - start).days
        points = random.randint(max(10, max_points // 2), max_points)
        chosen_days = sorted(random.sample(range(total_days + 1), k=min(points, total_days + 1)))

        for day_offset in chosen_days:
            d = start + timedelta(days=day_offset)

            weeks_since = (d - start).days / 7.0
            trend = weekly_drift * weeks_since

            noise = random.uniform(-0.4, 0.4)  # day-to-day fluctuation
            w = round(base + trend + noise, 1)

            db.add(models.WeighIn(user_id=u.id, weight=max(w, 40.0), date=d))

    db.commit()
    print("✅ Weigh-ins seeded.")
