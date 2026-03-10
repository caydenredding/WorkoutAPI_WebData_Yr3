from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    username: str
    password: str = Field(min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        return v.strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int
    username: str
    role: str