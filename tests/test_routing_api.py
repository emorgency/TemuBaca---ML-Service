"""POST /api/routing/route over HTTP (docs/BACKEND_PETA_RUTE.md section 10.3)."""

from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routing.graph import load_graph
from app.routing.service import RoutePlanner
from tests.conftest import TEST_TOKEN


ROUTE = "/api/routing/route"
FIXTURE = Path(__file__).parent / "fixtures" / "small_graph"
client = TestClient(app, headers={"X-Internal-Token": TEST_TOKEN})
anonymous = TestClient(app)


def body(origin=(-6.1900, 106.8300), destination=(-6.1920, 106.8320), **extra):
    return {"origin": {"lat": origin[0], "lng": origin[1]}, "destination": {"lat": destination[0], "lng": destination[1]}, **extra}


@pytest.fixture(autouse=True)
def fixture_graph():
    # Inject the fixture instead of reading data/graphs (section 10.3).
    app.state.routing = RoutePlanner({"drive": load_graph(FIXTURE)}, snap_max_m=300, cache_size=10)
    yield
    del app.state.routing


def test_valid_request_returns_a_route():
    response = client.post(ROUTE, json=body())
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "drive" and data["geometry"]["type"] == "LineString"
    assert set(data) == {"mode", "distance_m", "duration_s_estimate", "geometry", "via_streets", "snap", "warnings", "algorithm", "graph_version"}


@pytest.mark.parametrize("payload", [
    body(extra_field=1),
    body(mode="bus"),
    body(origin=(-91, 106.83)),
    {"origin": {"lat": -6.19}, "destination": {"lat": -6.19, "lng": 106.83}},
])
def test_invalid_params(payload):
    response = client.post(ROUTE, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PARAMS"


def test_out_of_coverage_names_the_point():
    response = client.post(ROUTE, json=body(destination=(-6.9175, 107.6191)))
    assert response.status_code == 422
    assert response.json()["error"] == {"code": "OUT_OF_COVERAGE", "message": "Titik berada di luar cakupan rute.", "point": "destination"}


def test_snap_too_far():
    response = client.post(ROUTE, json=body(origin=(-6.1860, 106.8260)))
    assert (response.status_code, response.json()["error"]["code"], response.json()["error"]["point"]) == (422, "SNAP_TOO_FAR", "origin")


def test_no_path():
    response = client.post(ROUTE, json=body(destination=(-6.1950, 106.8350)))
    assert (response.status_code, response.json()["error"]["code"]) == (404, "NO_PATH")


def test_unloaded_mode_is_unavailable_while_recommendations_work():
    response = client.post(ROUTE, json=body(mode="walk"))
    assert (response.status_code, response.json()["error"]["code"]) == (503, "ROUTING_UNAVAILABLE")
    assert client.post("/api/recommendations/books", json={"user_interests": ["fantasy"]}).status_code == 200


def test_no_graphs_at_all_is_unavailable():
    del app.state.routing
    response = client.post(ROUTE, json=body())
    assert (response.status_code, response.json()["error"]["code"]) == (503, "ROUTING_UNAVAILABLE")
    app.state.routing = None


def test_token_is_required():
    response = anonymous.post(ROUTE, json=body())
    assert (response.status_code, response.json()["error"]["code"]) == (401, "UNAUTHORIZED")


def test_routing_bodies_over_2_kb_are_rejected():
    padded = body()
    padded["origin"]["note"] = "x" * 2100
    assert client.post(ROUTE, json=padded).status_code == 413


def test_recommendation_errors_keep_their_format():
    response = client.post("/api/recommendations/books", json={"top_n": "many"})
    assert response.status_code == 422 and "detail" in response.json()


def test_health_keeps_old_fields_and_reports_routing():
    data = client.get("/health").json()
    assert (data["status"], data["service"]) == ("ok", "temubaca-ml")
    assert data["routing"] == {"drive": "test-drive-2026-10-25", "walk": None, "attribution": "© OpenStreetMap contributors"}


def test_service_starts_without_any_graph_folder(monkeypatch):
    monkeypatch.setattr(settings, "routing_graphs", "")
    with TestClient(app, headers={"X-Internal-Token": TEST_TOKEN}) as started:
        assert started.get("/health").json()["routing"]["drive"] is None
        assert started.post(ROUTE, json=body()).json()["error"]["code"] == "ROUTING_UNAVAILABLE"
