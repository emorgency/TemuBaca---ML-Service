"""Benchmark Dijkstra on a built graph (docs/BACKEND_PETA_RUTE.md section 10.4).

    python scripts/bench_route.py --graph jakarta-tangerang-drive-2026-10-25 --n 500

Routes between random node pairs (fixed seed) and reports p50, p95, and max
latency, mean nodes popped, graph size, and process memory after loading.
Runs each pair three times: over the memoryviews the service uses,
over plain Python lists, and over the raw numpy arrays (section 6.3).
"""

import argparse
import random
import resource
import statistics
import sys
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.routing.dijkstra import NoPathError, dijkstra  # noqa: E402
from app.routing.graph import load_graph  # noqa: E402


def memory_mb():
    with open("/proc/self/statm") as file:
        return int(file.read().split()[1]) * resource.getpagesize() / 1_048_576


def run(label, pairs, indptr, indices, weights):
    latencies, popped, missing = [], [], 0
    quarter = max(len(pairs) // 4, 1)
    for done, (source, target) in enumerate(pairs, start=1):
        stats = {}
        started = time.perf_counter()
        try:
            dijkstra(indptr, indices, weights, source, target, stats)
        except NoPathError:
            missing += 1
        latencies.append((time.perf_counter() - started) * 1000)
        popped.append(stats["popped"])
        if done % quarter == 0 or done == len(pairs):
            print(f"  {label}: {done}/{len(pairs)} pairs ({done * 100 // len(pairs)}%), "
                  f"median so far {statistics.median(latencies):.1f} ms", flush=True)
    return latencies, popped, missing


def report(label, latencies, popped, missing):
    p95 = statistics.quantiles(latencies, n=20)[-1]
    print(
        f"{label:<7} p50 {statistics.median(latencies):7.1f} ms   p95 {p95:7.1f} ms   max {max(latencies):7.1f} ms"
        f"   popped {statistics.mean(popped):,.0f} on average   no path {missing}",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--graph", required=True, help="folder name under GRAPH_DIR")
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261025)
    args = parser.parse_args()

    before = memory_mb()
    started = time.perf_counter()
    graph = load_graph(settings.graph_path / args.graph)
    print(f"{graph.version}: {len(graph.lat):,} nodes, {graph.dijkstra_indptr[-1]:,} edges, "
          f"loaded in {time.perf_counter() - started:.1f} s, +{memory_mb() - before:,.0f} MB "
          f"({memory_mb():,.0f} MB process)", flush=True)

    rng = random.Random(args.seed)
    nodes = len(graph.lat)
    pairs = [(rng.randrange(nodes), rng.randrange(nodes)) for _ in range(args.n)]
    print(f"{args.n} random pairs, seed {args.seed}, weights: {'travel_time_s' if graph.mode == 'drive' else 'length_m'}", flush=True)

    report("views", *run("views", pairs, graph.dijkstra_indptr, graph.dijkstra_indices, graph.dijkstra_weights))
    report("lists", *run("lists", pairs, graph.dijkstra_indptr.tolist(), graph.dijkstra_indices.tolist(), graph.dijkstra_weights.tolist()))
    weights = graph.travel_time_s if graph.mode == "drive" else graph.length_m
    report("numpy", *run("numpy", pairs, graph.indptr, graph.indices, weights))


if __name__ == "__main__":
    main()
