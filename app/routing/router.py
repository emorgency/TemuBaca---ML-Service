import logging

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

from app.routing.errors import RoutingError
from app.routing.schemas import RouteRequest


logger = logging.getLogger("app.routing")


class RoutingRoute(APIRoute):
    """Answers invalid input and a bad token in the section 5.3 error format.

    Validation and the internal-token dependency run inside the route handler, so
    catching them here keeps recommendations on FastAPI's default format without
    any path checks in the app-wide handlers.
    """

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise RoutingError("INVALID_PARAMS") from None
            except HTTPException as error:
                if error.status_code == 401:
                    raise RoutingError("UNAUTHORIZED") from None
                raise

        return handle


# Mounted under the /api router, so the internal token is required (R-07, option b).
router = APIRouter(prefix="/routing", route_class=RoutingRoute)


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


async def _routing_error(request, error):
    content = {"code": error.code, "message": error.message}
    if error.point:
        content["point"] = error.point
    return JSONResponse(status_code=error.status, content={"error": content})


def install_error_handlers(app):
    app.add_exception_handler(RoutingError, _routing_error)
