import yaml

from app.config import BASE_DIR


SPEEDS_FILE = BASE_DIR / "config" / "speeds.yaml"


def load_speeds(path=SPEEDS_FILE):
    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file)


def speed_kmh(highway, mode, speeds):
    """Assumed speed for an OSM `highway` value; osmnx may give a list, and the fastest class wins."""
    if mode == "walk":
        return speeds["walk_kmh"]
    classes = highway if isinstance(highway, list) else [highway]
    return max(speeds["drive_kmh"].get(name, speeds["drive_default_kmh"]) for name in classes)


def travel_time_s(length_m, highway, mode, speeds):
    return length_m / (speed_kmh(highway, mode, speeds) / 3.6)


def round_distance_m(meters):
    """Reported distances are rounded to 10 m (section 5.2)."""
    return int(round(meters / 10) * 10)


def round_duration_s(seconds):
    """Reported durations are rounded to 30 seconds (section 5.2)."""
    return int(round(seconds / 30) * 30)
