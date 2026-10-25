import logging

from fastapi import APIRouter, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.routing.errors import RoutingError
from app.routing.schemas import RouteRequest


logger = logging.getLogger("app.routing")

ROUTING_PREFIX = "/api/routing/"

# Mounted under the /api router, so the internal token is required (R-07, option b).
router = APIRouter(prefix="/routing")


@router.post("/route")
def plan_route(body: RouteRequest, request: Request):
    planner = getattr(request.app.state, "routing", None)
    if planner is None:
        raise RoutingError("ROUTING_UNAVAILABLE")
    try:
        return planner.route(body.origin, body.destination, body.mode)
    except RoutingError:
        raise
    except Exception:
        # The traceback names code, not request values, so no coordinates reach the log.
        logger.exception("routing failed")
        raise RoutingError("INTERNAL") from None


def _error(status, code, message, point=None):
    error = {"code": code, "message": message}
    if point:
        error["point"] = point
    return JSONResponse(status_code=status, content={"error": error})


async def _routing_error(request, error):
    return _error(error.status, error.code, error.message, error.point)


async def _validation_error(request, error):
    # Section 5.3 format only for routing; recommendations keep FastAPI's default.
    if request.url.path.startswith(ROUTING_PREFIX):
        exc = RoutingError("INVALID_PARAMS")
        return _error(exc.status, exc.code, exc.message)
    return await request_validation_exception_handler(request, error)


async def _http_error(request, error):
    if request.url.path.startswith(ROUTING_PREFIX) and error.status_code == 401:
        exc = RoutingError("UNAUTHORIZED")
        return _error(exc.status, exc.code, exc.message)
    return await http_exception_handler(request, error)


def install_error_handlers(app):
    app.add_exception_handler(RoutingError, _routing_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
