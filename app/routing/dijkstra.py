import heapq


class NoPathError(Exception):
    """The target cannot be reached from the source."""


def dijkstra(indptr, indices, weights, source, target):
    """Return (node_path, edge_positions, total_cost) on a CSR graph.

    The edges leaving node `u` sit at CSR positions `indptr[u]..indptr[u + 1]`;
    position k leads to `indices[k]` at cost `weights[k]`. Pass Python lists:
    the road graph converts its arrays once when it is loaded, not per request.
    """
    if source == target:
        return [source], [], 0.0

    dist = {source: 0.0}
    # Node -> (previous node, CSR position of the edge used to reach it).
    came_from = {}
    heap = [(0.0, source)]

    while heap:
        cost, node = heapq.heappop(heap)
        # Stop as soon as the target is settled.
        if node == target:
            return (*_walk_back(came_from, source, target), cost)
        # Lazy deletion: this entry is stale, a cheaper one was already settled.
        if cost > dist[node]:
            continue
        for position in range(indptr[node], indptr[node + 1]):
            neighbor = indices[position]
            candidate = cost + weights[position]
            if candidate < dist.get(neighbor, float("inf")):
                dist[neighbor] = candidate
                came_from[neighbor] = (node, position)
                heapq.heappush(heap, (candidate, neighbor))

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
