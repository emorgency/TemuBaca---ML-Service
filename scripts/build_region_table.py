"""Build data/reference/wilayah_kabkota.csv from the cahyadsn/wilayah dataset.

Usage (from the repo root):

    python scripts/build_region_table.py

The source file is pinned to one commit so the table is reproducible.
Only province (NN) and kab/kota (NN.NN) rows are kept; kecamatan and
desa are more precise than location privacy needs.
"""

import csv
import json
import re
import urllib.request
from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "reference"

SOURCE_REPO = "https://github.com/cahyadsn/wilayah"
SOURCE_COMMIT = "d68e8d5516f969d1905d0b2940f20034becb0db7"
SOURCE_PATH = "db/wilayah.sql"
SOURCE_URL = (
    "https://raw.githubusercontent.com/cahyadsn/wilayah/"
    f"{SOURCE_COMMIT}/{SOURCE_PATH}"
)

ROW = re.compile(r"\('(\d{2}(?:\.\d{2})?)','([^']*)'\)")

EXPECTED_PROVINCES = 38
EXPECTED_KABKOTA = 514


def level_of(name):
    if name.startswith("Kota "):
        return "kota"
    if name.startswith("Kabupaten "):
        return "kabupaten"
    raise ValueError(f"unexpected kab/kota name: {name!r}")


def main():
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        sql = response.read().decode("utf-8")

    provinces = {}
    kabkota = []

    for code, raw_name in ROW.findall(sql):
        name = " ".join(raw_name.split())

        if len(code) == 2:
            provinces[code] = name
        else:
            kabkota.append((code, name))

    if len(provinces) != EXPECTED_PROVINCES:
        raise SystemExit(f"expected {EXPECTED_PROVINCES} provinces, got {len(provinces)}")
    if len(kabkota) != EXPECTED_KABKOTA:
        raise SystemExit(f"expected {EXPECTED_KABKOTA} kab/kota, got {len(kabkota)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUT_DIR / "wilayah_kabkota.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["code", "name", "level", "province_code", "province_name"])

        for code, name in sorted(kabkota):
            province_code = code[:2]
            writer.writerow([code, name, level_of(name), province_code, provinces[province_code]])

    with open(OUT_DIR / "wilayah_provinsi.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["code", "name"])

        for code in sorted(provinces):
            writer.writerow([code, provinces[code]])

    meta_path = OUT_DIR / "wilayah_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.update({
        "source_repo": SOURCE_REPO,
        "source_commit": SOURCE_COMMIT,
        "source_file": SOURCE_PATH,
        "source_license": "MIT",
        "regulation": "Kepmendagri No. 300.2.2-2138 Tahun 2025, diubah dengan Kepmendagri No. 300.2.2-2430 Tahun 2025",
        "downloaded_at": date.today().isoformat(),
        "province_count": len(provinces),
        "kabkota_count": len(kabkota),
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(provinces)} provinces, {len(kabkota)} kab/kota written to {OUT_DIR}")


if __name__ == "__main__":
    main()
