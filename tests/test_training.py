import copy
import json

import joblib
import pytest

from app.training import (
    CATALOG_FILE,
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
