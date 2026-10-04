import joblib
import numpy as np
import pandas as pd

from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity


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

TFIDF_PATH = (
    BASE_DIR
    / "models"
    / "tfidf_vectorizer.joblib"
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

tfidf = joblib.load(TFIDF_PATH)

book_vectors = joblib.load(BOOK_VECTORS_PATH)


# =========================
# EXPLANATION
# =========================

def get_reason(user_interests, book_idx):

    book_text = str(
        books_ml.iloc[book_idx]["combined_text"]
    ).lower()

    matched_interests = []

    for interest in user_interests:

        if interest.lower() in book_text:
            matched_interests.append(interest)

    if matched_interests:

        return (
            "Sesuai dengan minat: "
            + ", ".join(matched_interests)
        )

    return "Memiliki kemiripan dengan minat Anda"


# =========================
# BOOK RECOMMENDATION
# =========================

def recommend_books(
    user_interests,
    top_n=10
):

    user_text = " ".join(user_interests)

    user_vector = tfidf.transform(
        [user_text]
    )

    scores = cosine_similarity(
        user_vector,
        book_vectors
    )[0]

    top_indices = np.argsort(
        scores
    )[::-1][:top_n]

    recommendations = []

    for idx in top_indices:

        recommendations.append({

            "book_id": int(
                books_ml.iloc[idx]["book_id"]
            ),

            "title": books_ml.iloc[idx]["title"],

            "score": round(
                float(scores[idx]),
                4
            ),

            "reason": get_reason(
                user_interests,
                idx
            )
        })

    return recommendations


# =========================
# FALLBACK
# =========================

def fallback_recommendations(
    top_n=10
):

    popular_books = books_ml.sort_values(
        by=[
            "ratings_count",
            "average_rating"
        ],
        ascending=False
    ).head(top_n)

    recommendations = []

    for _, book in popular_books.iterrows():

        recommendations.append({

            "book_id": int(
                book["book_id"]
            ),

            "title": book["title"],

            "score": None,

            "reason": (
                "Direkomendasikan berdasarkan "
                "popularitas buku"
            )
        })

    return recommendations


# =========================
# MAIN RECOMMENDATION
# =========================

def get_recommendations(
    user_interests=None,
    top_n=10
):

    if not user_interests:

        return fallback_recommendations(
            top_n
        )

    return recommend_books(
        user_interests,
        top_n
    )