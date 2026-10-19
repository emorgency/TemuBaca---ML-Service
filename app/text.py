from app.model_store import tfidf


# =========================
# INTEREST NORMALIZATION
# =========================

MAX_INTERESTS = 20
MAX_INTEREST_LENGTH = 50


def normalize_interests(user_interests):
    """Trim, collapse inner whitespace, casefold, drop empties and duplicates (order kept)."""
    normalized = []
    seen = set()

    for interest in user_interests or []:
        value = " ".join(str(interest).split()).casefold()

        if value and value not in seen:
            seen.add(value)
            normalized.append(value)

    return normalized


# =========================
# TOKEN MATCHING
# =========================

# Same analyzer as the TF-IDF scores, so a reason never names an
# interest the score did not use.
_analyze = tfidf.build_analyzer()
_vocabulary = tfidf.vocabulary_


def interest_token_ids(interest):
    """Vocabulary ids of the interest's tokens; unknown tokens are skipped."""
    return [
        _vocabulary[token]
        for token in _analyze(interest)
        if token in _vocabulary
    ]


def unmatched_interests(interests):
    """Interests with no token in the TF-IDF vocabulary."""
    return [
        interest
        for interest in interests
        if not interest_token_ids(interest)
    ]


def matched_interests(interests, item_vector):
    """Interests with at least one token weighted > 0 in the item's TF-IDF row."""
    weighted = {
        int(token_id)
        for token_id, weight in zip(item_vector.indices, item_vector.data)
        if weight > 0
    }

    return [
        interest
        for interest in interests
        if any(token_id in weighted for token_id in interest_token_ids(interest))
    ]
