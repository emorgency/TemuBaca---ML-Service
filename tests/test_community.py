import pytest

from app import community
from app.community import recommend_communities


# Kota Tangerang Selatan in data/reference/wilayah_kabkota.csv.
TANGSEL = "36.74"

# Communities in tests/fixtures/snapshot_small.json.
PUISI_TANGSEL = "c0000000-0000-4000-8000-000000000001"
SEJARAH_TANGSEL = "c0000000-0000-4000-8000-000000000003"
BACA_TANGSEL = "c0000000-0000-4000-8000-000000000005"
WITHOUT_TAGS = "c0000000-0000-4000-8000-000000000006"
WITHOUT_REGION = "c0000000-0000-4000-8000-000000000007"


def test_recommend_communities():
    results = recommend_communities(
        user_interests=["Puisi"],
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


def test_communities_come_from_the_snapshot():
    ids = list(community.communities["community_id"])

    assert len(ids) == 5
    assert ids == sorted(ids)
    # Communities without tags or a region are skipped until they fill them in.
    assert WITHOUT_TAGS not in ids
    assert WITHOUT_REGION not in ids


def test_interest_match_ranks_first():
    results = recommend_communities(
        user_interests=["Puisi"],
        user_region_code=TANGSEL,
        top_n=5
    )

    assert results[0]["community_id"] == PUISI_TANGSEL
    # Interests are normalized to lowercase; the website maps them back to its labels.
    assert results[0]["reason"] == "Sesuai dengan minat: puisi dan berada di Kota Tangerang Selatan"


def test_location_score():
    results = recommend_communities(
        user_interests=["Puisi"],
        user_region_code=TANGSEL,
        top_n=5
    )

    first = results[0]

    assert first["location_score"] == 1.0
    # The exact value depends on the trained model, so check the formula.
    assert first["score"] == pytest.approx(
        0.7 * first["interest_score"] + 0.3 * 1.0, abs=1e-4
    )


def test_top_n():
    for n in [1, 3, 5]:
        results = recommend_communities(
            user_interests=["Sejarah"],
            user_region_code=TANGSEL,
            top_n=n
        )

        assert len(results) <= n

    # More candidates than n: the list is cut to exactly n.
    assert len(recommend_communities(["Sejarah"], TANGSEL, top_n=2)) == 2


def test_empty_interests():
    results = recommend_communities(
        user_interests=[],
        user_region_code=TANGSEL,
        top_n=5
    )

    # Only the location matches remain, in id order, and none of them has an
    # interest score.
    assert [item["community_id"] for item in results] == [PUISI_TANGSEL, SEJARAH_TANGSEL, BACA_TANGSEL]

    for item in results:
        assert item["interest_score"] == 0


def test_no_communities_yet(monkeypatch):
    empty = community.communities.iloc[0:0]
    monkeypatch.setattr(community, "communities", empty)
    monkeypatch.setattr(community, "community_regions", [])
    monkeypatch.setattr(community, "community_vectors", community.build_community_vectors(empty))

    results = recommend_communities(["Puisi"], TANGSEL, top_n=5)

    assert results == []
    assert community.community_notice(["Puisi"], TANGSEL, results) == community.NO_MATCH
