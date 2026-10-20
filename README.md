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
│   ├── training.py
│   ├── security.py
│   ├── recommender.py
│   ├── community.py
│   └── schemas.py
│
├── data/
│   └── reference/
│
├── scripts/
│   ├── build_region_table.py
│   └── train_tfidf.py
│
├── models/
│   ├── tfidf_vectorizer.joblib
│   ├── book_vectors.joblib
│   ├── catalog_books.csv
│   └── meta.json
│
├── tests/
│   ├── test_recommender.py
│   ├── test_community.py
│   ├── test_regressions.py
│   ├── test_training.py
│   ├── test_security.py
│   ├── conftest.py
│   └── fixtures/snapshot_small.json
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

Salin `.env.example` menjadi `.env`, lalu isi `INTERNAL_TOKEN` (minimal 32 karakter):

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

### Token Internal

Semua endpoint `/api/*` wajib mengirim header `X-Internal-Token` yang sama dengan `INTERNAL_TOKEN`:

* Token salah atau tidak ada: `401`.
* `INTERNAL_TOKEN` kosong: semua `/api/*` membalas `503` (fail-closed). `/health` tetap terbuka.
* Token kurang dari 32 karakter: service gagal start.

Website TemuBaca mengirim token ini dari env `RECOMMENDATION_API_KEY`, jadi nilai keduanya harus sama. Service ini hanya dipanggil server ke server: tidak ada CORS, dan body request `/api/*` lebih dari 8 KB ditolak dengan `413`.

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
      "book_id": "927fb32b-5e53-4c6c-8ee4-df8bb87b212a",
      "title": "Sejarah sastra Indonesia",
      "score": 0.5541,
      "reason": "Sesuai dengan minat: sejarah, sastra indonesia",
      "source": "interest"
    }
  ],
  "unmatched_interests": []
}
```

* `book_id`: UUID buku di katalog TemuBaca (`books.id`).
* `source`: `"interest"` jika buku cocok dengan minat (skor > 0), `"popularity"` jika buku ditambahkan dari urutan popularitas. Item `popularity` selalu `score: null`.
* `unmatched_interests`: minat yang tidak punya satu token pun di vocabulary model, misalnya `["horor"]` selama belum ada buku bergenre itu. UI dapat menampilkan "Minat belum dikenali".

### Batas Input

* `user_interests` maksimal 20 item; setiap minat maksimal 50 karakter setelah spasi di tepi dibuang. Melebihi batas menghasilkan `422`.
* Minat kosong atau hanya spasi diabaikan.
* Minat dinormalisasi sebelum dipakai: spasi dirapikan, huruf dikecilkan (`casefold`), dan duplikat dibuang. `["Fantasy", "fantasy "]` sama dengan `["fantasy"]`.

### Cara Kerja

1. Minat pengguna dinormalisasi, lalu digabung menjadi teks.
2. Teks pengguna diubah menjadi vektor TF-IDF.
3. Vektor pengguna dibandingkan dengan vektor setiap buku menggunakan cosine similarity.
4. Hanya buku dengan skor > 0 yang dipakai, urut dari skor tertinggi. Jika skor sama, urutan mengikuti `book_id`.
5. Jika hasil kurang dari `top_n`, sisanya diisi buku populer yang belum terpilih (`source: "popularity"`). Popularitas = jumlah bookmark, lalu jumlah listing aktif, lalu `book_id`.
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
* Rekomendasi buku: `book_id` kini UUID string TemuBaca (sebelumnya integer Goodbooks; breaking). Item tambah `source`, response tambah `unmatched_interests`, buku berskor 0 diganti buku populer.

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
45 tests passed
```

### Regression

```powershell
python -m pytest tests/test_regressions.py
```

Satu test per bug di `docs/BACKEND_PETA_RUTE.md` bagian 13.2.

---

## 7. Data Katalog

Model dilatih dari **snapshot katalog TemuBaca** (endpoint `GET /api/internal/ml/snapshot` di website, atau file dari `bun run ml:snapshot -- --out <file>`). Snapshot hanya berisi data publik: judul, penulis, deskripsi, subjek provider, label genre situs, serta jumlah bookmark dan listing per buku.

