"""Build a road graph offline (docs/BACKEND_PETA_RUTE.md section 6.1).

    python scripts/build_graph.py --area jakarta-tangerang --mode drive --pbf data/osm/java-latest.osm.pbf
    python scripts/build_graph.py --area jakarta-tangerang --mode drive   # from the public Overpass API

Builds the OSM street network inside the area's administrative boundaries,
cleans it, and writes data/graphs/{area}-{mode}-{YYYY-MM-DD}/ with graph.npz,
edges.json, and meta.json in the format app/routing/graph.py loads. Needs
requirements-build.txt; the runtime never imports osmnx (R-09).

Prefer --pbf with a Geofabrik extract (https://download.geofabrik.de/asia/indonesia.html):
the OSM wiki advises against public Overpass servers for areas this large, and
the result depends only on the extract file.
"""

import argparse
import json
import re
import sys
import time

from datetime import date
from pathlib import Path

import numpy as np
import osmium
import osmnx as ox
import shapely
import yaml

# Private osmnx helpers (pinned in requirements-build.txt) so a PBF build uses the
# same way filters and graph construction as graph_from_polygon.
from osmnx._errors import ResponseStatusCodeError
from osmnx._overpass import _get_network_filter
from osmnx.graph import _create_graph

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.routing.estimate import load_speeds, travel_time_s  # noqa: E402
from app.routing.graph import load_graph  # noqa: E402

COVERAGE_FILE = ROOT / "config" / "coverage.yaml"
ATTRIBUTION = "© OpenStreetMap contributors"
COORD_DECIMALS = 6

# Be polite to the public Overpass server: many small queries, spaced by its own
# slot status (overpass_rate_limit), and cached so a rerun downloads nothing twice.
ox.settings.max_query_area_size = 250_000_000  # m², about 250 km² per request
ox.settings.requests_timeout = 600
ox.settings.overpass_rate_limit = True
ox.settings.use_cache = True
ox.settings.log_console = True


def boundary(places):
    """Union of the areas' administrative boundaries, geocoded once with Nominatim."""
    gdf = ox.geocode_to_gdf(places)
    missing = [place for place, geometry in zip(places, gdf.geometry) if geometry.geom_type not in ("Polygon", "MultiPolygon")]
    if missing:
        raise SystemExit(f"no boundary polygon for: {missing}")
    return gdf.geometry.union_all()


def from_overpass(polygon, mode, attempts=5):
    # A busy public Overpass server answers 502/504; osmnx does not retry those. Each
    # retry reuses the cached chunks, so only the failed ones are requested again.
    for attempt in range(1, attempts + 1):
        try:
            return ox.graph_from_polygon(polygon, network_type=mode, simplify=True, retain_all=False, truncate_by_edge=True)
        except ResponseStatusCodeError as error:
            if attempt == attempts:
                raise
            wait = 60 * attempt
            print(f"Overpass failed ({error}); retry {attempt}/{attempts - 1} in {wait} s", flush=True)
            time.sleep(wait)


# One clause of an osmnx Overpass way filter: ["key"], ["key"~"regex"], or ["key"!~"regex"].
FILTER_CLAUSE = re.compile(r'\["([^"]+)"(?:(!?~)"([^"]*)")?\]')


def way_filter(mode):
    """Python predicate over way tags equal to osmnx's Overpass filter for `mode`.

    Overpass regexes match anywhere in the value, and ["key"!~"x"] also passes
    ways without the key, so this uses re.search and treats a missing key that way.
    """
    query = _get_network_filter(mode)
    if FILTER_CLAUSE.sub("", query):
        raise SystemExit(f"unsupported clause in the osmnx {mode} filter: {query}")
    clauses = [(key, op, re.compile(pattern)) for key, op, pattern in FILTER_CLAUSE.findall(query)]

    def keep(tags):
        for key, op, pattern in clauses:
            value = tags.get(key)
            if op == "":
                matched = value is not None
            elif op == "~":
                matched = value is not None and pattern.search(value) is not None
            else:
                matched = value is None or pattern.search(value) is None
            if not matched:
                return False
        return True

    return keep


def pbf_elements(pbf, polygon, mode, location_cache):
    """Overpass-style elements for the filtered ways with a node inside `polygon`, and their nodes."""
    keep = way_filter(mode)
    shapely.prepare(polygon)
    nodes, ways = {}, []
    # Java has about 10^8 nodes: keep their locations on disk, not in memory.
    processor = (
        osmium.FileProcessor(str(pbf))
        .with_locations(f"sparse_file_array,{location_cache}")
        .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for way in processor:
        tags = {tag.k: tag.v for tag in way.tags}
        if not keep(tags):
            continue
        points = [(node.ref, node.location) for node in way.nodes]
        if not all(location.valid() for _, location in points):
            continue  # a way cut by the extract border; never near the coverage area
        lngs = np.array([location.lon for _, location in points])
        lats = np.array([location.lat for _, location in points])
        if not shapely.contains_xy(polygon, lngs, lats).any():
            continue
        for (ref, _), lat, lng in zip(points, lats, lngs):
            nodes[ref] = (float(lat), float(lng))
        ways.append({"type": "way", "id": way.id, "nodes": [ref for ref, _ in points], "tags": tags})
    elements = [{"type": "node", "id": ref, "lat": lat, "lon": lng} for ref, (lat, lng) in nodes.items()]
    return elements + ways


def from_pbf(pbf, polygon, mode, location_cache):
    """The steps of osmnx graph_from_polygon (simplify, truncate_by_edge, largest component), from a local extract."""
    poly_proj, crs_utm = ox.projection.project_geometry(polygon)
    poly_buff, _ = ox.projection.project_geometry(poly_proj.buffer(500), crs=crs_utm, to_latlong=True)
    try:
        elements = pbf_elements(pbf, poly_buff, mode, location_cache)
    finally:
        location_cache.unlink(missing_ok=True)

    graph = _create_graph([{"elements": elements}], mode in ox.settings.bidirectional_network_types)
    del elements
    graph = ox.truncate.truncate_graph_polygon(graph, poly_buff, truncate_by_edge=True)
    graph = ox.truncate.largest_component(graph, strongly=False)
    graph = ox.simplify_graph(graph)
    graph = ox.truncate.truncate_graph_polygon(graph, polygon, truncate_by_edge=True)
    return ox.truncate.largest_component(graph, strongly=False)


def clean(graph, mode):
    if mode == "drive":
        # One-way streets are kept; drop pieces a car cannot leave or enter.
        return ox.truncate.largest_component(graph, strongly=True)
    # "walk" is already bidirectional (settings.bidirectional_network_types) and
    # has only its largest weakly connected component.
    return graph


def edge_name(data):
    name = data.get("name")
    return " / ".join(name) if isinstance(name, list) else name


def edge_coords(graph, u, v, data):
    """Polyline [lng, lat] from u to v; osmnx stores x = lng, y = lat."""
    if "geometry" in data:
        points = list(data["geometry"].coords)
    else:
        points = [(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])]
    return [[round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)] for x, y in points]


