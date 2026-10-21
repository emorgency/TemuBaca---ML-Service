import copy
import json

import joblib
import pytest

from app.training import (
    CATALOG_FILE,
    COMMUNITIES_FILE,
    VECTORIZER_FILE,
    VECTORS_FILE,
    SnapshotError,
    load_stop_words,
    train,
)
from tests.conftest import FIXTURE


def fixture_snapshot():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_writes_consistent_artifacts(tmp_path):
    meta = train(fixture_snapshot(), tmp_path)

    vectors = joblib.load(tmp_path / VECTORS_FILE)
    vectorizer = joblib.load(tmp_path / VECTORIZER_FILE)
    rows = (tmp_path / CATALOG_FILE).read_text(encoding="utf-8").splitlines()

    assert meta["book_count"] == 24
    assert vectors.shape == (24, len(vectorizer.vocabulary_))
    assert rows[0] == "book_id,title,popularity_rank"
    assert len(rows) == 25
    assert meta["genres_missing_from_vocabulary"] == []


def test_writes_usable_communities_only(tmp_path):
    meta = train(fixture_snapshot(), tmp_path)

    rows = (tmp_path / COMMUNITIES_FILE).read_text(encoding="utf-8").splitlines()

    assert rows[0] == "community_id,name,region_code,interests"
    assert rows[1] == "c0000000-0000-4000-8000-000000000001,Lingkar Puisi Tangsel,36.74,Puisi|Sastra Indonesia"
    assert len(rows) == 6
    assert meta["community_count"] == 5
    assert meta["communities_skipped_without_tags_or_region"] == 2
    assert COMMUNITIES_FILE in meta["artifacts"]


def test_trains_without_communities(tmp_path):
    snapshot = fixture_snapshot()
    snapshot["communities"] = []

    meta = train(snapshot, tmp_path)

    assert meta["community_count"] == 0
    assert (tmp_path / COMMUNITIES_FILE).read_text(encoding="utf-8") == "community_id,name,region_code,interests\n"


def test_stop_words_cover_both_languages_without_hyphenated_entries():
    stop_words = set(load_stop_words())

    assert {"the", "and", "yang", "dan"} <= stop_words
    assert all("-" not in word for word in stop_words)


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda s: s.update(version=2), "unsupported snapshot version"),
        (lambda s: s.update(books=[]), "no books"),
        (lambda s: s["books"][1].update(id=s["books"][0]["id"]), "unique id"),
        (lambda s: s["communities"][0].update(id="C001"), "unique UUID id"),
        (lambda s: s["communities"][1].update(id=s["communities"][0]["id"]), "unique UUID id"),
        (lambda s: s["communities"][0].update(interests=["Horor"]), "unknown interests"),
        (lambda s: s["communities"][0].update(regionCode="36.99"), "unknown kab/kota"),
        # A province code is a valid region, but communities sit in a kab/kota.
        (lambda s: s["communities"][0].update(regionCode="36"), "unknown kab/kota"),
    ],
)
def test_rejects_unusable_snapshots(tmp_path, change, message):
    snapshot = copy.deepcopy(fixture_snapshot())
    change(snapshot)

    with pytest.raises(SnapshotError, match=message):
        train(snapshot, tmp_path)


def test_rejects_genre_labels_eaten_by_stop_words(tmp_path):
    snapshot = fixture_snapshot()
    snapshot["genres"].append({"slug": "uji", "label": "Yang Lain"})

    with pytest.raises(SnapshotError, match="stop words remove genre tokens"):
        train(snapshot, tmp_path)


def test_reports_genres_without_matching_books(tmp_path):
    snapshot = fixture_snapshot()
    snapshot["genres"].append({"slug": "horor", "label": "Horor"})

    meta = train(snapshot, tmp_path)

    assert meta["genres_missing_from_vocabulary"] == ["Horor"]
