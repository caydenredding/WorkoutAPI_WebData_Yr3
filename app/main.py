from fastapi import FastAPI
from app.database import engine, Base
from app import models
from app.routers import users, exercises, workouts

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Workout Tracker API")

app.include_router(users.router, prefix="/users", tags=["Users"])
# app.include_router(exercises.router, prefix="/exercises", tags=["Exercises"])
app.include_router(workouts.router, prefix="/workouts", tags=["Workouts"])

@app.get("/")
def root():
    return {"status": "API running"}
