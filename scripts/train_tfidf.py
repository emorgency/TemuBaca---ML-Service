"""Train the book model from a TemuBaca catalog snapshot (ML-T04).

Usage (from the repo root):

    # From a file written by `bun run ml:snapshot -- --out snapshot.json` in the website repo
    python scripts/train_tfidf.py --from-file snapshot.json

    # From the website endpoint; reads TEMUBACA_SNAPSHOT_URL and ML_SNAPSHOT_SECRET
    python scripts/train_tfidf.py

Artifacts go to models/ (or --out DIR). Keep snapshot files out of Git.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR  # noqa: E402
from app.training import train  # noqa: E402


def fetch_snapshot(url, token):
    """Follow nextCursor through every page of GET /api/internal/ml/snapshot."""
    pages = []
    cursor = None

    while True:
        query = {"limit": "1000"}
        if cursor:
            query["cursor"] = cursor

        request = urllib.request.Request(
            url + "?" + urllib.parse.urlencode(query),
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            page = json.loads(response.read().decode("utf-8"))["data"]

        pages.append(page)
        cursor = page.get("nextCursor")
        if not cursor:
            break

    first = pages[0]
    return {
        "version": first["version"],
        "generatedAt": first["generatedAt"],
        "books": [book for page in pages for book in page["books"]],
        "communities": first["communities"],
        "genres": first["genres"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-file", type=Path, help="snapshot JSON file")
    parser.add_argument("--out", type=Path, default=BASE_DIR / "models", help="artifact directory")
    args = parser.parse_args()

    if args.from_file:
        snapshot = json.loads(args.from_file.read_text(encoding="utf-8"))
    else:
        url = os.environ.get("TEMUBACA_SNAPSHOT_URL", "").strip()
        token = os.environ.get("ML_SNAPSHOT_SECRET", "").strip()
        if not url or not token:
            parser.error("pass --from-file, or set TEMUBACA_SNAPSHOT_URL and ML_SNAPSHOT_SECRET")
        snapshot = fetch_snapshot(url, token)

    meta = train(snapshot, args.out)
    print(
        f"{meta['model_version']}: {meta['book_count']} books, "
        f"{meta['vocabulary_size']} terms, {meta['community_count']} communities -> {args.out}"
    )
    if meta["communities_skipped_without_tags_or_region"]:
        print(f"communities skipped (no tags or region yet): {meta['communities_skipped_without_tags_or_region']}")
    if meta["genres_missing_from_vocabulary"]:
        print("genres with no matching book yet: " + ", ".join(meta["genres_missing_from_vocabulary"]))


if __name__ == "__main__":
    main()
