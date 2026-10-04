from datetime import datetime

from pydantic import BaseModel, Field


class ProfileInput(BaseModel):
    age: int = Field(ge=1, le=120)
    allergies: str = Field(default="", max_length=5000)
    food_likes: str = Field(default="", max_length=5000)
    food_dislikes: str = Field(default="", max_length=5000)
    dietary_restrictions: str = Field(default="", max_length=5000)
    notes: str = Field(default="", max_length=5000)


class ProfileResponse(ProfileInput):
    updated_at: datetime | None = None


class ReportSummary(BaseModel):
    id: int
    filename: str
    created_at: datetime


class ReportResponse(ReportSummary):
    plan: dict

