from app.routing.errors import RoutingError


def snap(graph, lat, lng, max_m, point):
    """Nearest graph node to a coordinate and its distance in metres (section 6.5).

    `point` ("origin" or "destination") names the offending end in the error.
    """
    if not graph.contains(lat, lng):
        raise RoutingError("OUT_OF_COVERAGE", point)
    offset_m, node = graph.kdtree.query(graph.project(lat, lng))
    if offset_m > max_m:
        raise RoutingError("SNAP_TOO_FAR", point)
    return int(node), float(offset_m)
