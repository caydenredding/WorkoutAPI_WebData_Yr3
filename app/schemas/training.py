from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date as Date
from typing import List, Optional
from .base import ExerciseOut

# -- Sets -- 
    
class SetBase(BaseModel):
    reps: int = Field(..., gt=0)
    weight: float = Field(..., ge=0)
    rir: Optional[int] = Field(None, ge=0, le=10, description="Reps in Reserve (0–10)")

class SetCreate(SetBase):
    pass

class SetUpdate(BaseModel):
    reps: Optional[int] = Field(None, gt=0)
    weight: Optional[float] = Field(None, ge=0)
    rir: Optional[int] = Field(None, ge=0, le=10, description="Reps in Reserve (0–10)")

class SetOut(SetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

    
# -- Exercise Logs --

class ExerciseLogCreate(BaseModel):
    exercise_id: int

class ExerciseLogUpdate(BaseModel):
    exercise_id: Optional[int] = None

class ExerciseLogOut(BaseModel):
    id: int
    workout_id: int
    exercise: ExerciseOut
    sets: List[SetOut]

    model_config = ConfigDict(from_attributes=True)
    

# -- Workouts --

class WorkoutBase(BaseModel):
    date: Date

class WorkoutCreate(WorkoutBase):
    pass

class WorkoutUpdate(BaseModel):
    date: Optional[Date] = None

class WorkoutOut(WorkoutBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)
    
    
