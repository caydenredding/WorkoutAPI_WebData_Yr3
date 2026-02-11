from sqlalchemy import Column, Integer, String, ForeignKey, Date, Float, Table
from sqlalchemy.orm import relationship
from app.database import Base

# Assosiation Tables
exercise_primary_muscles = Table(
    "exercise_primary_muscles",
    Base.metadata,
    Column("exercise_id", ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True),
    Column("muscle_id", ForeignKey("muscles.id", ondelete="CASCADE"), primary_key=True),
)

exercise_secondary_muscles = Table(
    "exercise_secondary_muscles",
    Base.metadata,
    Column("exercise_id", ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True),
    Column("muscle_id", ForeignKey("muscles.id", ondelete="CASCADE"), primary_key=True),
)

# Table of all exercises
class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Can be updated in future to be many-to-many table for muscle groups
    primary_muscles = relationship(
        "Muscle",
        secondary=exercise_primary_muscles,
        lazy="joined"
    )

    secondary_muscles = relationship(
        "Muscle",
        secondary=exercise_secondary_muscles,
        lazy="joined"
    )
    
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True)
    
    equipment = relationship("Equipment")
    
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
    sets = relationship(
    "SetLog",
    back_populates="exercise_log",
    cascade="all, delete-orphan",
    passive_deletes=True,
)
    workout = relationship("WorkoutLog", back_populates="exercise_logs")
    exercise = relationship("Exercise")
    
# Table for each individual muscle
class Muscle(Base):
    __tablename__ = "muscles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    
class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    
class SetLog(Base):
    __tablename__ = "set_logs"

    id = Column(Integer, primary_key=True, index=True)
    exercise_log_id = Column(
        Integer,
        ForeignKey("exercise_logs.id", ondelete="CASCADE"),
        nullable=False
    )

    reps = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)

    exercise_log = relationship("ExerciseLog", back_populates="sets")
    
    