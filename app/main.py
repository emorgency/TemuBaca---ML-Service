import logging
import time

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

# uvicorn configures only its own loggers, so the service's INFO lines (graph loads,
# per-request stats for routes and recommendations) need a handler to reach stdout.
# Children such as app.routing and app.recommendations propagate to this one.
app_log = logging.getLogger("app")
if not app_log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    app_log.addHandler(handler)
    app_log.setLevel(logging.INFO)

recommendations_log = logging.getLogger("app.recommendations")


def log_recommendations(kind, started, interests, unmatched, results, notice=None):
    # Counts only (ML-T08): never the interests, the region code, or the ids returned.
    # Only book results say where they came from (interest or popularity).
    sources = {}
    for item in results:
        if "source" in item:
            sources[item["source"]] = sources.get(item["source"], 0) + 1
    recommendations_log.info(
        "recommend kind=%s model=%s interests=%d unmatched=%d results=%d sources=%s notice=%s latency_ms=%.1f",
        kind, model_meta.get("model_version"), len(interests), len(unmatched), len(results),
        ",".join(f"{name}:{count}" for name, count in sorted(sources.items())) or "-", notice or "-",
        (time.perf_counter() - started) * 1000,
    )


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
    started = time.perf_counter()
    recommendations = get_recommendations(
        user_interests=request.user_interests,
        top_n=request.top_n
    )
    interests = normalize_interests(request.user_interests)
    unmatched = unmatched_interests(interests)
    log_recommendations("books", started, interests, unmatched, recommendations)

    return {
        "recommendations": recommendations,
        "unmatched_interests": unmatched
    }


@api.post(
    "/recommendations/communities",
    response_model=CommunityRecommendationResponse
)
def recommend_community(request: CommunityRecommendationRequest):
    started = time.perf_counter()
    recommendations = recommend_communities(
        user_interests=request.user_interests,
        user_region_code=request.user_region_code,
        top_n=request.top_n
    )
    interests = normalize_interests(request.user_interests)
    unmatched = unmatched_interests(interests)
    notice = community_notice(
        request.user_interests,
        request.user_region_code,
        recommendations
    )
    log_recommendations("communities", started, interests, unmatched, recommendations, notice)

    return {
        "recommendations": recommendations,
        "unmatched_interests": unmatched,
        "notice": notice
    }


api.include_router(routing_router)
app.include_router(api)
