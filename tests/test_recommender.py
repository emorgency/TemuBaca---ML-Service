from app.recommender import (
    recommend_books,
    fallback_recommendations,
    get_recommendations
)


def test_recommend_books():
    results = recommend_books(
        ["fantasy", "magic"],
        top_n=5
    )

    assert len(results) == 5
    assert all("book_id" in item for item in results)
    assert all("title" in item for item in results)
    assert all("score" in item for item in results)
    assert all("reason" in item for item in results)


def test_fallback_recommendations():
    results = fallback_recommendations(
        top_n=5
    )

    assert len(results) == 5
    assert all(item["score"] is None for item in results)
    assert all(
        item["reason"] == "Direkomendasikan berdasarkan popularitas buku"
        for item in results
    )


def test_empty_interests_uses_fallback():
    results = get_recommendations(
        user_interests=[],
        top_n=5
    )

    assert len(results) == 5
    assert all(item["score"] is None for item in results)


def test_none_interests_uses_fallback():
    results = get_recommendations(
        user_interests=None,
        top_n=5
    )

    assert len(results) == 5


def test_top_n():
    for n in [1, 3, 5, 10]:
        results = get_recommendations(
            user_interests=["fantasy"],
            top_n=n
        )

        assert len(results) == n