import json

import joblib
import pandas as pd

from app.config import settings
from app.training import CATALOG_FILE, META_FILE, VECTORIZER_FILE, VECTORS_FILE


# =========================
# SHARED MODEL ARTIFACTS
# =========================

# Built by scripts/train_tfidf.py; MODEL_DIR points elsewhere in tests.
MODEL_DIR = settings.model_path

# Loaded once and shared by the book and community recommenders.
tfidf = joblib.load(MODEL_DIR / VECTORIZER_FILE)

book_vectors = joblib.load(MODEL_DIR / VECTORS_FILE)

# Row i of book_vectors is catalog row i (books sorted by id).
catalog = pd.read_csv(
    MODEL_DIR / CATALOG_FILE,
    dtype={"book_id": str, "title": str, "popularity_rank": int},
    keep_default_na=False,
)

model_meta = json.loads((MODEL_DIR / META_FILE).read_text(encoding="utf-8"))

if book_vectors.shape[0] != len(catalog):
    raise ValueError("book_vectors and catalog_books.csv have different row counts")
