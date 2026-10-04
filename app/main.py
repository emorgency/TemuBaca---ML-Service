from fastapi import FastAPI
from app.recommender import get_recommendations
from app.community import recommend_communities

from app.schemas import (
    BookRecommendationRequest,
    BookRecommendationResponse,
    CommunityRecommendationRequest,
    CommunityRecommendationResponse
)

app = FastAPI(
    title="TemuBaca ML Service",
    description="Recommendation service for TemuBaca",
    version="1.0.0",
)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "temubaca-ml"
    }

@app.post(
    "/api/recommendations/books",
    response_model=BookRecommendationResponse
)
def recommend_books(request: BookRecommendationRequest):
    recommendations = get_recommendations(
        user_interests=request.user_interests,
        top_n=request.top_n
    )

    return {
        "recommendations": recommendations
    }

@app.post(
    "/api/recommendations/communities",
    response_model=CommunityRecommendationResponse
)
def recommend_community(request: CommunityRecommendationRequest):
    recommendations = recommend_communities(
        user_interests=request.user_interests,
        user_city=request.user_city,
        user_province=request.user_province,
        top_n=request.top_n
    )

    return {
        "recommendations": recommendations
    }