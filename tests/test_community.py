import pytest

from app.community import recommend_communities


# Kota Tangerang Selatan in data/reference/wilayah_kabkota.csv.
TANGSEL = "36.74"


def test_recommend_communities():
    results = recommend_communities(
        user_interests=["fantasy", "magic"],
        user_region_code=TANGSEL,
        top_n=5
    )

    # Only communities with score > 0 are returned (B-4), so the list can be
    # shorter than top_n.
    assert 0 < len(results) <= 5
    assert all("community_id" in item for item in results)
    assert all("name" in item for item in results)
    assert all("interest_score" in item for item in results)
    assert all("location_score" in item for item in results)
    assert all("score" in item for item in results)
    assert all("reason" in item for item in results)


def test_interest_match_ranks_first():
    results = recommend_communities(
        user_interests=["fantasy", "magic"],
        user_region_code=TANGSEL,
        top_n=5
    )

    assert results[0]["community_id"] == "C001"


def test_location_score():
    results = recommend_communities(
        user_interests=["fantasy", "magic"],
        user_region_code=TANGSEL,
        top_n=5
    )

    c001 = results[0]

    assert c001["location_score"] == 1.0
    assert c001["score"] == pytest.approx(0.894)


def test_top_n():
    for n in [1, 3, 5]:
        results = recommend_communities(
            user_interests=["fantasy"],
            user_region_code=TANGSEL,
            top_n=n
        )

        assert len(results) <= n

    # More candidates than n: the list is cut to exactly n.
    assert len(recommend_communities(["fantasy"], TANGSEL, top_n=2)) == 2


def test_empty_interests():
    results = recommend_communities(
        user_interests=[],
        user_region_code=TANGSEL,
        top_n=5
    )

    # Only the location matches remain, and none of them has an interest score.
    assert [item["community_id"] for item in results] == ["C001", "C003", "C005"]

    for item in results:
        assert item["interest_score"] == 0
