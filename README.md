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
│   ├── config.py
│   ├── model_store.py
│   ├── region.py
│   ├── text.py
│   ├── recommender.py
│   ├── community.py
│   └── schemas.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── reference/
│
├── scripts/
│   └── build_region_table.py
│
├── models/
│   ├── tfidf_vectorizer.joblib
│   ├── book_vectors.joblib
│   └── meta.json
│
├── notebooks/
│   └── 01_exploration.ipynb
│
├── tests/
│   ├── test_recommender.py
│   ├── test_community.py
│   └── test_regressions.py
│
├── docs/
│   └── BACKEND_PETA_RUTE.md
│
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .env.example
├── .python-version
└── README.md
```

---

## 3. Menjalankan Service

### Prasyarat

* Python **3.14** (lihat `.python-version`). Test sudah lulus di Python 3.14.7; versi lain belum diuji.
* Model di `models/` dibuat dengan scikit-learn 1.9.1 (lihat `models/meta.json`). Test gagal jika versi scikit-learn berbeda.

Pasang dependensi:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

`requirements.txt` berisi dependensi runtime. `requirements-dev.txt` menambahkan `pytest` dan `networkx` untuk test.

Salin `.env.example` menjadi `.env` bila perlu mengubah konfigurasi. Semua nilai punya default, jadi service tetap jalan tanpa `.env`.

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
      "book_id": 4712,
      "title": "Sandry's Book (Circle of Magic, #1)",
      "score": 0.4838,
      "reason": "Sesuai dengan minat: fantasy, magic",
      "source": "interest"
    }
  ],
  "unmatched_interests": []
}
```

* `source`: `"interest"` jika buku cocok dengan minat (skor > 0), `"popularity"` jika buku ditambahkan dari urutan popularitas. Item `popularity` selalu `score: null`.
* `unmatched_interests`: minat yang tidak punya satu token pun di vocabulary model, misalnya `["romansa"]`. UI dapat menampilkan "Minat belum dikenali".

### Batas Input

* `user_interests` maksimal 20 item; setiap minat maksimal 50 karakter setelah spasi di tepi dibuang. Melebihi batas menghasilkan `422`.
* Minat kosong atau hanya spasi diabaikan.
* Minat dinormalisasi sebelum dipakai: spasi dirapikan, huruf dikecilkan (`casefold`), dan duplikat dibuang. `["Fantasy", "fantasy "]` sama dengan `["fantasy"]`.

### Cara Kerja

1. Minat pengguna dinormalisasi, lalu digabung menjadi teks.
2. Teks pengguna diubah menjadi vektor TF-IDF.
3. Vektor pengguna dibandingkan dengan vektor setiap buku menggunakan cosine similarity.
4. Hanya buku dengan skor > 0 yang dipakai, urut dari skor tertinggi. Jika skor sama, urutan mengikuti dataset.
5. Jika hasil kurang dari `top_n`, sisanya diisi buku populer yang belum terpilih (`source: "popularity"`).
6. Alasan hanya menyebut minat yang token-nya berbobot > 0 di vektor buku tersebut, memakai analyzer TF-IDF yang sama dengan skor. Minat `"lit"` tidak lagi dianggap cocok hanya karena muncul di dalam kata "literature".

### Fallback

Jika pengguna belum memiliki minat:

```json
{
  "user_interests": [],
  "top_n": 5
}
```

Sistem menggunakan rekomendasi berdasarkan popularitas buku. Semua item memakai `source: "popularity"`.

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
  "user_region_code": "36.74",
  "top_n": 5
}
```

* `user_region_code` opsional: kode kab/kota Kemendagri (`NN.NN`) atau kode provinsi saja (`NN`). Kode yang formatnya salah atau tidak ada di tabel referensi menghasilkan `422`.
* Field lain ditolak dengan `422`, termasuk `user_city` dan `user_province` yang sudah dihapus.
* Batas minat sama dengan rekomendasi buku: maksimal 20 minat, masing-masing maksimal 50 karakter.

### Response

```json
{
  "recommendations": [
    {
      "community_id": "C001",
      "name": "Komunitas Pecinta Fantasy",
      "region_code": "36.74",
      "region_name": "Kota Tangerang Selatan",
      "interest_score": 0.8486,
      "location_score": 1.0,
      "score": 0.894,
      "reason": "Sesuai dengan minat: fantasy, magic dan berada di Kota Tangerang Selatan"
    }
  ],
  "unmatched_interests": [],
  "notice": null
}
```

* Hanya komunitas dengan `score > 0` yang dikembalikan, jadi jumlahnya bisa kurang dari `top_n`.
* `notice`:
  * `NEEDS_INTERESTS_OR_LOCATION`: minat kosong dan kode wilayah tidak diberikan; `recommendations` kosong.
  * `NO_MATCH`: ada input, tapi tidak ada komunitas dengan skor > 0; `recommendations` kosong.
  * `null`: ada hasil.
* `unmatched_interests`: minat yang tidak dikenali model, sama seperti rekomendasi buku.

### Scoring

Community menggunakan formula:

```text
final_score =
    0.7 × interest_score
    + 0.3 × location_score
```

Location score:

```text
1.0 = kode kab/kota sama
0.5 = kode provinsi sama
0.0 = berbeda atau pengguna tidak memberi kode wilayah
```

Alasan minat dicocokkan per token, sama seperti rekomendasi buku.

### Kode Wilayah

Tabel referensi ada di `data/reference/`:

* `wilayah_kabkota.csv` (514 kab/kota) dan `wilayah_provinsi.csv` (38 provinsi), berdasarkan Kepmendagri No. 300.2.2-2138 Tahun 2025 yang diubah dengan No. 300.2.2-2430 Tahun 2025.
* Dibuat ulang dengan `python scripts/build_region_table.py` dari dataset `cahyadsn/wilayah` (MIT) pada commit yang di-pin.
* Sumber, lisensi, dan hasil verifikasi terhadap PDF resmi dicatat di `wilayah_meta.json`.

Sistem hanya memakai kode kab/kota dan provinsi, tidak memakai kecamatan, desa, atau koordinat.

### Perubahan Kontrak (untuk backend utama)

Breaking change dibanding versi awal:

* Request: `user_city` dan `user_province` dihapus, diganti `user_region_code`. Request lama gagal dengan `422`.
* Request: field yang tidak dikenal ditolak (`extra="forbid"`).
* Response item: tambah `region_code` dan `region_name`.
* Response: tambah `unmatched_interests` dan `notice`; daftar bisa kosong.
* Komunitas berskor 0 tidak lagi dikembalikan.
* Rekomendasi buku (aditif): item tambah `source`, response tambah `unmatched_interests`, buku berskor 0 diganti buku populer.

`API_SPEC.md` di repo website perlu diperbarui, termasuk metode `POST`.

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
29 tests passed
```

### Regression

```powershell
python -m pytest tests/test_regressions.py
```

Satu test per bug di `docs/BACKEND_PETA_RUTE.md` bagian 13.2.

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
29 passed
```
