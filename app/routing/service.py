import logging
import re
import time

from collections import OrderedDict

from app.routing.dijkstra import NoPathError, dijkstra
from app.routing.errors import RoutingError
from app.routing.estimate import load_speeds, round_distance_m, round_duration_s, travel_time_s
from app.routing.graph import MODES, GraphLoadError, load_graph
from app.routing.snap import snap


logger = logging.getLogger("app.routing")

ATTRIBUTION = "© OpenStreetMap contributors"
GRAPH_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
MAX_VIA_STREETS = 3


def load_configured_graphs(settings):
    """Graphs named in ROUTING_GRAPHS, by mode (section 6.2).

    A graph that fails to load is logged and skipped so the service still
    starts; its mode then answers ROUTING_UNAVAILABLE. Names are folder names
    under GRAPH_DIR, never paths.
    """
    graphs = {}
    for name in filter(None, (part.strip() for part in settings.routing_graphs.split(","))):
        if not GRAPH_NAME.match(name):
            logger.error("routing graph %r skipped: not a plain folder name", name)
            continue
        try:
            graph = load_graph(settings.graph_path / name)
        except (GraphLoadError, OSError) as error:
            logger.error("routing graph %s not loaded: %s", name, error)
            continue
        if graph.mode in graphs:
            logger.error("routing graph %s skipped: %s already uses %s", name, graph.mode, graphs[graph.mode].version)
            continue
        graphs[graph.mode] = graph
        logger.info("routing graph %s loaded for %s", graph.version, graph.mode)
    return graphs


class RoutePlanner:
    """Snap, Dijkstra, and the route summary of section 5.2, with an LRU cache on snapped nodes (section 6.7)."""

    def __init__(self, graphs, snap_max_m, cache_size, speeds=None):
        self.graphs = graphs
        self.snap_max_m = snap_max_m
        self.cache_size = cache_size
        self.speeds = speeds or load_speeds()
        self._cache = OrderedDict()

    def versions(self):
        return {mode: (self.graphs[mode].version if mode in self.graphs else None) for mode in MODES}

    def route(self, origin, destination, mode):
        graph = self.graphs.get(mode)
        if graph is None:
            raise RoutingError("ROUTING_UNAVAILABLE")

        started = time.perf_counter()
        source, origin_offset = snap(graph, origin.lat, origin.lng, self.snap_max_m, "origin")
        target, destination_offset = snap(graph, destination.lat, destination.lng, self.snap_max_m, "destination")

        stats = {"popped": 0}
        key = (graph.version, source, target)
        cache_hit = key in self._cache
        try:
            if cache_hit:
                self._cache.move_to_end(key)
                path, positions, cost = self._cache[key]
            else:
                path, positions, cost = dijkstra(graph.dijkstra_indptr, graph.dijkstra_indices, graph.dijkstra_weights, source, target, stats)
                self._remember(key, (path, positions, cost))
        except NoPathError:
            self._log(graph, "NO_PATH", started, stats, cache_hit)
            raise RoutingError("NO_PATH") from None

        distance_m = float(sum(graph.length_m[position] for position in positions))
        # Drive weights are seconds; walk weights are metres at one walking speed.
        duration_s = cost if mode == "drive" else travel_time_s(distance_m, None, "walk", self.speeds)
        self._log(graph, "OK", started, stats, cache_hit)
        return {
            "mode": mode,
            "distance_m": round_distance_m(distance_m),
            "duration_s_estimate": round_duration_s(duration_s),
            "geometry": {"type": "LineString", "coordinates": _geometry(graph, path, positions)},
            "via_streets": _via_streets(graph, positions),
            "snap": {"origin_offset_m": round(origin_offset), "destination_offset_m": round(destination_offset)},
            "warnings": ["ESTIMATE_NO_TRAFFIC"],
            "algorithm": "dijkstra",
            "graph_version": graph.version,
        }

    def _remember(self, key, value):
        if self.cache_size <= 0:
            return
        self._cache[key] = value
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    def _log(self, graph, status, started, stats, cache_hit):
        # Never the coordinates (section 7): only what describes the work done.
        logger.info(
            "route mode=%s graph=%s status=%s latency_ms=%.1f popped=%d cache_hit=%s",
            graph.mode, graph.version, status, (time.perf_counter() - started) * 1000, stats["popped"], cache_hit,
        )


def _geometry(graph, path, positions):
    """[lng, lat] from the origin node to the destination node, along each edge's own polyline."""
    if not positions:
        node = [float(graph.lng[path[0]]), float(graph.lat[path[0]])]
        return [node, node]
    coordinates = []
    for start, position in zip(path, positions):
        coords = graph.edge_polyline(graph.edge_ref[position])
        # A geometry may be stored in either direction; start from the end nearest this edge's first node.
        if _squared_distance(coords[-1], graph, start) < _squared_distance(coords[0], graph, start):
            coords = coords[::-1]
        coordinates.extend((coords if not coordinates else coords[1:]).tolist())
    return coordinates


def _squared_distance(coord, graph, node):
    return (coord[0] - graph.lng[node]) ** 2 + (coord[1] - graph.lat[node]) ** 2


def _via_streets(graph, positions):
    """Up to three street names carrying the most distance, in travel order. Not turn-by-turn directions."""
    lengths, first_seen = {}, {}
    for order, position in enumerate(positions):
        name = graph.edge_names[graph.edge_ref[position]]
        if not name:
            continue
        # A merged edge carries several names joined with " / "; credit each.
        for part in name.split(" / "):
            lengths[part] = lengths.get(part, 0.0) + float(graph.length_m[position])
            first_seen.setdefault(part, order)
    longest = sorted(lengths, key=lengths.get, reverse=True)[:MAX_VIA_STREETS]
    return sorted(longest, key=first_seen.get)
