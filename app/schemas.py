from pydantic import BaseModel, Field


class BookRecommendationRequest(BaseModel):
    user_interests: list[str] = Field(default_factory=list)
    top_n: int = Field(default=10, ge=1, le=20)


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