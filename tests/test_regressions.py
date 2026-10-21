"""One regression test per bug in docs/BACKEND_PETA_RUTE.md section 13.2."""

from fastapi.testclient import TestClient

from app.main import app
from app.recommender import get_recommendations
from tests.conftest import TEST_TOKEN


client = TestClient(app, headers={"X-Internal-Token": TEST_TOKEN})


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
        json={"user_interests": ["horor", "kuliner"], "top_n": 5},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["unmatched_interests"] == ["horor", "kuliner"]
    assert len(body["recommendations"]) == 5
    assert all(item["source"] == "popularity" for item in body["recommendations"])
    assert all(item["score"] is None for item in body["recommendations"])


def test_b1_site_genre_labels_are_recognized():
    # "Romansa" is a site genre label; training adds labels to the book text.
    response = client.post(
        "/api/recommendations/books",
        json={"user_interests": ["Romansa"], "top_n": 3},
    )
    body = response.json()

    assert body["unmatched_interests"] == []
    assert body["recommendations"][0]["source"] == "interest"
    assert body["recommendations"][0]["reason"] == "Sesuai dengan minat: romansa"


def test_b1_popularity_follows_bookmarks_then_listings():
    from app.recommender import fallback_recommendations

    titles = [item["title"] for item in fallback_recommendations(top_n=4)]

    # Fixture counts (bookmarks, listings): Naga (9, 2), Revolusi (8, 1),
    # Penyihir (7, 1), Sajak (6, 0).
    assert titles == ["Buku Uji Naga", "Buku Uji Revolusi", "Buku Uji Penyihir", "Buku Uji Sajak"]


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

    row_of = {book_id: idx for idx, book_id in enumerate(books_ml["book_id"])}

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


# Community tests use codes from data/reference/wilayah_kabkota.csv:
# 36.74 Kota Tangerang Selatan, 36.71 Kota Tangerang (both in Banten 36),
# 32.73 Kota Bandung (Jawa Barat 32).
# Community ids are the synthetic ones in tests/fixtures/snapshot_small.json.
PUISI_TANGSEL = "c0000000-0000-4000-8000-000000000001"
FILSAFAT_BANDUNG = "c0000000-0000-4000-8000-000000000004"

def post_communities(payload):
    return client.post("/api/recommendations/communities", json=payload)


# B-2 (communities): substring matches no longer count.

def test_b2_community_substring_is_not_a_match():
    response = post_communities({"user_interests": ["puis"]})
    body = response.json()

    assert response.status_code == 200
    assert body["recommendations"] == []
    assert body["notice"] == "NO_MATCH"


# B-3: location is matched by region code.

def test_b3_same_kabkota_scores_one():
    body = post_communities({"user_interests": ["Puisi"], "user_region_code": "36.74"}).json()
    puisi = next(item for item in body["recommendations"] if item["community_id"] == PUISI_TANGSEL)

    assert puisi["location_score"] == 1.0
    assert puisi["region_name"] == "Kota Tangerang Selatan"
    assert "berada di Kota Tangerang Selatan" in puisi["reason"]


def test_b3_same_province_scores_half():
    for code in ("36.71", "36"):
        body = post_communities({"user_interests": ["Puisi"], "user_region_code": code}).json()
        puisi = next(item for item in body["recommendations"] if item["community_id"] == PUISI_TANGSEL)

        assert puisi["location_score"] == 0.5
        assert "berada di provinsi Banten" in puisi["reason"]


def test_b3_other_province_scores_zero():
    body = post_communities({"user_interests": ["Puisi"], "user_region_code": "32.73"}).json()

    assert body["recommendations"]
    assert all(
        item["location_score"] == 0.0
        for item in body["recommendations"]
        if item["community_id"] != FILSAFAT_BANDUNG
    )


def test_b3_unknown_code_is_rejected():
    assert post_communities({"user_region_code": "36.99"}).status_code == 422


def test_b3_malformed_code_is_rejected():
    assert post_communities({"user_region_code": "36-74"}).status_code == 422


def test_b3_removed_city_field_is_rejected():
    response = post_communities({"user_interests": ["Puisi"], "user_city": "Tangerang Selatan"})

    assert response.status_code == 422


# B-4: no interests and no location gives an empty list with a notice.

def test_b4_no_interests_and_no_location_returns_notice():
    response = post_communities({"user_interests": ["  "]})
    body = response.json()

    assert response.status_code == 200
    assert body["recommendations"] == []
    assert body["notice"] == "NEEDS_INTERESTS_OR_LOCATION"


def test_b4_only_positive_scores_are_returned():
    body = post_communities({"user_interests": ["Puisi", "horor"], "top_n": 5}).json()

    assert body["recommendations"]
    assert all(item["score"] > 0 for item in body["recommendations"])
    assert body["unmatched_interests"] == ["horor"]
    assert body["notice"] is None


def test_b6_community_request_is_bounded():
    assert post_communities({"user_interests": ["x" * 51]}).status_code == 422
    assert post_communities({"user_interests": [f"m{i}" for i in range(21)]}).status_code == 422
