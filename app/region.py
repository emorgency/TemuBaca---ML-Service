import csv

from dataclasses import dataclass

from app.config import BASE_DIR


# =========================
# REGION REFERENCE (R-11)
# =========================

# Kemendagri kab/kota and province codes; see data/reference/wilayah_meta.json.
REFERENCE_DIR = BASE_DIR / "data" / "reference"

REGION_CODE_PATTERN = r"^\d{2}(\.\d{2})?$"


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    province_code: str
    province_name: str


def _load():
    with open(REFERENCE_DIR / "wilayah_provinsi.csv", encoding="utf-8", newline="") as file:
        provinces = {row["code"]: row["name"] for row in csv.DictReader(file)}

    regions = {
        code: Region(code, name, code, name)
        for code, name in provinces.items()
    }

    with open(REFERENCE_DIR / "wilayah_kabkota.csv", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            regions[row["code"]] = Region(
                row["code"],
                row["name"],
                row["province_code"],
                row["province_name"],
            )

    return regions


_regions = _load()


def get_region(code):
    """Province (`NN`) or kab/kota (`NN.NN`) for a code, or None if unknown."""
    return _regions.get(code)


def is_kabkota(region):
    return region.code != region.province_code
