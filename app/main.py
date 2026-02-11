from fastapi import FastAPI
from app.database import engine, Base
from app import models
from app.routers import users, exercises, workouts, exercise_logs, muscles, equipment, sets

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Workout Tracker API")

app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(exercises.router, prefix="/exercises", tags=["Exercises"])
app.include_router(workouts.router, tags=["Workouts"])
app.include_router(exercise_logs.router, tags=["Exercise Logs"])
app.include_router(muscles.router, prefix="/muscles", tags=["Muscles"])
app.include_router(equipment.router, prefix="/equipment", tags=["Equipment"])
app.include_router(sets.router, tags=["Sets"])


@app.get("/")
def root():
    return {"status": "API running"}
