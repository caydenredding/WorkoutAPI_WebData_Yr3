import json
from sqlalchemy.orm import Session
from models import Exercise
from database import SessionLocal, engine, Base

JSON_FILE = "../data/exercises.json"
FILTER_MUSCLES = ["chest", "back", "legs", "shoulders", "arms", "abs"]

# Create Table if doesnt exist
Base.metadata.create_all(bind=engine)

def seed_exercises():
    db: Session = SessionLocal()
    # Step 2: Only seed if table is empty
    if db.query(Exercise).count() == 0:
        with open(JSON_FILE, "r") as f:
            data = json.load(f)
            
        # Extract the excerise list
        data = data["exercises"]
        exercises_to_insert = []
        for ex in data:
            # This creates string csvs of the list of primary and secondary muscles
            primary_list = [m.lower() for m in ex.get("primary_muscles", [])]
            secondary_list = [m.lower() for m in ex.get("secondary_muscles", [])]

            if FILTER_MUSCLES and not any(m in FILTER_MUSCLES for m in primary_list + secondary_list):
                continue

            primary = ",".join(primary_list)
            secondary = ",".join(secondary_list)
            
            exercises_to_insert.append(
                Exercise(
                    name=ex.get("name", ""),
                    primary_muscle=primary,
                    secondary_muscle=secondary,
                    equipment=",".join(ex.get("equipment", []))
                )
            )
        db.add_all(exercises_to_insert)
        db.commit()
        print(f"Inserted {len(exercises_to_insert)} exercises.")
    else:
        print("Exercises table already populated, skipping seeding.")
    db.close()

if __name__ == "__main__":
    seed_exercises()