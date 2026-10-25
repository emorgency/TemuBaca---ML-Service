"""Graph loading, snapping, and estimates on the hand-made fixture (section 10.1)."""

import json
import shutil

from pathlib import Path

import numpy as np
import pytest

from app.routing.dijkstra import NoPathError, dijkstra
from app.routing.errors import RoutingError
from app.routing.estimate import load_speeds, round_distance_m, round_duration_s, speed_kmh, travel_time_s
from app.routing.graph import GraphLoadError, load_graph
from app.routing.snap import snap


FIXTURE = Path(__file__).parent / "fixtures" / "small_graph"
A, B, C, D, E = range(5)


@pytest.fixture(scope="module")
def graph():
    return load_graph(FIXTURE)


def broken_copy(tmp_path, change):
    """A copy of the fixture with one array replaced by `change(arrays)`."""
    folder = tmp_path / "graph"
    shutil.copytree(FIXTURE, folder)
    with np.load(folder / "graph.npz") as npz:
        arrays = dict(npz)
    change(arrays)
    np.savez(folder / "graph.npz", **arrays)
    return folder


# Loading

def test_fixture_loads_with_drive_weights(graph):
    assert graph.version == "test-drive-2026-10-25"
    assert graph.mode == "drive"
    assert len(graph.lat) == 5 and graph.indptr_list[-1] == 7
    assert graph.weights_list == graph.travel_time_s.tolist()


def test_rejects_inconsistent_array_sizes(tmp_path):
    folder = broken_copy(tmp_path, lambda arrays: arrays.update(length_m=arrays["length_m"][:-1]))
    with pytest.raises(GraphLoadError, match="length_m"):
        load_graph(folder)


def test_rejects_negative_weights(tmp_path):
    def negative(arrays):
        arrays["travel_time_s"][0] = -1.0
    with pytest.raises(GraphLoadError, match="travel_time_s"):
        load_graph(broken_copy(tmp_path, negative))


def test_rejects_edges_pointing_at_missing_nodes(tmp_path):
    def outside(arrays):
        arrays["indices"][0] = 99
    with pytest.raises(GraphLoadError, match="indices"):
        load_graph(broken_copy(tmp_path, outside))


def test_rejects_a_missing_file_or_a_bad_mode(tmp_path):
    folder = tmp_path / "graph"
    shutil.copytree(FIXTURE, folder)
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    (folder / "meta.json").write_text(json.dumps({**meta, "mode": "bus"}), encoding="utf-8")
    with pytest.raises(GraphLoadError, match="mode"):
        load_graph(folder)

    (folder / "edges.json").unlink()
    with pytest.raises(GraphLoadError, match="edges.json"):
        load_graph(folder)


def test_refuses_pickled_arrays(tmp_path):
    def pickled(arrays):
        arrays["edge_ref"] = np.array([{"not": "numeric"}] * len(arrays["edge_ref"]), dtype=object)
    folder = broken_copy(tmp_path, pickled)
    with pytest.raises(ValueError):
        load_graph(folder)


# Routing on the fixture

def test_drive_route_prefers_the_faster_streets(graph):
    # A -> B -> C (primary + secondary) beats A -> D -> C (residential) on time.
    path, _, _ = dijkstra(graph.indptr_list, graph.indices_list, graph.weights_list, A, C)
    assert path == [A, B, C]


def test_one_way_street_is_respected(graph):
    # Jl. Empat runs D -> C only, so C -> D goes round through B and A.
    path, positions, _ = dijkstra(graph.indptr_list, graph.indices_list, graph.weights_list, C, D)
    assert path == [C, B, A, D]
    assert [graph.edges[graph.edge_ref[position]].name for position in positions] == ["Jl. Dua", "Jl. Satu", "Jl. Tiga"]


def test_isolated_node_has_no_path(graph):
    with pytest.raises(NoPathError):
        dijkstra(graph.indptr_list, graph.indices_list, graph.weights_list, A, E)


# Snapping

def test_snaps_to_the_nearest_node(graph):
    node, offset_m = snap(graph, -6.19005, 106.83005, 300, "origin")
    assert node == A
    assert 0 < offset_m < 10


def test_point_far_from_any_road_is_too_far(graph):
    with pytest.raises(RoutingError) as error:
        snap(graph, -6.1860, 106.8260, 300, "destination")
    assert (error.value.code, error.value.status, error.value.point) == ("SNAP_TOO_FAR", 422, "destination")


def test_point_outside_the_bbox_is_out_of_coverage(graph):
    with pytest.raises(RoutingError) as error:
        snap(graph, -6.9175, 107.6191, 300, "origin")  # Bandung
    assert (error.value.code, error.value.point) == ("OUT_OF_COVERAGE", "origin")


# Estimates

def test_speed_per_highway_class():
    speeds = load_speeds()
    assert speed_kmh("primary", "drive", speeds) == 30
    assert speed_kmh("living_street", "drive", speeds) == 10
    assert speed_kmh("anything_else", "drive", speeds) == 10
    assert speed_kmh("primary", "walk", speeds) == 4.5


def test_highway_list_takes_the_fastest_class():
    speeds = load_speeds()
    assert speed_kmh(["residential", "secondary"], "drive", speeds) == 25


def test_travel_time_and_rounding():
    speeds = load_speeds()
    assert travel_time_s(250, "primary", "drive", speeds) == pytest.approx(30)
    assert round_distance_m(2296) == 2300
    assert round_duration_s(545) == 540
