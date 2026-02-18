from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date as Date
from typing import List, Optional, Literal

# -- Equipment --

class EquipmentOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
    
# -- Muscles --

class MuscleOut(BaseModel):
    id: int
    name: str
    
    model_config = ConfigDict(from_attributes=True)
    
# -- Goals --

class GoalOut(BaseModel):
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