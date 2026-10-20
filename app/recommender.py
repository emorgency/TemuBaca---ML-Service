import numpy as np

from sklearn.metrics.pairwise import cosine_similarity

from app.model_store import book_vectors, catalog, tfidf
from app.text import matched_interests, normalize_interests


# =========================
# CATALOG
# =========================

# Kept under this name for callers that read book rows by position.
books_ml = catalog


# Positional indices of all books, most popular first (bookmarks, then
# listings, then id; ranked at training time).
popularity_order = np.argsort(
    catalog["popularity_rank"].to_numpy(),
    kind="stable"
)

POPULARITY_REASON = (
    "Direkomendasikan berdasarkan "
    "popularitas buku"
)


# =========================
# EXPLANATION
# =========================

def get_reason(user_interests, book_idx):

    matched = matched_interests(
        user_interests,
        book_vectors[book_idx]
    )

    if matched:

        return (
            "Sesuai dengan minat: "
            + ", ".join(matched)
        )

    return "Sesuai dengan minat Anda"


def popularity_item(book_idx):

    return {

        "book_id": str(
            books_ml.iloc[book_idx]["book_id"]
        ),

        "title": books_ml.iloc[book_idx]["title"],

        "score": None,

        "reason": POPULARITY_REASON,

        "source": "popularity"
    }


# =========================
# BOOK RECOMMENDATION
# =========================

def recommend_books(
    user_interests,
    top_n=10
):

    user_interests = normalize_interests(user_interests)

    if not user_interests:

        return fallback_recommendations(
            top_n
        )

    user_text = " ".join(user_interests)

    user_vector = tfidf.transform(
        [user_text]
    )

    scores = cosine_similarity(
        user_vector,
        book_vectors
    )[0]

    # Only books whose rounded score is still above zero count as matches,
    # so no "interest" item is ever shown with score 0.0.
    rounded = np.round(scores, 4)
    positive = np.flatnonzero(rounded > 0)

    # Highest score first; equal scores keep the dataset order.
    picked = positive[
        np.lexsort((positive, -scores[positive]))
    ][:top_n]

    recommendations = []

    for idx in picked:

        recommendations.append({

            "book_id": str(
                books_ml.iloc[idx]["book_id"]
            ),

            "title": books_ml.iloc[idx]["title"],

            "score": float(rounded[idx]),

            "reason": get_reason(
                user_interests,
                idx
            ),

            "source": "interest"
        })

    if len(recommendations) < top_n:

        chosen = {int(idx) for idx in picked}

        for idx in popularity_order:

            if len(recommendations) >= top_n:
                break

            if int(idx) not in chosen:
                recommendations.append(
                    popularity_item(idx)
                )

    return recommendations


# =========================
# FALLBACK
# =========================

def fallback_recommendations(
    top_n=10
):

    return [
        popularity_item(idx)
        for idx in popularity_order[:top_n]
    ]


# =========================
# MAIN RECOMMENDATION
# =========================

def get_recommendations(
    user_interests=None,
    top_n=10
):

    user_interests = normalize_interests(user_interests)

    if not user_interests:

        return fallback_recommendations(
            top_n
        )

    return recommend_books(
        user_interests,
        top_n
    )