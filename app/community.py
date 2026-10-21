from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity

from app.model_store import community_rows, tfidf
from app.region import get_region, is_kabkota
from app.text import matched_interests, normalize_interests


# =========================
# COMMUNITY DATA
# =========================

# Verified TemuBaca communities from the training snapshot (ML-T05),
# scored on their interest tags only.
communities = community_rows

# Training checked every code against the reference table; fail at startup
# if the artifact and the table disagree anyway.
community_regions = [
    get_region(code) for code in communities["region_code"]
]

if any(region is None for region in community_regions):
    raise ValueError("community region_code missing from the reference table")


def build_community_vectors(rows):
    # The transformer rejects zero rows, which is the normal state before any
    # verified community has filled in its tags and region.
    if rows.empty:
        return csr_matrix((0, len(tfidf.vocabulary_)))

    return tfidf.transform(rows["interests"].str.join(" "))


community_vectors = build_community_vectors(communities)


NEEDS_INTERESTS_OR_LOCATION = "NEEDS_INTERESTS_OR_LOCATION"
NO_MATCH = "NO_MATCH"


# =========================
# LOCATION SCORE
# =========================

def get_location_score(
    user_region,
    community_region
):
    if user_region is None:
        return 0.0

    if (
        is_kabkota(user_region)
        and user_region.code == community_region.code
    ):
        return 1.0

    if user_region.province_code == community_region.province_code:
        return 0.5

    return 0.0


# =========================
# COMMUNITY EXPLANATION
# =========================

def get_community_reason(
    user_interests,
    community_idx,
    community_region,
    location_score
):
    matched = matched_interests(
        user_interests,
        community_vectors[community_idx]
    )

    reasons = []

    if matched:
        reasons.append(
            "Sesuai dengan minat: "
            + ", ".join(matched)
        )

    if location_score == 1.0:
        reasons.append("berada di " + community_region.name)

    elif location_score == 0.5:
        reasons.append(
            "berada di provinsi " + community_region.province_name
        )

    if not reasons:
        return "Sesuai dengan minat Anda"

    reason = " dan ".join(reasons)

    return reason[:1].upper() + reason[1:]


# =========================
# COMMUNITY RECOMMENDATION
# =========================

def recommend_communities(
    user_interests,
    user_region_code=None,
    top_n=5
):
    """Communities with score > 0, best first (B-4).

    Without interests and without a region code the list is empty (R-10);
    community_notice() explains why a list is empty.
    """
    user_interests = normalize_interests(user_interests)
    user_region = get_user_region(user_region_code)

    if (not user_interests and user_region is None) or communities.empty:
        return []

    if user_interests:
        interest_scores = cosine_similarity(
            tfidf.transform([" ".join(user_interests)]),
            community_vectors
        )[0]
    else:
        interest_scores = [0.0] * len(communities)

    results = []

    for idx, community in communities.iterrows():

        community_region = community_regions[idx]

        location_score = get_location_score(
            user_region,
            community_region
        )

        final_score = round(
            0.7 * float(interest_scores[idx])
            + 0.3 * location_score,
            4
        )

        if final_score <= 0:
            continue

        results.append({
            "community_id": community["community_id"],
            "name": community["name"],
            "region_code": community_region.code,
            "region_name": community_region.name,
            "interest_score": round(
                float(interest_scores[idx]), 4
            ),
            "location_score": location_score,
            "score": final_score,
            "reason": get_community_reason(
                user_interests,
                idx,
                community_region,
                location_score
            )
        })

    # Stable sort: equal scores keep the data order.
    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:top_n]


def get_user_region(user_region_code):
    if not user_region_code:
        return None

    region = get_region(user_region_code)

    if region is None:
        raise ValueError("unknown region code")

    return region


def community_notice(
    user_interests,
    user_region_code,
    recommendations
):
    if recommendations:
        return None

    if not normalize_interests(user_interests) and not user_region_code:
        return NEEDS_INTERESTS_OR_LOCATION

    return NO_MATCH
