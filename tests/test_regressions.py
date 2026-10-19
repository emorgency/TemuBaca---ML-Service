"""One regression test per bug in docs/BACKEND_PETA_RUTE.md section 13.2."""

from fastapi.testclient import TestClient

from app.main import app
from app.recommender import get_recommendations


client = TestClient(app)


# B-5: interests are normalized before scoring and in reasons.

def test_b5_duplicate_and_blank_interests_are_normalized():
    messy = get_recommendations(["Fantasy", "fantasy ", "  "], top_n=5)
    clean = get_recommendations(["fantasy"], top_n=5)

    assert messy == clean
    assert all("Fantasy" not in item["reason"] for item in messy)


# B-6: request size is bounded.

def test_b6_more_than_20_interests_is_rejected():
    response = client.post(
        "/api/recommendations/books",
        json={"user_interests": [f"minat{i}" for i in range(21)]},
    )

    assert response.status_code == 422


def test_b6_interest_longer_than_50_characters_is_rejected():
    response = client.post(
        "/api/recommendations/books",
        json={"user_interests": ["x" * 51]},
    )

    assert response.status_code == 422


def test_b6_limits_are_inclusive_and_blanks_are_dropped():
    response = client.post(
        "/api/recommendations/books",
        json={"user_interests": ["x" * 50, "   "] + ["fantasy"] * 18, "top_n": 3},
    )

    assert response.status_code == 200


# B-1: zero-score books are never presented as interest matches.

def test_b1_unknown_interests_fall_back_to_popularity():
    response = client.post(
        "/api/recommendations/books",
        json={"user_interests": ["romansa", "horor"], "top_n": 5},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["unmatched_interests"] == ["romansa", "horor"]
    assert len(body["recommendations"]) == 5
    assert all(item["source"] == "popularity" for item in body["recommendations"])
    assert all(item["score"] is None for item in body["recommendations"])


def test_b1_sparse_matches_are_topped_up_without_duplicates():
    results = get_recommendations(["pramoedya"], top_n=20)
    interest = [item for item in results if item["source"] == "interest"]
    popularity = [item for item in results if item["source"] == "popularity"]

    assert len(results) == 20
    assert interest, "pramoedya is in the vocabulary and should match"
    assert all(item["score"] > 0 for item in interest)
    assert all(item["score"] is None for item in popularity)
    assert results[: len(interest)] == interest
    assert len({item["book_id"] for item in results}) == 20


def test_b1_interest_items_are_sorted_by_score():
    results = get_recommendations(["fantasy", "magic"], top_n=20)
    scores = [item["score"] for item in results if item["source"] == "interest"]

    assert scores == sorted(scores, reverse=True)


# B-2: reasons name only interests whose tokens weigh > 0 in the book.

def test_b2_reasons_match_tokens_not_substrings():
    from app.recommender import book_vectors, books_ml
    from app.text import interest_token_ids

    row_of = {int(book_id): idx for idx, book_id in enumerate(books_ml["book_id"])}

    for interests in (["lit"], ["lit", "fantasy"], ["sejarah", "magic"]):
        for item in get_recommendations(interests, top_n=20):
            if item["source"] != "interest":
                continue

            prefix = "Sesuai dengan minat: "
            assert item["reason"].startswith(prefix)

            weighted = set(book_vectors[row_of[item["book_id"]]].indices)
            for named in item["reason"][len(prefix):].split(", "):
                assert named in interests
                assert weighted & set(interest_token_ids(named))


# General: the same request gives the same response.

def test_same_request_gives_identical_response():
    payload = {"user_interests": ["fantasy", "sejarah", "romansa"], "top_n": 10}

    first = client.post("/api/recommendations/books", json=payload).json()
    second = client.post("/api/recommendations/books", json=payload).json()

    assert first == second
