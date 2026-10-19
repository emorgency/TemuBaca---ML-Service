import joblib
import numpy as np
import pandas as pd

from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

from app.model_store import tfidf
from app.text import matched_interests, normalize_interests


# =========================
# PROJECT PATH
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "books_processed.csv"
)

BOOK_VECTORS_PATH = (
    BASE_DIR
    / "models"
    / "book_vectors.joblib"
)


# =========================
# LOAD DATA & MODEL
# =========================

books_ml = pd.read_csv(DATA_PATH)

book_vectors = joblib.load(BOOK_VECTORS_PATH)


# Positional indices of all books, most popular first. The multi-column
# sort is stable, so ties keep the dataset order.
popularity_order = books_ml.sort_values(
    by=[
        "ratings_count",
        "average_rating"
    ],
    ascending=False
).index.to_numpy()

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

        "book_id": int(
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

            "book_id": int(
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