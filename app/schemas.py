from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.text import MAX_INTEREST_LENGTH, MAX_INTERESTS


class BookRecommendationRequest(BaseModel):
    user_interests: list[str] = Field(
        default_factory=list,
        max_length=MAX_INTERESTS
    )
    top_n: int = Field(default=10, ge=1, le=20)

    @field_validator("user_interests")
    @classmethod
    def limit_interest_length(cls, interests):
        # Blank entries are dropped later by normalize_interests, not rejected.
        stripped = [interest.strip() for interest in interests]

        for interest in stripped:
            if len(interest) > MAX_INTEREST_LENGTH:
                raise ValueError(
                    f"each interest must be at most {MAX_INTEREST_LENGTH} characters"
                )

        return [interest for interest in stripped if interest]


class BookRecommendation(BaseModel):
    book_id: int
    title: str
    score: float | None
    reason: str


class BookRecommendationResponse(BaseModel):
    recommendations: list[BookRecommendation]


class CommunityRecommendationRequest(BaseModel):
    user_interests: list[str] = Field(default_factory=list)
    user_city: str | None = None
    user_province: str | None = None
    top_n: int = Field(default=5, ge=1, le=20)


class CommunityRecommendation(BaseModel):
    community_id: str
    name: str
    interest_score: float
    location_score: float
    score: float
    reason: str


class CommunityRecommendationResponse(BaseModel):
    recommendations: list[CommunityRecommendation]