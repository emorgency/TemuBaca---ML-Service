import joblib
import pandas as pd

from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity


# =========================
# PROJECT PATH
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent

TFIDF_PATH = BASE_DIR / "models" / "tfidf_vectorizer.joblib"


# =========================
# LOAD MODEL
# =========================

tfidf = joblib.load(TFIDF_PATH)


# =========================
# COMMUNITY DATA
# =========================

communities = pd.DataFrame([
    {
        "community_id": "C001",
        "name": "Komunitas Pecinta Fantasy",
        "interests": "fantasy magic adventure",
        "city": "Tangerang Selatan",
        "province": "Banten",
        "verified": True
    },
    {
        "community_id": "C002",
        "name": "Klub Buku Romance",
        "interests": "romance love novel",
        "city": "Jakarta Selatan",
        "province": "DKI Jakarta",
        "verified": True
    },
    {
        "community_id": "C003",
        "name": "Komunitas Mystery & Crime",
        "interests": "mystery crime thriller",
        "city": "Tangerang Selatan",
        "province": "Banten",
        "verified": True
    },
    {
        "community_id": "C004",
        "name": "Book Club Sains",
        "interests": "science technology education",
        "city": "Bandung",
        "province": "Jawa Barat",
        "verified": True
    },
    {
        "community_id": "C005",
        "name": "Komunitas Literasi Umum",
        "interests": "reading literacy books",
        "city": "Tangerang Selatan",
        "province": "Banten",
        "verified": True
    }
])


community_vectors = tfidf.transform(
    communities["interests"]
)


# =========================
# LOCATION SCORE
# =========================

def get_location_score(
    user_city,
    user_province,
    community_city,
    community_province
):
    if (
        user_city
        and community_city
        and user_city.lower() == community_city.lower()
    ):
        return 1.0

    if (
        user_province
        and community_province
        and user_province.lower() == community_province.lower()
    ):
        return 0.5

    return 0.0


# =========================
# COMMUNITY EXPLANATION
# =========================

def get_community_reason(
    user_interests,
    community,
    location_score
):
    matched_interests = []

    community_interests = str(
        community["interests"]
    ).lower()

    for interest in user_interests:
        if interest.lower() in community_interests:
            matched_interests.append(interest)

    reasons = []

    if matched_interests:
        reasons.append(
            "Sesuai dengan minat: "
            + ", ".join(matched_interests)
        )

    if location_score == 1.0:
        reasons.append("Berada di kota yang sama")

    elif location_score == 0.5:
        reasons.append("Berada di provinsi yang sama")

    if not reasons:
        return "Belum ditemukan kecocokan minat atau lokasi yang kuat"

    return " dan ".join(reasons)


# =========================
# COMMUNITY RECOMMENDATION
# =========================

def recommend_communities(
    user_interests,
    user_city=None,
    user_province=None,
    top_n=5
):
    user_text = " ".join(user_interests)

    user_vector = tfidf.transform(
        [user_text]
    )

    interest_scores = cosine_similarity(
        user_vector,
        community_vectors
    )[0]

    results = []

    for idx, community in communities.iterrows():

        location_score = get_location_score(
            user_city,
            user_province,
            community["city"],
            community["province"]
        )

        final_score = (
            0.7 * interest_scores[idx]
            + 0.3 * location_score
        )

        reason = get_community_reason(
            user_interests,
            community,
            location_score
        )

        results.append({
            "community_id": community["community_id"],
            "name": community["name"],
            "interest_score": round(
                float(interest_scores[idx]), 4
            ),
            "location_score": location_score,
            "score": round(
                float(final_score), 4
            ),
            "reason": reason
        })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:top_n]