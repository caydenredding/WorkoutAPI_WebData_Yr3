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
    years_experience: Optional[int] = Field(
        None,
        ge=0,
        le=80,
        description="Years of structured training experience (0–80)"
    )
    goal_id: Optional[int] = Field(
        None,
        ge=1,
        description="Goal ID (optional)"
    )

class UserUpdate(BaseModel):
    """
    Single PATCH payload:
    - omit fields to leave unchanged
    - goal_id can be null to clear
    """
    username: Optional[str] = None
    years_experience: Optional[int] = Field(None, ge=0, le=80)
    goal_id: Optional[int] = Field(None, ge=1)

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

# -- Analytic Schemas --

class ExerciseMaxSetVolumeOut(BaseModel):
    exercise_id: int
    exercise_name: str
    max_set_volume: float
    reps: int
    weight: float
    date: date

    model_config = ConfigDict(from_attributes=True)


class ExerciseBest1RMOut(BaseModel):
    exercise_id: int
    exercise_name: str
    formula: str
    best_e1rm: float

    model_config = ConfigDict(from_attributes=True)
    
class WeeklyStreakOut(BaseModel):
    user_id: int
    weekly_goal: int
    current_weekly_streak: int

    model_config = ConfigDict(from_attributes=True)


class WorkoutsLast30DaysOut(BaseModel):
    user_id: int
    days: int
    workouts_count: int

    model_config = ConfigDict(from_attributes=True)


class LastSevenDayGapOut(BaseModel):
    user_id: int
    last_gap_start_date: Optional[date]  # first day of the 7-day no-workout window
    last_gap_end_date: Optional[date]    # last day of that window (start + 6)

    model_config = ConfigDict(from_attributes=True)
    

