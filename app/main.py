import logging

from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request

from app.community import community_notice, recommend_communities
from app.config import settings
from app.model_store import model_meta
from app.recommender import get_recommendations
from app.routing.router import install_error_handlers, router as routing_router
from app.routing.graph import MODES
from app.routing.service import ATTRIBUTION, RoutePlanner, load_configured_graphs
from app.security import ApiBodyLimitMiddleware, require_internal_token
from app.text import normalize_interests, unmatched_interests

from app.schemas import (
    BookRecommendationRequest,
    BookRecommendationResponse,
    CommunityRecommendationRequest,
    CommunityRecommendationResponse
)

# uvicorn configures only its own loggers, so routing's INFO lines (graph loads,
# per-route stats without coordinates) need a handler to reach stdout.
routing_log = logging.getLogger("app.routing")
if not routing_log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    routing_log.addHandler(handler)
    routing_log.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app):
    # Graphs load here, not at import, so a missing or broken graph never stops
    # the service: recommendations keep working and routing answers 503.
    app.state.routing = RoutePlanner(
        load_configured_graphs(settings),
        snap_max_m=settings.snap_max_m,
        cache_size=settings.route_cache_size,
    )
    yield


app = FastAPI(
    title="TemuBaca ML Service",
    description="Recommendation service for TemuBaca",
    version="1.0.0",
    lifespan=lifespan,
)
install_error_handlers(app)

# No CORS middleware: browsers never call this service directly.
app.add_middleware(ApiBodyLimitMiddleware)

# Every /api/* route requires the internal token (R-07).
api = APIRouter(
    prefix="/api",
    dependencies=[Depends(require_internal_token)]
)


@app.get("/health")
def health_check(request: Request):
    planner = getattr(request.app.state, "routing", None)
    return {
        "status": "ok",
        "service": "temubaca-ml",
        "model_version": model_meta.get("model_version"),
        "book_count": model_meta.get("book_count"),
        "routing": {
            **(planner.versions() if planner else dict.fromkeys(MODES)),
            "attribution": ATTRIBUTION,
        },
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


api.include_router(routing_router)
app.include_router(api)
