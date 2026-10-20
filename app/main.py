from fastapi import APIRouter, Depends, FastAPI

from app.community import community_notice, recommend_communities
from app.model_store import model_meta
from app.recommender import get_recommendations
from app.security import ApiBodyLimitMiddleware, require_internal_token
from app.text import normalize_interests, unmatched_interests

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

# No CORS middleware: browsers never call this service directly.
app.add_middleware(ApiBodyLimitMiddleware)

# Every /api/* route requires the internal token (R-07).
api = APIRouter(
    prefix="/api",
    dependencies=[Depends(require_internal_token)]
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "temubaca-ml",
        "model_version": model_meta.get("model_version"),
        "book_count": model_meta.get("book_count")
    }


@api.post(
    "/recommendations/books",
    response_model=BookRecommendationResponse
)
def recommend_books(request: BookRecommendationRequest):
    recommendations = get_recommendations(
        user_interests=request.user_interests,
        top_n=request.top_n
    )

    return {
        "recommendations": recommendations,
        "unmatched_interests": unmatched_interests(
            normalize_interests(request.user_interests)
        )
    }


@api.post(
    "/recommendations/communities",
    response_model=CommunityRecommendationResponse
)
def recommend_community(request: CommunityRecommendationRequest):
    recommendations = recommend_communities(
        user_interests=request.user_interests,
        user_region_code=request.user_region_code,
        top_n=request.top_n
    )

    return {
        "recommendations": recommendations,
        "unmatched_interests": unmatched_interests(
            normalize_interests(request.user_interests)
        ),
        "notice": community_notice(
            request.user_interests,
            request.user_region_code,
            recommendations
        )
    }


app.include_router(api)
