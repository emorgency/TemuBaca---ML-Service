# Error codes of POST /api/routing/route (docs/BACKEND_PETA_RUTE.md section 5.3).
# Messages are shown to readers, so they are in Indonesian.
ERRORS = {
    "INVALID_PARAMS": (422, "Parameter rute tidak valid."),
    "OUT_OF_COVERAGE": (422, "Titik berada di luar cakupan rute."),
    "SNAP_TOO_FAR": (422, "Titik terlalu jauh dari jalan yang dipetakan."),
    "NO_PATH": (404, "Rute tidak ditemukan."),
    "UNAUTHORIZED": (401, "Token internal tidak valid."),
    "ROUTING_UNAVAILABLE": (503, "Layanan rute belum tersedia."),
    "INTERNAL": (500, "Terjadi kesalahan pada layanan rute."),
}


class RoutingError(Exception):
    """A routing failure with a stable code; `point` is "origin" or "destination" when one is at fault."""

    def __init__(self, code, point=None):
        status, message = ERRORS[code]
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message
        self.point = point
