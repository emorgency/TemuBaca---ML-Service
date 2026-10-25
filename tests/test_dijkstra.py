"""Dijkstra against networkx (docs/BACKEND_PETA_RUTE.md section 10.1)."""

import random

import networkx as nx
import pytest

from app.routing.dijkstra import NoPathError, dijkstra


def to_csr(graph, nodes):
    """CSR lists from a networkx DiGraph whose nodes are 0..nodes-1."""
    indptr, indices, weights = [0], [], []
    for node in range(nodes):
        for neighbor, data in sorted(graph[node].items()):
            indices.append(neighbor)
            weights.append(data["weight"])
        indptr.append(len(indices))
    return indptr, indices, weights


def assert_valid_path(csr, path, positions, cost, source, target):
    indptr, indices, weights = csr
    assert path[0] == source and path[-1] == target
    assert len(positions) == len(path) - 1
    for node, position, following in zip(path, positions, path[1:]):
        assert indptr[node] <= position < indptr[node + 1]
        assert indices[position] == following
    assert sum(weights[position] for position in positions) == pytest.approx(cost)


def test_matches_networkx_on_200_random_graphs():
    rng = random.Random(20261025)
    for _ in range(200):
        nodes = rng.randint(2, 40)
        graph = nx.gnp_random_graph(nodes, rng.uniform(0.05, 0.3), seed=rng.randint(0, 10**9), directed=True)
        for u, v in graph.edges:
            graph[u][v]["weight"] = rng.uniform(0.5, 100)
        csr = to_csr(graph, nodes)
        source, target = rng.randrange(nodes), rng.randrange(nodes)

        try:
            expected = nx.shortest_path_length(graph, source, target, weight="weight")
        except nx.NetworkXNoPath:
            with pytest.raises(NoPathError):
                dijkstra(*csr, source, target)
            continue

        path, positions, cost = dijkstra(*csr, source, target)
        assert cost == pytest.approx(expected)
        assert_valid_path(csr, path, positions, cost, source, target)


def test_equal_cost_paths_give_the_same_cost():
    # A 4x4 grid with unit weights has many shortest paths between corners.
    grid = nx.DiGraph()
    for (r, c) in [(r, c) for r in range(4) for c in range(4)]:
        for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            if 0 <= r + dr < 4 and 0 <= c + dc < 4:
                grid.add_edge(r * 4 + c, (r + dr) * 4 + c + dc, weight=1.0)
    csr = to_csr(grid, 16)

    path, positions, cost = dijkstra(*csr, 0, 15)
    assert cost == 6.0
    assert_valid_path(csr, path, positions, cost, 0, 15)


def test_unreachable_target_raises():
    # 0 -> 1, and 2 is cut off.
    with pytest.raises(NoPathError):
        dijkstra([0, 1, 1, 1], [1], [3.0], 0, 2)


def test_source_equals_target():
    assert dijkstra([0, 1, 1], [1], [3.0], 1, 1) == ([1], [], 0.0)


def test_source_without_outgoing_edges():
    # Node 1 has no outgoing edges; reaching it works, leaving it does not.
    assert dijkstra([0, 1, 1], [1], [3.0], 0, 1) == ([0, 1], [0], 3.0)
    with pytest.raises(NoPathError):
        dijkstra([0, 1, 1], [1], [3.0], 1, 0)


def test_takes_the_cheaper_of_two_routes():
    # 0 -> 1 -> 2 costs 2; the direct 0 -> 2 edge costs 5.
    indptr, indices, weights = [0, 2, 3, 3], [1, 2, 2], [1.0, 5.0, 1.0]
    assert dijkstra(indptr, indices, weights, 0, 2) == ([0, 1, 2], [0, 2], 2.0)