File snapshot **tidak** di-commit. Yang di-commit hanya artefak model dan `models/catalog_books.csv` (`book_id`, `title`, `popularity_rank`).

---

## 8. Model

Model recommendation menggunakan pendekatan **content-based recommendation**.

### Alur Model

```text
Snapshot katalog TemuBaca
     ↓
Judul + penulis + subjek + label genre + deskripsi
     ↓
TF-IDF (stop word Inggris + Indonesia)
     ↓
Book Vectors
     ↓
Cosine Similarity
     ↓
Recommendation Ranking
```

Label genre situs (misalnya "Romansa", "Sastra Indonesia") ikut masuk ke teks buku, sehingga minat yang dipilih pengguna di website cocok dengan buku yang subjek providernya berbahasa Inggris.

### Analyzer

* `lowercase`, `strip_accents="unicode"`, `sublinear_tf=True`, tanpa stemming.
* Stop word: daftar Inggris scikit-learn + `data/reference/stopwords_id.txt` dari [stopwords-iso/stopwords-id](https://github.com/stopwords-iso/stopwords-id) (MIT, commit di-pin; lihat `stopwords_meta.json`). Entri berstrip seperti "baik-baiknya" dilewati.
* Training gagal jika stop word membuang token dari label genre situs.

### Melatih Ulang

```powershell
# Di repo website: tulis snapshot (tambahkan --cloud untuk production)
bun run ml:snapshot -- --out snapshot.json

# Di repo ini
python scripts/train_tfidf.py --from-file snapshot.json
```

Atau langsung dari endpoint website dengan `TEMUBACA_SNAPSHOT_URL` dan `ML_SNAPSHOT_SECRET`:

```powershell
python scripts/train_tfidf.py
```

Artefak ditulis ke `models/`:

```text
models/tfidf_vectorizer.joblib
models/book_vectors.joblib
models/catalog_books.csv
models/meta.json
```

`models/meta.json` mencatat versi model, waktu snapshot, jumlah buku, ukuran vocabulary, versi scikit-learn, dan genre situs yang belum punya buku. Setelah melatih ulang, jalankan test lalu commit artefaknya.

`MODEL_DIR` (default `models`) menentukan folder model yang dimuat service. Test memakai model dari `tests/fixtures/snapshot_small.json` (data buatan), jadi hasil test tidak bergantung pada isi katalog production.

---

## 9. Integration Notes

* `book_id` adalah UUID buku TemuBaca, jadi website bisa langsung mencocokkan hasil dengan `books.id`.
* Buku baru di website baru ikut direkomendasikan setelah model dilatih ulang.
* Community ID seperti `C001`, `C002`, dan seterusnya masih data demo ML dan perlu diganti dengan komunitas dari snapshot (ML-T05).

---

## 10. Limitations

* Rekomendasi buku berbasis metadata/minat, bukan collaborative filtering.
* Belum menggunakan histori interaksi pengguna sebagai model utama.
* Popularitas hanya dari jumlah bookmark dan listing; selama keduanya nol, urutan cadangan mengikuti `book_id`.
* Tanpa stemming: "romantis" dan "romansa" dianggap kata berbeda.
* Data community saat ini masih berupa data demo.
* Nilai cosine similarity merupakan skor kemiripan, bukan persentase akurasi.

---

## 11. API Summary

| Method | Endpoint                           | Fungsi                  |
| ------ | ---------------------------------- | ----------------------- |
| GET    | `/health`                          | Status service, `model_version`, `book_count` (tanpa token) |
| POST   | `/api/recommendations/books`       | Rekomendasi buku (token) |
| POST   | `/api/recommendations/communities` | Rekomendasi komunitas (token) |

---

## 12. Model Version

Versi model yang sedang dipakai ada di `models/meta.json` (`model_version`, misalnya `temubaca-20261020082721`).

---

## 13. Final Test

Untuk menjalankan seluruh automated test:

```powershell
python -m pytest tests
```

Expected result:

```text
45 passed
```
