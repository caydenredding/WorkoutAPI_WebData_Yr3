from sqlalchemy import Column, Integer, String, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from app.database import Base

# Table of all exercises
class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Can be updated in future to be many-to-many table for muscle groups
    primary_muscle = Column(String)
    secondary_muscle = Column(String)
    equipment = Column(String)
    
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    
    workouts = relationship("WorkoutLog", back_populates="user", cascade="all, delete-orphan")

class WorkoutLog(Base):
    __tablename__ = "workout_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    
    user = relationship("User", back_populates="workouts")
    exercise_logs = relationship("ExerciseLog", back_populates="workout", cascade="all, delete-orphan")
    
class ExerciseLog(Base):
    __tablename__ = "exercise_logs"
    id = Column(Integer, primary_key=True, index=True)
    workout_id = Column(Integer, ForeignKey("workout_logs.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    sets = Column(Integer, nullable=False)
    reps = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    
    
    workout = relationship("WorkoutLog", back_populates="exercise_logs")
    exercise = relationship("Exercise")
    
    
    