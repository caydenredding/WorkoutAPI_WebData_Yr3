from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date
from typing import List, Optional

MIN_USERNAME_LEN = 6
MAX_USERNAME_LEN = 20

# -- Users --

class UserBase(BaseModel):
    # May add other restrictions - not sure yet
    username: str
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_USERNAME_LEN:
            raise ValueError(f"username must be at least {MIN_USERNAME_LEN} characters")
        if len(v) > MAX_USERNAME_LEN:
            raise ValueError(f"username must be at most {MAX_USERNAME_LEN} characters")
        return v

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) < MIN_USERNAME_LEN:
            raise ValueError(f"username must be at least {MIN_USERNAME_LEN} characters")
        if len(v) > MAX_USERNAME_LEN:
            raise ValueError(f"username must be at most {MAX_USERNAME_LEN} characters")
        return v
    
class UserOut(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
        
# -- Workouts --

class WorkoutBase(BaseModel):
    date: date

class WorkoutCreate(WorkoutBase):
    pass

class WorkoutUpdate(BaseModel):
    date: Optional[date]

class WorkoutOut(WorkoutBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)
    
# -- Muscles --

class MuscleOut(BaseModel):
    id: int
    name: str
    
    model_config = ConfigDict(from_attributes=True)
    

# -- Equipment --

class EquipmentOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
    

# -- Exercises --

class ExerciseOut(BaseModel):
    id: int
    name: str
    equipment: EquipmentOut | None
    primary_muscles: list[MuscleOut]
    secondary_muscles: list[MuscleOut]

    model_config = ConfigDict(from_attributes=True)
    
# -- Sets -- 
    
class SetBase(BaseModel):
    reps: int = Field(..., gt=0)
    weight: float = Field(..., ge=0)

class SetCreate(SetBase):
    pass

class SetUpdate(BaseModel):
    reps: Optional[int] = Field(None, gt=0)
    weight: Optional[float] = Field(None, ge=0)

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

    

