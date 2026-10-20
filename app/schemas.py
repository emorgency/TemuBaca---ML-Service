from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.region import REGION_CODE_PATTERN, get_region
from app.text import MAX_INTEREST_LENGTH, MAX_INTERESTS


def limit_interest_length(interests):
    # Blank entries are dropped later by normalize_interests, not rejected.
    stripped = [interest.strip() for interest in interests]

    for interest in stripped:
        if len(interest) > MAX_INTEREST_LENGTH:
            raise ValueError(
                f"each interest must be at most {MAX_INTEREST_LENGTH} characters"
            )

    return [interest for interest in stripped if interest]


class BookRecommendationRequest(BaseModel):
    user_interests: list[str] = Field(
        default_factory=list,
        max_length=MAX_INTERESTS
    )
    top_n: int = Field(default=10, ge=1, le=20)

    @field_validator("user_interests")
    @classmethod
    def limit_interests(cls, interests):
        return limit_interest_length(interests)


class BookRecommendation(BaseModel):
    book_id: str
    title: str
    score: float | None
    reason: str
    source: Literal["interest", "popularity"]


class BookRecommendationResponse(BaseModel):
    recommendations: list[BookRecommendation]
    unmatched_interests: list[str] = Field(default_factory=list)


class CommunityRecommendationRequest(BaseModel):
    # Unknown fields (including the removed user_city / user_province)
    # fail with 422 instead of being silently ignored.
    model_config = ConfigDict(extra="forbid")

    user_interests: list[str] = Field(
        default_factory=list,
        max_length=MAX_INTERESTS
    )
    user_region_code: str | None = Field(
        default=None,
        pattern=REGION_CODE_PATTERN
    )
    top_n: int = Field(default=5, ge=1, le=20)

    @field_validator("user_interests")
    @classmethod
    def limit_interests(cls, interests):
        return limit_interest_length(interests)

    @field_validator("user_region_code")
    @classmethod
    def known_region_code(cls, code):
        if code is not None and get_region(code) is None:
            raise ValueError("unknown region code")

        return code


class CommunityRecommendation(BaseModel):
    community_id: str
    name: str
    region_code: str
    region_name: str
    interest_score: float
    location_score: float
    score: float
    reason: str


class CommunityRecommendationResponse(BaseModel):
    recommendations: list[CommunityRecommendation]
    unmatched_interests: list[str] = Field(default_factory=list)
    notice: Literal["NEEDS_INTERESTS_OR_LOCATION", "NO_MATCH"] | None = None
