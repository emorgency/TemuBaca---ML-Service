# TemuBaca ML Service

Recommendation service untuk fitur rekomendasi buku dan komunitas pada TemuBaca.

## 1. Fitur

ML Service menyediakan dua fitur utama:

* Rekomendasi buku berdasarkan minat pengguna
* Rekomendasi komunitas berdasarkan minat dan lokasi umum pengguna

Metode yang digunakan:

* TF-IDF
* Cosine Similarity
* Rule-based location scoring
* Popularity fallback

---

## 2. Struktur Project

```text
ml-service/
├── app/
│   ├── main.py
│   ├── recommender.py
│   ├── community.py
│   └── schemas.py
│
├── data/
│   ├── raw/
│   └── processed/
│
├── models/
│   ├── tfidf_vectorizer.joblib
│   └── book_vectors.joblib
│
├── notebooks/
│   └── 01_exploration.ipynb
│
├── tests/
│   ├── test_recommender.py
│   └── test_community.py
│
├── requirements.txt
└── README.md
```

---

## 3. Menjalankan Service

Pastikan berada di root project:

```powershell
cd D:\TemuBaca\ml-service
```

Aktifkan virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Jalankan FastAPI:

```powershell
fastapi dev app/main.py
```

Swagger tersedia di:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
GET /health
```

---

## 4. Book Recommendation

### Endpoint

```text
POST /api/recommendations/books
```

### Request

```json
{
  "user_interests": ["fantasy", "magic"],
  "top_n": 5
}
```

### Response

```json
{
  "recommendations": [
    {
      "book_id": 1230,
      "title": "Before They Are Hanged",
      "score": 0.4329,
      "reason": "Sesuai dengan minat: fantasy, magic"
    }
  ]
}
```

### Cara Kerja

1. Minat pengguna digabung menjadi teks.
2. Teks pengguna diubah menjadi vektor TF-IDF.
3. Vektor pengguna dibandingkan dengan vektor setiap buku menggunakan cosine similarity.
4. Buku dengan similarity tertinggi diprioritaskan.
5. Sistem memberikan alasan rekomendasi berdasarkan minat yang cocok.

### Fallback

Jika pengguna belum memiliki minat:

```json
{
  "user_interests": [],
  "top_n": 5
}
```

Sistem menggunakan rekomendasi berdasarkan popularitas buku.

---

## 5. Community Recommendation

### Endpoint

```text
POST /api/recommendations/communities
```

### Request

```json
{
  "user_interests": ["fantasy", "magic"],
  "user_city": "Tangerang Selatan",
  "user_province": "Banten",
  "top_n": 5
}
```

### Response

```json
{
  "recommendations": [
    {
      "community_id": "C001",
      "name": "Komunitas Pecinta Fantasy",
      "interest_score": 0.8486,
      "location_score": 1.0,
      "score": 0.894,
      "reason": "Sesuai dengan minat: fantasy, magic dan Berada di kota yang sama"
    }
  ]
}
```

### Scoring

Community menggunakan formula:

```text
final_score =
    0.7 × interest_score
    + 0.3 × location_score
```

Location score:

```text
1.0 = kota sama
0.5 = provinsi sama
0.0 = berbeda
```

Sistem hanya menggunakan lokasi umum seperti kota dan provinsi.

---

## 6. Testing

### Book Recommendation

```powershell
python -m pytest tests/test_recommender.py
```

Hasil:

```text
5 passed
```

### Community Recommendation

```powershell
python -m pytest tests/test_community.py
```

Hasil:

```text
5 passed
```

### Total

```text
10 tests passed
```

---

## 7. Dataset

Baseline recommendation menggunakan dataset **Goodbooks-10k**.

Data yang digunakan:

* `books.csv`
* `book_tags.csv`
* `tags.csv`

Dataset digunakan sebagai data pengembangan/baseline dan tidak dianggap sebagai representasi penuh preferensi pembaca Indonesia.

---

## 8. Model

Model recommendation menggunakan pendekatan **content-based recommendation**.

### Alur Model

```text
Book Metadata
     ↓
Combined Text
     ↓
TF-IDF
     ↓
Book Vectors
     ↓
Cosine Similarity
     ↓
Recommendation Ranking
```

Model yang disimpan:

```text
models/tfidf_vectorizer.joblib
models/book_vectors.joblib
```

---

## 9. Integration Notes

ML Service saat ini menggunakan `book_id` dari dataset Goodbooks-10k.

`book_id` tersebut belum sama dengan `Book.id` UUID pada database TemuBaca.

Oleh karena itu, sebelum production integration diperlukan mapping:

```text
Goodbooks book_id
       ↓
Book identifier TemuBaca
       ↓
Book.id UUID
```

Community ID seperti `C001`, `C002`, `C003`, dan seterusnya juga masih merupakan data demo ML dan perlu diganti atau dihubungkan dengan ID community dari database TemuBaca.

---

## 10. Limitations

* Goodbooks-10k digunakan sebagai baseline dan bukan representasi khusus pengguna Indonesia.
* Rekomendasi buku saat ini berbasis metadata/minat, bukan collaborative filtering.
* Belum menggunakan histori interaksi pengguna sebagai model utama.
* Mapping Goodbooks `book_id` ke `Book.id` TemuBaca belum tersedia.
* Data community saat ini masih berupa data demo.
* Nilai cosine similarity merupakan skor kemiripan, bukan persentase akurasi.

---

## 11. API Summary

| Method | Endpoint                           | Fungsi                  |
| ------ | ---------------------------------- | ----------------------- |
| GET    | `/health`                          | Mengecek status service |
| POST   | `/api/recommendations/books`       | Rekomendasi buku        |
| POST   | `/api/recommendations/communities` | Rekomendasi komunitas   |

---

## 12. Model Version

**Current Model:**

```text
TF-IDF Content-Based Recommendation
Version: 1.0
```

---

## 13. Final Test

Untuk menjalankan seluruh automated test:

```powershell
python -m pytest tests
```

Expected result:

```text
10 passed
```
