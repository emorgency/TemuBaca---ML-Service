"""Write the hand-made test graph in this folder: `python tests/fixtures/small_graph/make_fixture.py`.

Four street corners in Jakarta Pusat plus one isolated node, so tests never need OSM:

    A --Jl. Satu (primary)----- B
    |                           |
    Jl. Tiga (residential)      Jl. Dua (secondary)
    |                           |
    D --Jl. Empat (one-way D->C) C          E (no roads)
"""

import json
import math
import sys

from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from app.routing.estimate import load_speeds, travel_time_s  # noqa: E402

NODES = {  # name: (lat, lng)
    "A": (-6.1900, 106.8300),
    "B": (-6.1900, 106.8320),
    "C": (-6.1920, 106.8320),
    "D": (-6.1920, 106.8300),
    "E": (-6.1950, 106.8350),
}
STREETS = [  # (from, to, name, highway, two_way)
    ("A", "B", "Jl. Satu", "primary", True),
    ("B", "C", "Jl. Dua", "secondary", True),
    ("A", "D", "Jl. Tiga", "residential", True),
    ("D", "C", "Jl. Empat", "residential", False),
]
BBOX = [106.825, -6.200, 106.840, -6.185]


def haversine_m(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def main():
    speeds = load_speeds()
    names = list(NODES)
    index = {name: i for i, name in enumerate(names)}

    edges, slots = [], []  # slots: (source index, target index, length, edge_ref)
    for start, end, street, highway, two_way in STREETS:
        for a, b in [(start, end), (end, start)] if two_way else [(start, end)]:
            ref = len(edges)
            edges.append({"name": street, "highway": highway, "coords": [[NODES[a][1], NODES[a][0]], [NODES[b][1], NODES[b][0]]]})
            slots.append((index[a], index[b], haversine_m(NODES[a], NODES[b]), ref))
    slots.sort(key=lambda slot: slot[0])

    indptr = np.zeros(len(names) + 1, dtype=np.int64)
    for source, *_ in slots:
        indptr[source + 1] += 1
    indptr = np.cumsum(indptr)

    np.savez(
        HERE / "graph.npz",
        node_ids=np.arange(len(names), dtype=np.int64),
        lat=np.array([NODES[name][0] for name in names]),
        lng=np.array([NODES[name][1] for name in names]),
        indptr=indptr,
        indices=np.array([slot[1] for slot in slots], dtype=np.int64),
        length_m=np.array([slot[2] for slot in slots]),
        travel_time_s=np.array([travel_time_s(slot[2], edges[slot[3]]["highway"], "drive", speeds) for slot in slots]),
        edge_ref=np.array([slot[3] for slot in slots], dtype=np.int64),
    )
    (HERE / "edges.json").write_text(json.dumps(edges, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    meta = {
        "graph_version": "test-drive-2026-10-25",
        "area": "test",
        "mode": "drive",
        "bbox": BBOX,
        "nodes": len(names),
        "edges": len(slots),
        "attribution": "hand-made test fixture, not OpenStreetMap data",
    }
    (HERE / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
