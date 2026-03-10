from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date as Date
from typing import List, Optional

MIN_USERNAME_LEN = 6
MAX_USERNAME_LEN = 20


class UserBase(BaseModel):
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
    """
    Admin-only: create a user (account) without going through /auth/register.
    """
    years_experience: Optional[int] = Field(None, ge=0, le=80)
    goal_id: Optional[int] = Field(None, ge=1)
    target_days_per_week: Optional[int] = Field(None, ge=1, le=7)

    # Optional: allow admin to set role
    role: Optional[str] = Field(default="user", description="user or admin")

    # Admin can set an initial password
    password: str = Field(min_length=8, max_length=72)


class UserUpdate(BaseModel):
    username: Optional[str] = None
    years_experience: Optional[int] = Field(None, ge=0, le=80)
    goal_id: Optional[int] = Field(None, ge=1)
    target_days_per_week: Optional[int] = Field(None, ge=1, le=7)

    # Admin-only in practice (enforced in router)
    role: Optional[str] = Field(None, description="user or admin")

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
    years_experience: int
    goal_id: int
    target_days_per_week: int
    account_created: Date

    role: str

    model_config = ConfigDict(from_attributes=True)


class WeighInCreate(BaseModel):
    weight: float
    date: Date


class WeighInOut(BaseModel):
    id: int
    user_id: int
    weight: float = Field(..., gt=0, description="Bodyweight value (kg)")
    date: Date

    model_config = ConfigDict(from_attributes=True)


class WeighInListOut(BaseModel):
    user_id: int
    count: int
    weigh_ins: List[WeighInOut]


class WeighInUpdate(BaseModel):
    weight: Optional[float] = Field(None, gt=0, description="Bodyweight value (kg)")
    date: Optional[Date] = None