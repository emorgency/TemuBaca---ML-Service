from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    """POST /api/routing/route (docs/BACKEND_PETA_RUTE.md section 5.1)."""

    model_config = ConfigDict(extra="forbid")

    origin: Point
    destination: Point
    mode: Literal["drive", "walk"] = "drive"