def to_arrays(graph, mode, speeds):
    osm_ids = sorted(graph.nodes)
    index = {osm_id: i for i, osm_id in enumerate(osm_ids)}

    # A two-way street is two directed edges with the same geometry; store it once,
    # oriented from the lower node index to the higher. The service reverses it as needed.
    edges, edge_index, slots = [], {}, []
    for u, v, data in graph.edges(data=True):
        a, b = index[u], index[v]
        coords = edge_coords(graph, u, v, data)
        if a > b:
            coords = coords[::-1]
        key = (min(a, b), max(a, b), tuple(map(tuple, coords)))
        if key not in edge_index:
            edge_index[key] = len(edges)
            edges.append({"name": edge_name(data), "highway": data.get("highway"), "coords": coords})
        ref = edge_index[key]
        length = float(data["length"])
        slots.append((a, b, length, travel_time_s(length, data.get("highway"), mode, speeds), ref))
    slots.sort(key=lambda slot: slot[0])

    counts = np.bincount([slot[0] for slot in slots], minlength=len(osm_ids))
    arrays = {
        "node_ids": np.array(osm_ids, dtype=np.int64),
        "lat": np.array([graph.nodes[osm_id]["y"] for osm_id in osm_ids]),
        "lng": np.array([graph.nodes[osm_id]["x"] for osm_id in osm_ids]),
        "indptr": np.concatenate([[0], np.cumsum(counts)]).astype(np.int64),
        "indices": np.array([slot[1] for slot in slots], dtype=np.int64),
        "length_m": np.array([slot[2] for slot in slots]),
        "travel_time_s": np.array([slot[3] for slot in slots]),
        "edge_ref": np.array([slot[4] for slot in slots], dtype=np.int64),
    }
    return arrays, edges


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--area", required=True)
    parser.add_argument("--mode", required=True, choices=["drive", "walk"])
    parser.add_argument("--out", type=Path, default=settings.graph_path)
    parser.add_argument("--pbf", type=Path, help="local OSM extract (.osm.pbf) to build from instead of the Overpass API")
    args = parser.parse_args()
    if args.pbf and not args.pbf.is_file():
        raise SystemExit(f"no such extract: {args.pbf}")

    areas = yaml.safe_load(COVERAGE_FILE.read_text(encoding="utf-8"))["areas"]
    if args.area not in areas:
        raise SystemExit(f"unknown area {args.area!r}; known: {sorted(areas)}")
    area = areas[args.area]
    if args.mode not in area["modes"]:
        raise SystemExit(f"area {args.area!r} is not built for mode {args.mode!r}")

    started = time.monotonic()
    polygon = boundary(area["places"])
    if args.pbf:
        graph = from_pbf(args.pbf, polygon, args.mode, args.pbf.with_suffix(".locations"))
    else:
        graph = from_overpass(polygon, args.mode)
    graph = clean(graph, args.mode)
    arrays, edges = to_arrays(graph, args.mode, load_speeds())

    built_on = date.today().isoformat()
    version = f"{args.area}-{args.mode}-{built_on}"
    folder = args.out / version
    folder.mkdir(parents=True, exist_ok=True)
    np.savez(folder / "graph.npz", **arrays)
    (folder / "edges.json").write_text(json.dumps(edges, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    min_lng, min_lat, max_lng, max_lat = polygon.bounds
    meta = {
        "graph_version": version,
        "area": args.area,
        "mode": args.mode,
        "bbox": [min_lng, min_lat, max_lng, max_lat],
        "places": area["places"],
        "source": f"extract {args.pbf.name}" if args.pbf else "Overpass API",
        "nodes": len(arrays["node_ids"]),
        "edges": len(arrays["indices"]),
        "edge_coords": "from the lower node index to the higher",
        "downloaded_on": built_on,
        "osmnx_version": ox.__version__,
        "attribution": ATTRIBUTION,
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # Load the result back with the runtime loader, so a broken build fails here.
    load_graph(folder)
    sizes = {path.name: path.stat().st_size for path in sorted(folder.iterdir())}
    print(f"{version}: {meta['nodes']:,} nodes, {meta['edges']:,} edges ({len(edges):,} distinct geometries)")
    for name, size in sizes.items():
        print(f"  {name}: {size / 1_048_576:.1f} MB")
    print(f"built in {time.monotonic() - started:.0f} s -> {folder}")


if __name__ == "__main__":
    main()
