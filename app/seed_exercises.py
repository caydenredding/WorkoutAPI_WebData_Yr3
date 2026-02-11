import json
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app import models

# Path from project root:
# project/
# ├─ app/
# │  └─ seed_exercises.py
# └─ data/
#    └─ exercises.json
JSON_FILE = Path("data") / "exercises.json"

FILTER_CATEGORY = "strength"  # only seed strength exercises


def norm(s: str) -> str:
    return str(s).strip().lower()


def get_or_create_muscle(db: Session, cache: dict[str, models.Muscle], name: str) -> models.Muscle:
    key = norm(name)
    if not key:
        raise ValueError("Empty muscle name")

    obj = cache.get(key)
    if obj is not None:
        return obj

    obj = db.query(models.Muscle).filter(models.Muscle.name == key).first()
    if obj is None:
        obj = models.Muscle(name=key)
        db.add(obj)
        db.flush()  # assigns id without committing
    cache[key] = obj
    return obj


def get_or_create_equipment(db: Session, cache: dict[str, models.Equipment], name: str) -> models.Equipment:
    key = norm(name)
    if not key:
        raise ValueError("Empty equipment name")

    obj = cache.get(key)
    if obj is not None:
        return obj

    obj = db.query(models.Equipment).filter(models.Equipment.name == key).first()
    if obj is None:
        obj = models.Equipment(name=key)
        db.add(obj)
        db.flush()
    cache[key] = obj
    return obj


def seed_exercises() -> None:
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    if not JSON_FILE.exists():
        raise FileNotFoundError(f"JSON file not found at: {JSON_FILE.resolve()}")

    db: Session = SessionLocal()

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        exercises_data = payload.get("exercises", [])
        equipment_list = payload.get("equipment", [])

        # ---- Build caches from DB ----
        muscle_cache: dict[str, models.Muscle] = {m.name: m for m in db.query(models.Muscle).all()}
        equipment_cache: dict[str, models.Equipment] = {e.name: e for e in db.query(models.Equipment).all()}
        existing_exercises: set[str] = {e.name for e in db.query(models.Exercise.name).all()}

        # ---- Seed equipment options (read-only reference data) ----
        # Your JSON has a top-level list of equipment strings. Seed them all.
        equipment_added = 0
        for eq in equipment_list:
            eq_key = norm(eq)
            if not eq_key:
                continue
            if eq_key not in equipment_cache:
                db.add(models.Equipment(name=eq_key))
                equipment_added += 1
        if equipment_added:
            db.flush()
            equipment_cache = {e.name: e for e in db.query(models.Equipment).all()}

        inserted = 0
        skipped_existing = 0
        skipped_category = 0
        skipped_no_primary = 0

        # ---- Seed exercises ----
        for ex in exercises_data:
            category = norm(ex.get("category", ""))
            if FILTER_CATEGORY and category != FILTER_CATEGORY:
                skipped_category += 1
                continue

            name = (ex.get("name") or "").strip()
            if not name:
                continue

            # idempotency: skip if already seeded (by exercise name)
            if name in existing_exercises:
                skipped_existing += 1
                continue

            primary_list = [norm(m) for m in ex.get("primary_muscles", []) if str(m).strip()]
            secondary_list = [norm(m) for m in ex.get("secondary_muscles", []) if str(m).strip()]
            equipment_items = [norm(e) for e in ex.get("equipment", []) if str(e).strip()]

            # Enforce: primary muscles must be >= 1
            if len(primary_list) == 0:
                skipped_no_primary += 1
                continue

            # Choose ONE equipment for now (many-to-one). We pick the first item.
            # If missing/unknown, we fall back to "other" if it exists.
            equipment_id = None
            if equipment_items:
                chosen = equipment_items[0]
                eq_obj = equipment_cache.get(chosen)
                if eq_obj is None and "other" in equipment_cache:
                    eq_obj = equipment_cache["other"]
                if eq_obj is not None:
                    equipment_id = eq_obj.id

            exercise_obj = models.Exercise(
                name=name,
                equipment_id=equipment_id,  # requires Exercise.equipment_id FK
            )

            # Attach primary muscles
            for m in primary_list:
                exercise_obj.primary_muscles.append(get_or_create_muscle(db, muscle_cache, m))

            # Attach secondary muscles (0..n)
            for m in secondary_list:
                exercise_obj.secondary_muscles.append(get_or_create_muscle(db, muscle_cache, m))

            db.add(exercise_obj)
            db.flush()

            existing_exercises.add(name)
            inserted += 1

        db.commit()

        print("✅ Seeding complete.")
        print(f"Equipment added: {equipment_added}")
        print(f"Exercises inserted: {inserted}")
        print(f"Skipped (existing): {skipped_existing}")
        print(f"Skipped (non-{FILTER_CATEGORY} category): {skipped_category}")
        print(f"Skipped (no primary muscles): {skipped_no_primary}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_exercises()
