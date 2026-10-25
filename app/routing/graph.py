import json
import math

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from scipy.spatial import cKDTree


MODES = ("drive", "walk")
ARRAYS = ("node_ids", "lat", "lng", "indptr", "indices", "length_m", "travel_time_s", "edge_ref")

# Local equirectangular projection (section 6.2): metres per degree.
M_PER_DEG_LNG_AT_EQUATOR = 111320
M_PER_DEG_LAT = 110540


class GraphLoadError(ValueError):
    """A graph folder is missing a file or holds inconsistent data."""


@dataclass(frozen=True)
class EdgeInfo:
    name: str | None
    highway: str | list[str] | None
    coords: list[list[float]]  # polyline as [lng, lat]


@dataclass(frozen=True)
class RoadGraph:
    version: str
    mode: str
    bbox: tuple[float, float, float, float]  # min_lng, min_lat, max_lng, max_lat
    lat: np.ndarray  # internal node index 0..N-1
    lng: np.ndarray
    indptr: np.ndarray  # CSR adjacency
    indices: np.ndarray
    length_m: np.ndarray
    travel_time_s: np.ndarray
    edge_ref: np.ndarray  # CSR position -> index into `edges`
    edges: list[EdgeInfo]
    kdtree: cKDTree  # over projected node coordinates, in metres
    lat0: float  # projection origin: the middle of the bbox
    # Plain lists for the Dijkstra loop, converted once at load (section 6.3).
    indptr_list: list[int]
    indices_list: list[int]
    weights_list: list[float]

    def project(self, lat, lng):
        return project(lat, lng, self.lat0)

    def contains(self, lat, lng):
        min_lng, min_lat, max_lng, max_lat = self.bbox
        return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def project(lat, lng, lat0):
    """Metres on a local plane; accurate enough at city scale."""
    x = np.asarray(lng) * math.cos(math.radians(lat0)) * M_PER_DEG_LNG_AT_EQUATOR
    y = np.asarray(lat) * M_PER_DEG_LAT
    return np.column_stack([x, y]) if np.ndim(x) else np.array([x, y])


def load_graph(path):
    """Load and validate one graph folder (graph.npz, edges.json, meta.json)."""
    path = Path(path)
    try:
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        edges_raw = json.loads((path / "edges.json").read_text(encoding="utf-8"))
        # Never unpickle (R-08): the npz holds plain numeric arrays only.
        with np.load(path / "graph.npz", allow_pickle=False) as npz:
            arrays = {name: npz[name] for name in ARRAYS}
    except FileNotFoundError as error:
        raise GraphLoadError(f"missing file in {path}: {Path(error.filename).name}") from error
    except KeyError as error:
        raise GraphLoadError(f"graph.npz in {path} lacks array {error}") from error

    version, mode, bbox = _check_meta(meta)
    edges = [EdgeInfo(edge.get("name"), edge.get("highway"), edge["coords"]) for edge in edges_raw]
    _check_arrays(arrays, len(edges))

    lat0 = (bbox[1] + bbox[3]) / 2
    weights = arrays["travel_time_s"] if mode == "drive" else arrays["length_m"]
    return RoadGraph(
        version=version,
        mode=mode,
        bbox=bbox,
        lat=arrays["lat"],
        lng=arrays["lng"],
        indptr=arrays["indptr"],
        indices=arrays["indices"],
        length_m=arrays["length_m"],
        travel_time_s=arrays["travel_time_s"],
        edge_ref=arrays["edge_ref"],
        edges=edges,
        kdtree=cKDTree(project(arrays["lat"], arrays["lng"], lat0)),
        lat0=lat0,
        indptr_list=arrays["indptr"].tolist(),
        indices_list=arrays["indices"].tolist(),
        weights_list=weights.tolist(),
    )


def _check_meta(meta):
    version, mode, bbox = meta.get("graph_version"), meta.get("mode"), meta.get("bbox")
    if not isinstance(version, str) or not version:
        raise GraphLoadError("meta.json needs graph_version")
    if mode not in MODES:
        raise GraphLoadError(f"meta.json mode must be one of {MODES}")
    if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(value, (int, float)) for value in bbox)):
        raise GraphLoadError("meta.json bbox must be [min_lng, min_lat, max_lng, max_lat]")
    if not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
        raise GraphLoadError("meta.json bbox minimums must be below its maximums")
    return version, mode, tuple(float(value) for value in bbox)


def _check_arrays(arrays, edge_count):
    nodes = len(arrays["node_ids"])
    if len(arrays["lat"]) != nodes or len(arrays["lng"]) != nodes:
        raise GraphLoadError("lat and lng must have one value per node")

    indptr = arrays["indptr"]
    if len(indptr) != nodes + 1 or indptr[0] != 0 or np.any(np.diff(indptr) < 0):
        raise GraphLoadError("indptr must start at 0, never decrease, and have nodes + 1 entries")

    slots = int(indptr[-1])
    for name in ("indices", "length_m", "travel_time_s", "edge_ref"):
        if len(arrays[name]) != slots:
            raise GraphLoadError(f"{name} must have one value per edge ({slots})")

    if slots and (arrays["indices"].min() < 0 or arrays["indices"].max() >= nodes):
        raise GraphLoadError("indices must point at existing nodes")
    if slots and (arrays["edge_ref"].min() < 0 or arrays["edge_ref"].max() >= edge_count):
        raise GraphLoadError("edge_ref must point into edges.json")
    for name in ("length_m", "travel_time_s"):
        values = arrays[name]
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise GraphLoadError(f"{name} must be finite and not negative")
