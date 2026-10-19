import joblib

from app.config import BASE_DIR


# =========================
# SHARED MODEL ARTIFACTS
# =========================

TFIDF_PATH = BASE_DIR / "models" / "tfidf_vectorizer.joblib"

# Loaded once and shared by the book and community recommenders.
tfidf = joblib.load(TFIDF_PATH)
