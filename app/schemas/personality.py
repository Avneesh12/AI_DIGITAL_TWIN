"""app/schemas/personality.py — Personality profile schemas."""
from pydantic import BaseModel, Field, field_validator


class PersonalityCreate(BaseModel):
    tone: str | None = None
    communication_style: str | None = None
    values: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    decision_style: str | None = None
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)
    persona_summary: str | None = None


class PersonalityUpdate(BaseModel):
    tone: str | None = None
    communication_style: str | None = None
    values: list[str] | None = None
    interests: list[str] | None = None
    decision_style: str | None = None
    openness: float | None = Field(default=None, ge=0.0, le=1.0)
    conscientiousness: float | None = Field(default=None, ge=0.0, le=1.0)
    extraversion: float | None = Field(default=None, ge=0.0, le=1.0)
    agreeableness: float | None = Field(default=None, ge=0.0, le=1.0)
    neuroticism: float | None = Field(default=None, ge=0.0, le=1.0)
    persona_summary: str | None = None


class PersonalityResponse(BaseModel):
    id: str
    user_id: str
    tone: str | None
    communication_style: str | None
    values: list[str]
    interests: list[str]
    decision_style: str | None
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float
    persona_summary: str | None
    trait_confidence: float

    model_config = {"from_attributes": True}
