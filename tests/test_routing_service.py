"""Route planning on the hand-made fixture (docs/BACKEND_PETA_RUTE.md section 10.2)."""

import logging
import math

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.routing.errors import RoutingError
from app.routing.graph import load_graph
from app.routing.schemas import Point
from app.routing.service import RoutePlanner, load_configured_graphs


FIXTURES = Path(__file__).parent / "fixtures"
A, B, C, D, E = (-6.1900, 106.8300), (-6.1900, 106.8320), (-6.1920, 106.8320), (-6.1920, 106.8300), (-6.1950, 106.8350)


def point(lat_lng):
    return Point(lat=lat_lng[0], lng=lat_lng[1])


def haversine_m(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


@pytest.fixture
def planner():
    return RoutePlanner({"drive": load_graph(FIXTURES / "small_graph")}, snap_max_m=300, cache_size=10)


def test_distance_matches_the_hand_computed_route(planner):
    route = planner.route(point(A), point(C), "drive")
    # A -> B -> C on Jl. Satu and Jl. Dua.
    assert route["distance_m"] == round((haversine_m(A, B) + haversine_m(B, C)) / 10) * 10
    assert route["duration_s_estimate"] % 30 == 0
    assert route["warnings"] == ["ESTIMATE_NO_TRAFFIC"]
    assert route["algorithm"] == "dijkstra"
    assert route["graph_version"] == "test-drive-2026-10-25"


def test_geometry_runs_from_origin_to_destination(planner):
    coordinates = planner.route(point(C), point(D), "drive")["geometry"]["coordinates"]
    assert coordinates[0] == [C[1], C[0]]
    assert coordinates[-1] == [D[1], D[0]]
    # One-way Jl. Empat forces C -> B -> A -> D.
    assert coordinates == [[C[1], C[0]], [B[1], B[0]], [A[1], A[0]], [D[1], D[0]]]


def test_via_streets_are_at_most_three_in_travel_order(planner):
    assert planner.route(point(C), point(D), "drive")["via_streets"] == ["Jl. Dua", "Jl. Satu", "Jl. Tiga"]


def test_same_origin_and_destination_node(planner):
    route = planner.route(point(A), point((-6.19001, 106.83001)), "drive")
    assert route["distance_m"] == 0
    assert len(route["geometry"]["coordinates"]) == 2


def test_second_call_on_the_same_nodes_is_a_cache_hit(planner, caplog):
    with caplog.at_level(logging.INFO, logger="app.routing"):
        planner.route(point(A), point(C), "drive")
        # A slightly different origin still snaps to node A.
        planner.route(point((-6.19002, 106.83002)), point(C), "drive")
    hits = [record.getMessage() for record in caplog.records if "route mode=" in record.getMessage()]
    assert "cache_hit=False" in hits[0] and "cache_hit=True" in hits[1]


def test_log_never_holds_coordinates(planner, caplog):
    with caplog.at_level(logging.INFO, logger="app.routing"):
        planner.route(point(A), point(C), "drive")
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "6.19" not in text and "106.83" not in text


def test_unreachable_and_unloaded_modes(planner):
    with pytest.raises(RoutingError) as error:
        planner.route(point(A), point(E), "drive")
    assert error.value.code == "NO_PATH"
    with pytest.raises(RoutingError) as error:
        planner.route(point(A), point(C), "walk")
    assert error.value.code == "ROUTING_UNAVAILABLE"


def test_configured_graphs_skip_bad_names_and_missing_folders(caplog):
    settings = SimpleNamespace(graph_path=FIXTURES, routing_graphs="small_graph, ../small_graph, missing-graph")
    with caplog.at_level(logging.ERROR, logger="app.routing"):
        graphs = load_configured_graphs(settings)
    assert list(graphs) == ["drive"]
    assert "not a plain folder name" in caplog.text and "missing-graph not loaded" in caplog.text


def test_no_configured_graphs_loads_nothing():
    assert load_configured_graphs(SimpleNamespace(graph_path=FIXTURES, routing_graphs="")) == {}
