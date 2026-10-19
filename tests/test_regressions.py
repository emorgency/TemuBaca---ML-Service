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
