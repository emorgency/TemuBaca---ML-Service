import heapq


class NoPathError(Exception):
    """The target cannot be reached from the source."""


def dijkstra(indptr, indices, weights, source, target, stats=None):
    """Return (node_path, edge_positions, total_cost) on a CSR graph.

    The edges leaving node `u` sit at CSR positions `indptr[u]..indptr[u + 1]`;
    position k leads to `indices[k]` at cost `weights[k]`. Pass sequences that
    index to plain Python numbers (lists, array.array, or a memoryview of a numpy
    array): indexing a numpy array directly is several times slower.
    When `stats` is a dict, stats["popped"] receives the number of heap pops.
    """
    if source == target:
        return [source], [], 0.0

    dist = {source: 0.0}
    # Node -> (previous node, CSR position of the edge used to reach it).
    came_from = {}
    heap = [(0.0, source)]
    popped = 0
    # Local names: this loop runs for every edge of hundreds of thousands of nodes.
    pop, push, best, inf = heapq.heappop, heapq.heappush, dist.get, float("inf")

    while heap:
        cost, node = pop(heap)
        popped += 1
        # Stop as soon as the target is settled.
        if node == target:
            if stats is not None:
                stats["popped"] = popped
            return (*_walk_back(came_from, source, target), cost)
        # Lazy deletion: this entry is stale, a cheaper one was already settled.
        if cost > dist[node]:
            continue
        for position in range(indptr[node], indptr[node + 1]):
            neighbor = indices[position]
            candidate = cost + weights[position]
            if candidate < best(neighbor, inf):
                dist[neighbor] = candidate
                came_from[neighbor] = (node, position)
                push(heap, (candidate, neighbor))

    if stats is not None:
        stats["popped"] = popped
    raise NoPathError(f"no path from {source} to {target}")


def _walk_back(came_from, source, target):
    nodes, positions = [target], []
    node = target
    while node != source:
        node, position = came_from[node]
        nodes.append(node)
        positions.append(position)
    nodes.reverse()
    positions.reverse()
    return nodes, positions
