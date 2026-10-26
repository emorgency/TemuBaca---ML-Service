# TemuBaca ML Service

Recommendation service untuk fitur rekomendasi buku dan komunitas pada TemuBaca.

## 1. Fitur

ML Service menyediakan tiga fitur utama:

* Rekomendasi buku berdasarkan minat pengguna
* Rekomendasi komunitas berdasarkan minat dan lokasi umum pengguna
* Rute jalan untuk Peta Literasi (mobil dan jalan kaki) di Jakarta dan Tangerang, memakai Dijkstra (bagian 10b)

Metode yang digunakan:

* TF-IDF
* Cosine Similarity
* Rule-based location scoring
* Popularity fallback
* Dijkstra di atas graf jalan OpenStreetMap

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
│   ├── schemas.py
│   └── routing/           # graph.py, dijkstra.py, snap.py, estimate.py, service.py, router.py
│
├── config/
│   ├── coverage.yaml      # wilayah graf (R-01)
│   └── speeds.yaml        # asumsi kecepatan untuk estimasi waktu
│
├── data/
│   ├── reference/
│   ├── graphs/            # graf jalan hasil build (tidak di-commit)
│   └── osm/               # ekstrak OSM untuk build (tidak di-commit)
│
├── scripts/
│   ├── build_region_table.py
│   ├── train_tfidf.py
│   ├── build_graph.py
│   └── bench_route.py
│
├── models/
│   ├── tfidf_vectorizer.joblib
│   ├── book_vectors.joblib
│   ├── catalog_books.csv
│   ├── communities.csv
│   └── meta.json
│
├── tests/
│   ├── test_recommender.py
│   ├── test_community.py
│   ├── test_regressions.py
│   ├── test_training.py
│   ├── test_security.py
│   ├── test_dijkstra.py
│   ├── test_routing_graph.py
│   ├── test_routing_service.py
│   ├── test_routing_api.py
│   ├── test_contract.py
│   ├── test_recommendation_log.py
│   ├── conftest.py
│   ├── contract/          # pasangan request/respons yang juga dipakai website
│   └── fixtures/          # snapshot_small.json, small_graph/
│
├── docs/
│   └── BACKEND_PETA_RUTE.md
│
├── pyproject.toml
├── uv.lock
├── .fastapicloudignore
├── requirements.txt
├── requirements-dev.txt
├── requirements-build.txt # osmnx + osmium, hanya untuk build graf
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
  "user_interests": ["Puisi", "Sejarah"],
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
      "community_id": "c0000000-0000-4000-8000-000000000003",
      "name": "Komunitas Sejarah Tangsel",
      "region_code": "36.74",
      "region_name": "Kota Tangerang Selatan",
      "interest_score": 0.5588,
      "location_score": 1.0,
      "score": 0.6912,
      "reason": "Sesuai dengan minat: sejarah dan berada di Kota Tangerang Selatan"
    }
  ],
  "unmatched_interests": [],
  "notice": null
}
```

* Contoh di atas adalah item pertama untuk request tersebut dengan `top_n: 1`, memakai model dan komunitas sintetis dari `tests/fixtures/snapshot_small.json`.
* `community_id` adalah UUID komunitas TemuBaca (`communities.id`). Kandidatnya adalah komunitas `VERIFIED` dari snapshot yang sudah mengisi tag minat (1–5 label genre situs) dan kab/kota. Komunitas yang belum mengisi keduanya dilewati sampai diisi.
* Skor minat hanya memakai tag minat komunitas, bukan nama atau deskripsinya.
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

### Kontrak dengan website (ML-T10)

`tests/contract/*.json` membekukan request yang dikirim website dan respons persis yang diberikan service ini untuk fixture test (buku, komunitas dengan dan tanpa kecocokan, rute, dan rute di luar cakupan). `tests/test_contract.py` gagal bila respons berubah. Website menyimpan salinan identik di `tests/fixtures/ml-contract/` dan mengujinya di `tests/unit/ml-contract.test.ts` (body yang dikirim harus sama, respons harus lolos validasi). Setelah perubahan kontrak yang disengaja:

```bash
UPDATE_CONTRACT=1 python -m pytest tests/test_contract.py
cp tests/contract/*.json ../temubaca/tests/fixtures/ml-contract/
```

Jumlah total test ada di bagian 13.

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

Training juga menulis `models/communities.csv` (`community_id,name,region_code,interests`, tag dipisah `|`). Snapshot gagal dilatih jika tag komunitas bukan label genre situs atau kab/kota-nya tidak ada di `data/reference/wilayah_kabkota.csv`. Vektor komunitas dibuat dari tag tersebut saat service mulai.

`models/meta.json` mencatat versi model, waktu snapshot, jumlah buku, jumlah komunitas, ukuran vocabulary, versi scikit-learn, dan genre situs yang belum punya buku. Setelah melatih ulang, jalankan test lalu commit artefaknya.

`MODEL_DIR` (default `models`) menentukan folder model yang dimuat service. Test memakai model dari `tests/fixtures/snapshot_small.json` (data buatan), jadi hasil test tidak bergantung pada isi katalog production.

---

## 9. Integration Notes

* `book_id` adalah UUID buku TemuBaca, jadi website bisa langsung mencocokkan hasil dengan `books.id`.
* Buku baru di website baru ikut direkomendasikan setelah model dilatih ulang.
* `community_id` adalah UUID komunitas TemuBaca, jadi website bisa langsung mencocokkan hasil dengan `communities.id`.
* Komunitas yang baru diverifikasi, atau yang baru mengisi tag dan wilayah, baru ikut direkomendasikan setelah model dilatih ulang.
* Model `temubaca-20261020082721` dilatih dari snapshot sebelum website punya tag dan wilayah komunitas, jadi `communities.csv`-nya masih kosong dan rekomendasi komunitas selalu `NO_MATCH` sampai model dilatih ulang.
* Setiap request rekomendasi menulis satu baris log `app.recommendations` berisi jumlah saja (ML-T08), misalnya `recommend kind=books model=<versi> interests=2 unmatched=1 results=3 sources=interest:1,popularity:2 notice=- latency_ms=2.2`. Minat, kode wilayah, dan id hasil tidak pernah masuk log; `tests/test_recommendation_log.py` menjaganya. Log akses uvicorn tetap mencatat path dan status.

---

## 10. Limitations

* Rekomendasi buku berbasis metadata/minat, bukan collaborative filtering.
* Belum menggunakan histori interaksi pengguna sebagai model utama.
* Popularitas hanya dari jumlah bookmark dan listing; selama keduanya nol, urutan cadangan mengikuti `book_id`.
* Tanpa stemming: "romantis" dan "romansa" dianggap kata berbeda.
* Nilai cosine similarity merupakan skor kemiripan, bukan persentase akurasi.

---

## 10a. Deploy ke FastAPI Cloud

Konfigurasi deploy ada di `pyproject.toml`:

* `requires-python = "==3.14.*"` dan dependensi runtime dengan versi tetap, dikunci di `uv.lock`. scikit-learn harus tetap 1.9.1 selama model dibuat dengan versi itu.
* `[tool.fastapi] entrypoint = "app.main:app"`, sehingga `fastapi run` dan `fastapi deploy` tidak butuh argumen path.
* `.fastapicloudignore` mengecualikan `tests/`, `docs/`, `scripts/`, dan `requirements-dev.txt`. `models/` dan `data/reference/` ikut diunggah.

`requirements.txt` tetap dipakai untuk instalasi pip lokal. Bila menambah atau menaikkan dependensi, ubah `pyproject.toml`, jalankan `uv lock`, dan samakan versinya di `requirements.txt`.

Langkah deploy (dijalankan pemilik akun):

```powershell
fastapi login
fastapi deploy
fastapi cloud env set INTERNAL_TOKEN --secret
fastapi deploy
```

`fastapi deploy` mengunggah setiap file yang tidak dikecualikan `.gitignore` atau `.fastapicloudignore`, termasuk file lain yang kebetulan ada di folder repo tetapi tidak dilacak Git. Deploy 26 Okt 2026 (`0bf74c4`) karena itu dijalankan dari salinan bersih, berisi hasil `git archive HEAD` ditambah `data/graphs/` (44 file, 139,6 MB):

```bash
git archive HEAD | tar -x -C /tmp/ml-deploy && cp -r data/graphs /tmp/ml-deploy/data/
cd /tmp/ml-deploy && git init -q && FASTAPI_CLOUD_APP_ID=<id app> fastapi deploy --large-file-threshold 200
```

Setelah deploy, cek:

* `GET /health` membalas `200` dengan `model_version` yang sama seperti `models/meta.json`.
* `POST /api/recommendations/books` tanpa token membalas `401`, dan dengan token membalas `200`.

Lalu isi `RECOMMENDATION_API_URL` (URL aplikasi) dan `RECOMMENDATION_API_KEY` (nilai `INTERNAL_TOKEN`) di environment Vercel website.

**Cold start.** Paket Hobby memakai scale-to-zero, jadi request pertama setelah idle menunggu service start. Pengukuran lokal (Windows, 20 Okt 2026): `import app.main` 9–10 detik pada venv yang hangat, terbesar dari `sklearn.metrics.pairwise` (±5 detik) dan `pandas` (±3 detik); request setelah siap 30–108 ms. Angka di FastAPI Cloud belum diukur. Selama start lebih lama dari batas waktu klien website (3 detik), request itu memakai rekomendasi baseline.

---

## 10b. Routing (Peta Literasi)

Rute jalan dari titik asal ke tempat di Peta Literasi, dengan Dijkstra buatan sendiri (`app/routing/dijkstra.py`, `heapq`). Rancangan lengkap ada di `docs/BACKEND_PETA_RUTE.md`. Service hanya menerima dua koordinat dan moda; `place_id`, cek `is_routable`, dan tautan Google Maps diurus website (Lampiran A).

### Cakupan dan graf

* Wilayah (R-01, 25 Okt 2026): DKI Jakarta daratan (tanpa Kepulauan Seribu), Kota Tangerang, Kabupaten Tangerang, dan Kota Tangerang Selatan (`config/coverage.yaml`). Titik di luar wilayah ini mendapat `OUT_OF_COVERAGE`.
* Moda: `drive` (bobot waktu tempuh, menghormati jalan satu arah) dan `walk` (bobot jarak, dua arah).
* Data: OpenStreetMap, © OpenStreetMap contributors. Atribusi ini tampil di `/health` dan wajib tampil di peta website.
* Estimasi waktu memakai asumsi kecepatan di `config/speeds.yaml`, bukan data lalu lintas. Setiap rute membawa peringatan `ESTIMATE_NO_TRAFFIC`.

### Membangun graf

Graf dibangun offline dan tidak di-commit. Server Overpass publik tidak andal untuk area sebesar ini (25 Okt 2026: 502, 504, lalu koneksi ditolak), dan wiki OSM menyarankan ekstrak untuk area besar. Bangun dari ekstrak Geofabrik:

```powershell
pip install -r requirements-build.txt
Invoke-WebRequest https://download.geofabrik.de/asia/indonesia/java-latest.osm.pbf -OutFile data/osm/java-latest.osm.pbf
python scripts/build_graph.py --area jakarta-tangerang --mode drive --pbf data/osm/java-latest.osm.pbf
python scripts/build_graph.py --area jakarta-tangerang --mode walk --pbf data/osm/java-latest.osm.pbf
```

Cocokkan file ekstrak dengan `java-latest.osm.pbf.md5` dari Geofabrik. Tanpa `--pbf`, skrip memakai Overpass API.

Hasil build 25 Okt 2026 (ekstrak 24 Okt 2026, Linux, RAM 7,5 GB):

| Graf | Node | Edge | File | Puncak memori build | Waktu build |
| --- | --- | --- | --- | --- | --- |
| `jakarta-tangerang-drive-2026-10-25` | 238.773 | 564.039 | 53 MB | 2,9 GB | 4 menit |
| `jakarta-tangerang-walk-2026-10-25` | 386.573 | 993.130 | 86 MB | 4,2 GB | 5 menit |

Build `walk` butuh sekitar 4,3 GB RAM bebas.

Format graf (format 2, `meta.json` `"format": 2`): `graph.npz` berisi adjacency CSR, panjang, waktu tempuh, dan geometri semua edge sebagai array datar (`edge_coords`, `edge_coord_offsets`); `edges.json` hanya berisi nama jalan. Bentuk ini dipilih karena FastAPI Cloud membatasi memori 512 MB: format lama (geometri sebagai objek JSON per edge) membuat service + graf `drive` saja 623 MB. Graf format lama ditolak saat dimuat dan harus dibangun ulang.

### Menjalankan

Isi `ROUTING_GRAPHS` di `.env` dengan nama folder graf di `data/graphs/`, lalu jalankan service seperti biasa:

```text
ROUTING_GRAPHS=jakarta-tangerang-drive-2026-10-25,jakarta-tangerang-walk-2026-10-25
```

Graf dimuat saat startup (±1 detik untuk keduanya). Memori service terukur (RSS, 26 Okt 2026, setelah Dijkstra membaca array graf lewat `memoryview` tanpa salinan kedua):

| `ROUTING_GRAPHS` | Memori |
| --- | --- |
| kosong (rekomendasi saja) | 183 MB |
| `drive` | 258 MB |
| `drive` + `walk` | 359 MB |

Graf yang gagal dimuat dicatat di log dan dilewati: service tetap jalan, rekomendasi tetap berfungsi, dan moda itu membalas `503 ROUTING_UNAVAILABLE`.

### Request dan respons

```powershell
$body = '{"origin":{"lat":-6.1760,"lng":106.8225},"destination":{"lat":-6.2443,"lng":106.8007},"mode":"drive"}'
Invoke-RestMethod http://127.0.0.1:8000/api/routing/route -Method Post -ContentType 'application/json' `
  -Headers @{ 'X-Internal-Token' = $env:INTERNAL_TOKEN } -Body $body
```

Contoh respons (Jl. Medan Merdeka Barat ke Blok M, `coordinates` dipersingkat dari 356 titik):

```json
{
  "mode": "drive",
  "distance_m": 9040,
  "duration_s_estimate": 1140,
  "geometry": { "type": "LineString", "coordinates": [[106.822759, -6.174613], "...", [106.800827, -6.243235]] },
  "via_streets": ["Jalan Mohammad Husni Thamrin", "Jalan Jenderal Sudirman", "Jalan Pattimura"],
  "snap": { "origin_offset_m": 156, "destination_offset_m": 119 },
  "warnings": ["ESTIMATE_NO_TRAFFIC"],
  "algorithm": "dijkstra",
  "graph_version": "jakarta-tangerang-drive-2026-10-25"
}
```

Error memakai `{"error": {"code", "message", "point"?}}`: `INVALID_PARAMS` (422), `OUT_OF_COVERAGE` dan `SNAP_TOO_FAR` (422, dengan `point`), `NO_PATH` (404), `UNAUTHORIZED` (401), `ROUTING_UNAVAILABLE` (503), `INTERNAL` (500). Body lebih dari 2 KB ditolak `413`. Snap memilih simpang terdekat (maks. `SNAP_MAX_M`, 300 m), sehingga di ruas jalan panjang jarak snap bisa lebih dari 100 m.

Koordinat tidak pernah masuk log. Log rute hanya berisi moda, versi graf, status, latensi, jumlah node yang diproses, dan cache hit.

### Benchmark

`python scripts/bench_route.py --graph <versi> --n 500` merutekan pasangan node acak (seed 20261025) tiga kali: lewat `memoryview` atas array numpy (dipakai service), list Python, dan akses elemen numpy langsung. Hasil 26 Okt 2026, Linux, Python 3.14, graf format 2. Mesin sedang menjalankan aplikasi lain, jadi bandingkan baris dalam satu graf, bukan angka absolutnya:

| Graf | Iterasi | p50 | p95 | Maks | Node diproses | Memori graf |
| --- | --- | --- | --- | --- | --- | --- |
| `drive` | `memoryview` (service) | 221 ms | 409 ms | 1.331 ms | 130.038 | +76 MB |
| `drive` | list | 261 ms | 572 ms | 897 ms | 130.038 | |
| `drive` | numpy | 348 ms | 650 ms | 686 ms | 130.038 | |
| `walk` | `memoryview` (service) | 360 ms | 679 ms | 4.394 ms | 213.910 | +118 MB |
| `walk` | list | 466 ms | 897 ms | 1.241 ms | 213.910 | |
| `walk` | numpy | 581 ms | 1.105 ms | 1.227 ms | 213.910 | |

`memoryview` tidak menyalin array graf dan lebih cepat daripada list maupun akses elemen numpy. Dibanding versi 25 Okt (salinan `array.array`, p50 318 ms `drive` / 531 ms `walk`), loop Dijkstra kini mengikat `heappop`, `heappush`, dan `dict.get` ke nama lokal. Nilai maks tunggal dipengaruhi beban mesin lain. Pasangan acak tersebar di seluruh Jakarta–Tangerang, jadi lebih panjang daripada rute nyata ke tempat terdekat: rute dalam kota terukur 3–176 ms. Target latensi belum disepakati.

### Deploy graf

`data/graphs/` tidak ada di Git, tetapi ikut terunggah saat `fastapi deploy` lewat `!data/graphs/` di `.fastapicloudignore` (±133 MB untuk kedua graf; `data/osm/` dan `cache/` tetap tidak terunggah). Setelah deploy, set `ROUTING_GRAPHS` di environment cloud dengan nama folder graf, lalu cek `/health` menampilkan versi kedua graf. Batas ukuran upload FastAPI Cloud belum tercantum di halaman harganya.

### Belum diputuskan

* Target latensi.

---

## 11. API Summary

| Method | Endpoint                           | Fungsi                  |
| ------ | ---------------------------------- | ----------------------- |
| GET    | `/health`                          | Status service, `model_version`, `book_count`, graf rute yang dimuat (tanpa token) |
| POST   | `/api/recommendations/books`       | Rekomendasi buku (token) |
| POST   | `/api/recommendations/communities` | Rekomendasi komunitas (token) |
| POST   | `/api/routing/route`               | Rute Dijkstra antar dua titik (token) |

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
110 passed
```
