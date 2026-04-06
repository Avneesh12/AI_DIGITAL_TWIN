"""app/api/v1/personality.py — Personality profile CRUD."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUser, get_personality_service
from app.schemas.personality import PersonalityCreate, PersonalityResponse, PersonalityUpdate
from app.services.personality_service import PersonalityService

router = APIRouter(prefix="/personality", tags=["Personality"])


@router.get("", response_model=PersonalityResponse)
async def get_personality(
    current_user: CurrentUser,
    svc: Annotated[PersonalityService, Depends(get_personality_service)],
) -> PersonalityResponse:
    """Get the personality profile for the authenticated user."""
    profile = await svc.get_or_create(str(current_user.id), session=None)  # type: ignore
    return PersonalityResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        tone=profile.tone,
        communication_style=profile.communication_style,
        values=profile.values or [],
        interests=profile.interests or [],
        decision_style=profile.decision_style,
        openness=profile.openness,
        conscientiousness=profile.conscientiousness,
        extraversion=profile.extraversion,
        agreeableness=profile.agreeableness,
        neuroticism=profile.neuroticism,
        persona_summary=profile.persona_summary,
        trait_confidence=profile.trait_confidence,
    )


@router.post("", response_model=PersonalityResponse, status_code=201)
async def create_personality(
    data: PersonalityCreate,
    current_user: CurrentUser,
    svc: Annotated[PersonalityService, Depends(get_personality_service)],
) -> PersonalityResponse:
    """Create or overwrite the personality profile."""
    profile = await svc.create_profile(str(current_user.id), data)
    return PersonalityResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        tone=profile.tone,
        communication_style=profile.communication_style,
        values=profile.values or [],
        interests=profile.interests or [],
        decision_style=profile.decision_style,
        openness=profile.openness,
        conscientiousness=profile.conscientiousness,
        extraversion=profile.extraversion,
        agreeableness=profile.agreeableness,
        neuroticism=profile.neuroticism,
        persona_summary=profile.persona_summary,
        trait_confidence=profile.trait_confidence,
    )


@router.patch("", response_model=PersonalityResponse)
async def update_personality(
    data: PersonalityUpdate,
    current_user: CurrentUser,
    svc: Annotated[PersonalityService, Depends(get_personality_service)],
) -> PersonalityResponse:
    """Partially update the personality profile."""
    profile = await svc.update_profile(str(current_user.id), data)
    return PersonalityResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        tone=profile.tone,
        communication_style=profile.communication_style,
        values=profile.values or [],
        interests=profile.interests or [],
        decision_style=profile.decision_style,
        openness=profile.openness,
        conscientiousness=profile.conscientiousness,
        extraversion=profile.extraversion,
        agreeableness=profile.agreeableness,
        neuroticism=profile.neuroticism,
        persona_summary=profile.persona_summary,
        trait_confidence=profile.trait_confidence,
    )
