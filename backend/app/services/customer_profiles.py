"""Persistence helpers for browser-scoped customer research profiles."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import CustomerProfile, User
from ..models.schemas import CustomerProfilePreferences, CustomerProfileResponse


def _profile_values(preferences: CustomerProfilePreferences) -> dict:
    values = preferences.model_dump(mode="json")
    return {
        **values,
        # These fields predate onboarding and remain intentionally unused by
        # this phase. Keeping them empty prevents the profile from becoming a
        # suitability or trading-instruction system.
        "excluded_investment_types": [],
        "presentation_preferences": {},
    }


def serialize_profile(profile: CustomerProfile) -> CustomerProfileResponse:
    return CustomerProfileResponse(
        customer_id=profile.user_id,
        experience_level=profile.experience_level,
        research_horizon=profile.research_horizon,
        priorities=profile.priorities,
        risk_comfort=profile.risk_comfort,
        preferred_report_depth=profile.preferred_report_depth,
        preferred_language=profile.preferred_language,
        industries_of_interest=profile.industries_of_interest,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def get_customer_profile(session: Session, customer_id: UUID) -> CustomerProfile | None:
    return session.scalar(
        select(CustomerProfile).where(CustomerProfile.user_id == customer_id)
    )


def create_customer_profile(
    session: Session, preferences: CustomerProfilePreferences
) -> CustomerProfile:
    user = User(email=None)
    profile = CustomerProfile(**_profile_values(preferences))
    user.customer_profile = profile
    session.add(user)
    session.commit()
    session.refresh(profile)
    return profile


def update_customer_profile(
    session: Session,
    profile: CustomerProfile,
    preferences: CustomerProfilePreferences,
) -> CustomerProfile:
    values = _profile_values(preferences)
    for key, value in values.items():
        setattr(profile, key, value)
    session.commit()
    session.refresh(profile)
    return profile
