import json
import math
import sys

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from scipy.spatial import cKDTree


MODES = ("drive", "walk")
# Format 2 keeps edge geometry in graph.npz as flat arrays; edges.json holds street names only.
GRAPH_FORMAT = 2
ARRAYS = ("node_ids", "lat", "lng", "indptr", "indices", "length_m", "travel_time_s", "edge_ref", "edge_coords", "edge_coord_offsets")

# Local equirectangular projection (section 6.2): metres per degree.
M_PER_DEG_LNG_AT_EQUATOR = 111320
M_PER_DEG_LAT = 110540


class GraphLoadError(ValueError):
    """A graph folder is missing a file or holds inconsistent data."""


@dataclass(frozen=True)
class RoadGraph:
    """A road graph in compact form: the service must fit in 512 MB with its models.

    Python objects per edge (lists of coordinates, dataclasses) cost about ten
    times the raw numbers, so everything stays in numpy arrays and Dijkstra reads
    them through memoryviews, without a second copy.
    """

    version: str
    mode: str
    bbox: tuple[float, float, float, float]  # min_lng, min_lat, max_lng, max_lat
    lat: np.ndarray  # internal node index 0..N-1
    lng: np.ndarray
    indptr: np.ndarray  # CSR adjacency
    indices: np.ndarray
    length_m: np.ndarray
    travel_time_s: np.ndarray
    edge_ref: np.ndarray  # CSR position -> edge geometry index
    edge_names: list[str | None]
    edge_coords: np.ndarray  # all polylines, [lng, lat] rows
    edge_coord_offsets: np.ndarray  # geometry i is edge_coords[offsets[i]:offsets[i + 1]]
    kdtree: cKDTree  # over projected node coordinates, in metres
    lat0: float  # projection origin: the middle of the bbox
    # Views for the Dijkstra loop (section 6.3): indexing a memoryview returns plain
    # Python numbers about as fast as a list; numpy element access is much slower.
    dijkstra_indptr: memoryview
    dijkstra_indices: memoryview
    dijkstra_weights: memoryview

    def project(self, lat, lng):
        return project(lat, lng, self.lat0)

    def contains(self, lat, lng):
        min_lng, min_lat, max_lng, max_lat = self.bbox
        return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng

    def edge_polyline(self, ref):
        """The [lng, lat] rows of one edge geometry, as stored (either direction)."""
        return self.edge_coords[self.edge_coord_offsets[ref]:self.edge_coord_offsets[ref + 1]]


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
        names = json.loads((path / "edges.json").read_text(encoding="utf-8"))
        # Never unpickle (R-08): the npz holds plain numeric arrays only.
        with np.load(path / "graph.npz", allow_pickle=False) as npz:
            arrays = {name: npz[name] for name in ARRAYS}
    except FileNotFoundError as error:
        raise GraphLoadError(f"missing file in {path}: {Path(error.filename).name}") from error
    except KeyError as error:
        raise GraphLoadError(f"graph.npz in {path} lacks array {error}; rebuild with the current scripts/build_graph.py") from error

    version, mode, bbox = _check_meta(meta)
    if not (isinstance(names, list) and all(name is None or isinstance(name, str) for name in names)):
        raise GraphLoadError("edges.json must be a list of street names (or null)")
    _check_arrays(arrays, len(names))

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
        # Street names repeat across many edges; share one string object per name.
        edge_names=[None if name is None else sys.intern(name) for name in names],
        edge_coords=arrays["edge_coords"],
        edge_coord_offsets=arrays["edge_coord_offsets"],
        kdtree=cKDTree(project(arrays["lat"], arrays["lng"], lat0)),
        lat0=lat0,
        dijkstra_indptr=memoryview(np.ascontiguousarray(arrays["indptr"], dtype=np.int64)),
        dijkstra_indices=memoryview(np.ascontiguousarray(arrays["indices"], dtype=np.int64)),
        dijkstra_weights=memoryview(np.ascontiguousarray(weights, dtype=np.float64)),
    )


def _check_meta(meta):
    version, mode, bbox = meta.get("graph_version"), meta.get("mode"), meta.get("bbox")
    if meta.get("format") != GRAPH_FORMAT:
        raise GraphLoadError(f"meta.json format must be {GRAPH_FORMAT}; rebuild with the current scripts/build_graph.py")
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

    coords, offsets = arrays["edge_coords"], arrays["edge_coord_offsets"]
    if coords.ndim != 2 or coords.shape[1] != 2 or not np.all(np.isfinite(coords)):
        raise GraphLoadError("edge_coords must be finite [lng, lat] rows")
    if (len(offsets) != edge_count + 1 or offsets[0] != 0 or offsets[-1] != len(coords)
            or np.any(np.diff(offsets) < 2)):
        raise GraphLoadError("edge_coord_offsets must split edge_coords into one polyline of 2+ points per edge")
