from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date as Date
from typing import List, Optional, Literal

# -- Performance Analytics --

class ExerciseMaxSetVolumeOut(BaseModel):
    exercise_id: int
    exercise_name: str
    max_set_volume: float
    reps: int
    weight: float
    date: Date

    model_config = ConfigDict(from_attributes=True)


class ExerciseBest1RMOut(BaseModel):
    exercise_id: int
    exercise_name: str
    formula: str
    best_e1rm: float

    model_config = ConfigDict(from_attributes=True)
    
# -- Consistency Analytics --
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
    last_gap_start_date: Optional[Date]  # first day of the 7-day no-workout window
    last_gap_end_date: Optional[Date]    # last day of that window (start + 6)

    model_config = ConfigDict(from_attributes=True)