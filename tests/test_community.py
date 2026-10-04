from app.community import recommend_communities


def test_recommend_communities():
    results = recommend_communities(
        user_interests=["fantasy", "magic"],
        user_city="Tangerang Selatan",
        user_province="Banten",
        top_n=5
    )

    assert len(results) == 5
    assert all("community_id" in item for item in results)
    assert all("name" in item for item in results)
    assert all("interest_score" in item for item in results)
    assert all("location_score" in item for item in results)
    assert all("score" in item for item in results)
    assert all("reason" in item for item in results)


def test_interest_match_ranks_first():
    results = recommend_communities(
        user_interests=["fantasy", "magic"],
        user_city="Tangerang Selatan",
        user_province="Banten",
        top_n=5
    )

    assert results[0]["community_id"] == "C001"


def test_location_score():
    results = recommend_communities(
        user_interests=["fantasy", "magic"],
        user_city="Tangerang Selatan",
        user_province="Banten",
        top_n=5
    )

    c001 = results[0]

    assert c001["location_score"] == 1.0
    assert c001["score"] == 0.894


def test_top_n():
    for n in [1, 3, 5]:
        results = recommend_communities(
            user_interests=["fantasy"],
            user_city="Tangerang Selatan",
            user_province="Banten",
            top_n=n
        )

        assert len(results) == n


def test_empty_interests():
    results = recommend_communities(
        user_interests=[],
        user_city="Tangerang Selatan",
        user_province="Banten",
        top_n=5
    )

    assert len(results) == 5

    for item in results:
        assert item["interest_score"] == 0