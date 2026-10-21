# BACKEND — Peta Literasi & Rute (Dijkstra)

**Versi:** 0.3 • **Status:** Draft untuk dikerjakan dengan Claude Code • **Repo target:** `emorgency/TemuBaca---ML-Service` • **Bahasa kode & komentar:** Inggris; teks yang tampil ke pengguna: Indonesia

**Perubahan dari v0.2:** ditambah **Fase 0 — Fondasi & perbaikan kode lama** (bagian 13), berisi perbaikan bug rekomendasi yang ditemukan saat review kode. Fase lama 1 (persiapan repo) digabung ke Fase 0, sehingga fase routing kini bernomor 1–4.

**Perubahan dari v0.1:** routing tidak lagi dibuat sebagai layanan baru. Routing ditambahkan sebagai modul di FastAPI ML Service yang sudah ada, mengikuti struktur dan pola repo tersebut. Places API dipindah ke lampiran karena berada di backend utama, bukan di repo ini.

Desain UI acuan: Figma `TemuBaca` → section **Pembaca** → frame `Peta Literasi v2 — Default (Desktop)` dan `Peta Literasi v2 — State: Rute (Desktop)`.

Dokumen terkait: `PRD.md` (FR-03), `SECURITY.md`, `ARCHITECTURE.md`, `DECISIONS.md` (DEC-01, DEC-07, DEC-08), `TASKS.md` (TB-026, TB-027).

---

## 0. Aturan untuk Claude Code

1. **Kerjakan per fase** (bagian 9), mulai dari Fase 0. Setelah setiap fase, jalankan `python -m pytest tests` dan laporkan hasilnya apa adanya, termasuk yang gagal.
2. **Perilaku `/api/recommendations/*` hanya boleh berubah sesuai bagian 13 (Fase 0).** Test lama yang memeriksa perilaku yang memang diubah di Fase 0 boleh disesuaikan, tapi setiap perubahan test harus disebutkan beserta alasannya. Setelah Fase 0, seluruh test rekomendasi wajib tetap lulus di fase-fase berikutnya.
3. **Jangan mengasumsikan keputusan berstatus `TBD`** (bagian 2). Jika sebuah fase bergantung padanya, berhenti dan tanyakan dalam bentuk pilihan ganda.
4. **Dijkstra wajib diimplementasikan sendiri** dengan `heapq`. `networkx` hanya boleh dipakai di test (sebagai pembanding) dan di skrip build graf, tidak di jalur runtime.
5. **Jangan memanggil API pihak ketiga per request** (Overpass, Nominatim, Google). Data jalan diunduh offline lewat skrip build.
6. **Service harus tetap menyala walau file graf belum ada.** Rekomendasi tetap berfungsi; endpoint rute mengembalikan `503 ROUTING_UNAVAILABLE`.
7. **Jangan menyimpan atau me-log koordinat pengguna** (bagian 7).
8. **Jangan commit file graf** (`data/graphs/`) atau `.env`.
9. Jangan menambah dependensi runtime di luar bagian 8 tanpa bertanya.

---

## 1. Kondisi repo saat ini

Diperiksa pada commit `deb8fbb` (5 Okt 2026).

| Aspek | Temuan | Dampak untuk routing |
|---|---|---|
| Framework | FastAPI 0.142, Pydantic v2, satu app di `app/main.py` | Routing ditambahkan sebagai `APIRouter`, bukan app baru. |
| Struktur | Datar: `app/`, `models/`, `data/`, `tests/`, `notebooks/` | Modul baru di `app/routing/`, skrip di `scripts/`. |
| Endpoint | `GET /health`, `POST /api/recommendations/books`, `POST /api/recommendations/communities` | Ikuti prefix `/api/...` dan metode POST. Perluas `/health`, jangan buat `/healthz`. |
| Pemuatan model | Model dan CSV dimuat saat modul di-import (module-level) | Graf **jangan** dimuat di level modul. Muat lewat `lifespan` supaya kegagalan graf tidak mematikan service. |
| Konfigurasi | Belum ada env/config; path dihitung dari `BASE_DIR` | Tambahkan `app/config.py` memakai `pydantic-settings` (sudah ada di requirements). |
| Auth | Semua endpoint terbuka | Lihat R-07. |
| Test | 10 test, **10 lulus** (dijalankan ulang pada 17 Okt 2026, Python 3.13). Test hanya memeriksa bentuk respons, sehingga tidak menangkap bug di bagian 13. | Baseline dicatat sebelum Fase 0; sebagian test disesuaikan di Fase 0. |
| `requirements.txt` | Hasil `pip freeze` (63 paket), **ber-encoding UTF-16 LE**, tanpa `pytest`. pip masih bisa membaca, tapi diff Git dan alat edit teks bisa merusaknya. | Konversi ke UTF-8 di Fase 0, sebagai commit terpisah tanpa mengubah isi. |
| Data di Git | ~52 MB CSV dan model ikut di-commit | File graf bisa jauh lebih besar; wajib di `.gitignore`. |
| Lingkungan dev | README memakai PowerShell (Windows) | Perintah di dokumen ini ditulis untuk PowerShell. Kemampuan instal `osmnx` di Windows perlu diverifikasi (lihat 6.1). |

Ketidaksesuaian di luar scope dokumen ini, tapi perlu dicatat tim:
- `API_SPEC.md` menulis `GET /api/recommendations/{books,communities}`, sedangkan repo memakai `POST`.
- `book_id` Goodbooks dan `community_id` demo (`C001`…) belum dipetakan ke UUID TemuBaca. README sudah mencatat ini. **Selesai:** `book_id` di ML-T04, `community_id` di ML-T05 (komunitas dari snapshot, artefak `models/communities.csv`).

---

## 2. Status keputusan

### Sudah diputuskan

| Keputusan | Nilai |
|---|---|
| Kategori di peta | 4: Perpustakaan, Komunitas, Kegiatan, Titik Temu |
| Peta & data jalan | OpenStreetMap |
| Algoritma rute | Dijkstra buatan sendiri |
| Navigasi nyata | Deep link "Buka di Google Maps" (tanpa API key) |
| Komunitas tanpa venue tetap | Area, **tidak bisa dirutekan** |
| Tujuan rute | Selalu `place_id` yang di-resolve oleh backend utama, bukan koordinat bebas dari browser |

### Keputusan yang diambil dokumen ini (bisa dibatalkan tim)

| ID | Keputusan | Alasan | Alternatif |
|---|---|---|---|
| R-04 | Routing ditempatkan **di repo ML Service**, modul `app/routing/` | Satu layanan Python untuk di-deploy; sesuai prinsip `TECH_STACK.md` untuk tidak menambah layanan hanya demi arsitektur. | Repo/service terpisah. Lebih bersih secara domain, tapi menambah deployment. Pemisahan modul di sini memudahkan pindah nanti. |
| R-08 | Format graf: `graph.npz` + `edges.json` + `meta.json`, **bukan pickle** | Pickle bisa mengeksekusi kode saat dimuat, dan formatnya rapuh antar versi Python. | Pickle (lebih cepat dibuat, tapi tidak disarankan). |
| R-09 | `osmnx` hanya dependensi build, bukan runtime | Menghindari geopandas/shapely di image runtime. Runtime cukup memakai numpy dan scipy, yang sudah terpasang. | |

### Keputusan pemilik produk untuk Fase 0 (17 Okt 2026)

| ID | Keputusan |
|---|---|
| R-10 | Rekomendasi komunitas tanpa minat **dan** tanpa lokasi mengembalikan **daftar kosong** dengan `notice`, supaya UI meminta pengguna mengisi minat. Tidak ada fallback komunitas. |
| R-11 | Pencocokan lokasi komunitas memakai **kode wilayah Kemendagri** tingkat kabupaten/kota, bukan nama kota/provinsi. Ini perubahan kontrak API (bagian 13.3). |

### Belum diputuskan

| ID | Pertanyaan | Default | Catatan |
|---|---|---|---|
| R-01 | Cakupan wilayah graf | **TBD — wajib ditanyakan sebelum Fase 2** | (a) satu kota, mis. Jakarta Pusat atau Tangsel; (b) Jabodetabek. Pilihan (b) jauh lebih berat untuk memori, waktu build, dan latensi. |
| R-02 | Moda | `drive` dan `walk` | Transportasi umum di luar scope. |
| R-06 | Kecepatan untuk estimasi waktu | Tabel di 6.4 | Asumsi kasar, bukan data lalu lintas. |
| R-07 | Proteksi endpoint | **TBD — tanyakan di Fase 3** | (a) token internal hanya untuk `/api/routing/*`; (b) token internal untuk **semua** `/api/*`, termasuk rekomendasi (memengaruhi pemanggil yang sudah ada); (c) tanpa token di dev, wajib di staging/produksi. |

---

## 3. Arsitektur

```text
Browser (Peta Literasi)
  └─ Backend utama (repo lain; stack TBD — DEC-01)
        ├─ GET /api/places ............. DB tempat publik (lampiran A)
        └─ GET /api/route .............. resolve place_id → koordinat, cek is_routable, rate limit
                │  POST + X-Internal-Token
                ▼
        TemuBaca ML Service (repo ini, FastAPI)
          ├─ /api/recommendations/books        (sudah ada)
          ├─ /api/recommendations/communities  (sudah ada)
          ├─ POST /api/routing/route           (baru)
          └─ GET  /health                      (diperluas dengan status routing)
                └─ graf OSM in-memory, dimuat saat startup dari data/graphs/

Offline: scripts/build_graph.py → unduh OSM per area & moda → bersihkan → simpan graf berversi
```

ML Service **tidak** mengetahui `place_id`, tidak mengakses database, dan tidak dipanggil langsung oleh browser. Service ini hanya menerima dua koordinat dan moda, lalu mengembalikan rute.

---

## 4. Struktur file yang ditambahkan

Struktur yang ada tidak diubah. File baru:

```text
app/
  config.py                    # Settings (pydantic-settings), dibaca dari env
  model_store.py               # Fase 0: memuat TF-IDF sekali, dipakai bersama
  text.py                      # Fase 0: normalisasi minat & pencocokan token
  region.py                    # Fase 0: tabel & validasi kode wilayah
  routing/
    __init__.py
    router.py                  # APIRouter: POST /api/routing/route
    schemas.py                 # Pydantic model khusus routing
    graph.py                   # RoadGraph: load npz/json, adjacency CSR, KD-tree
    dijkstra.py                # dijkstra(), NoPathError
    snap.py                    # nearest node + cek cakupan
    estimate.py                # tabel kecepatan, durasi
    service.py                 # orkestrasi: snap → dijkstra → geometri → ringkasan
    errors.py                  # RoutingError + kode error (bagian 5.3)
config/
  coverage.yaml                # area & bbox (diisi setelah R-01)
  speeds.yaml                  # tabel 6.4
scripts/
  build_graph.py
  bench_route.py
data/graphs/                   # .gitignore
data/reference/
  wilayah_kabkota.csv          # Fase 0: kode wilayah kab/kota (bagian 13.3)
  wilayah_meta.json            # sumber, versi, tanggal unduh
models/meta.json               # Fase 0: versi scikit-learn & tanggal pembuatan model
tests/
  test_regressions.py          # Fase 0: satu test per bug di bagian 13
  fixtures/small_graph/        # graph.npz, edges.json, meta.json buatan tangan
  test_dijkstra.py
  test_routing_service.py
  test_routing_api.py
requirements.txt               # runtime (UTF-8)
requirements-dev.txt           # pytest, networkx
requirements-build.txt         # osmnx
.env.example
```

Perubahan pada file yang sudah ada:
- Fase 0: `app/recommender.py`, `app/community.py`, `app/schemas.py`, `tests/test_*.py`, `requirements.txt`, `README.md` sesuai bagian 13.
- `app/main.py`: tambahkan `lifespan` untuk memuat graf, `app.include_router(routing_router)`, dan field `routing` di `/health`.
- `.gitignore`: tambahkan `data/graphs/`.
- `README.md`: tambahkan bagian Routing (Fase 4).

---

## 5. Kontrak endpoint routing (repo ini)

### 5.1 `POST /api/routing/route`

Request:

```json
{
  "origin": { "lat": -6.2001, "lng": 106.8302 },
  "destination": { "lat": -6.1904, "lng": 106.8392 },
  "mode": "drive"
}
```

Validasi (Pydantic):
- `lat` dalam [-90, 90] dan `lng` dalam [-180, 180].
- `mode` ∈ {`drive`, `walk`}, default `drive`.
- Field lain ditolak (`extra="forbid"`).

### 5.2 Respons 200

```json
{
  "mode": "drive",
  "distance_m": 2300,
  "duration_s_estimate": 540,
  "geometry": { "type": "LineString", "coordinates": [[106.8302, -6.2001], [106.8392, -6.1904]] },
  "via_streets": ["Jl. Teuku Umar", "Jl. Cikini Raya"],
  "snap": { "origin_offset_m": 35, "destination_offset_m": 12 },
  "warnings": ["ESTIMATE_NO_TRAFFIC"],
  "algorithm": "dijkstra",
  "graph_version": "jakpus-drive-2026-10-17"
}
```

- `geometry` dalam urutan GeoJSON, yaitu `[lng, lat]`, dan dibangun dari geometri edge, bukan sekadar titik node.
- `distance_m` dibulatkan ke 10 m; `duration_s_estimate` dibulatkan ke 30 detik.
- `via_streets` berisi maksimal 3 nama jalan dengan porsi jarak terbesar, urut sesuai perjalanan. **Bukan** instruksi belok-per-belok.
- `external_url` (deep link Google Maps) **tidak** dibuat di sini, melainkan di backend utama, karena backend utama yang memegang data tempat.

### 5.3 Error

Format seragam, tanpa stack trace:

```json
{ "error": { "code": "SNAP_TOO_FAR", "message": "Titik terlalu jauh dari jalan yang dipetakan." } }
```

| Status | Kode | Kapan |
|---|---|---|
| 422 | `INVALID_PARAMS` | Validasi gagal (ubah handler validasi default FastAPI ke format di atas **hanya untuk** `/api/routing/*`) |
| 422 | `OUT_OF_COVERAGE` | Asal atau tujuan di luar bbox graf; sertakan `"point": "origin" \| "destination"` |
| 422 | `SNAP_TOO_FAR` | Node terdekat lebih jauh dari `SNAP_MAX_M`; sertakan `point` |
| 404 | `NO_PATH` | Tidak ada jalur di graf |
| 401 | `UNAUTHORIZED` | Token internal salah atau tidak ada (sesuai R-07) |
| 503 | `ROUTING_UNAVAILABLE` | Graf untuk moda itu belum dimuat |
| 500 | `INTERNAL` | Lainnya |

---

## 6. Implementasi routing

### 6.1 Build graf (offline): `scripts/build_graph.py`

```powershell
pip install -r requirements-build.txt
python scripts/build_graph.py --area jakpus --mode drive
```

1. Baca area dari `config/coverage.yaml` (nama, bbox `[min_lng, min_lat, max_lng, max_lat]`, daftar moda). **Isi bbox setelah R-01 diputuskan.**
2. Unduh jaringan jalan dengan osmnx: `network_type="drive"` atau `"walk"`, dibatasi bbox.
3. Bersihkan graf:
   - `drive`: ambil *largest strongly connected component* dan hormati `oneway`.
   - `walk`: ambil *largest weakly connected component* dan buat edge dua arah.
4. Hitung `travel_time_s` per edge memakai `config/speeds.yaml`.
5. Ekspor ke `data/graphs/{area}-{mode}-{YYYY-MM-DD}/`:
   - `graph.npz`: `node_ids`, `lat`, `lng`, `indptr`, `indices`, `length_m`, `travel_time_s`, `edge_ref` (adjacency CSR).
   - `edges.json`: per `edge_ref` berisi `name`, `highway`, dan `coords` (polyline `[lng, lat]`).
   - `meta.json`: `graph_version`, `area`, `mode`, `bbox`, jumlah node dan edge, tanggal unduh, versi osmnx, serta atribusi `"© OpenStreetMap contributors"`.
6. Cetak ringkasan: jumlah node, jumlah edge, ukuran file, dan waktu build.

Catatan verifikasi:
- Unduhan memakai server Overpass publik dan harus mengikuti kebijakan pemakaiannya, terutama untuk area besar. **This needs verification** sebelum build Jabodetabek.
- Instalasi `osmnx` di Windows belum diuji. Jika gagal, jalankan build di WSL atau Google Colab, lalu salin folder hasilnya ke `data/graphs/`. Runtime tidak membutuhkan osmnx.

### 6.2 `RoadGraph` (runtime)

```python
@dataclass(frozen=True)
class RoadGraph:
    version: str
    mode: str
    bbox: tuple[float, float, float, float]
    lat: np.ndarray          # index node internal 0..N-1
    lng: np.ndarray
    indptr: np.ndarray       # CSR
    indices: np.ndarray
    length_m: np.ndarray
    travel_time_s: np.ndarray
    edge_ref: np.ndarray
    edges: list[EdgeInfo]
    kdtree: scipy.spatial.cKDTree   # di atas koordinat proyeksi lokal (meter)
```

- `load_graph(path) -> RoadGraph`: validasi `meta.json`, ukuran array yang konsisten, dan nilai tidak negatif.
- Proyeksi untuk KD-tree memakai equirectangular lokal: `x = lng·cos(lat0)·111320`, `y = lat·110540`, dengan `lat0` titik tengah bbox. Akurasi ini cukup untuk skala kota.
- Graf yang dipilih dikontrol oleh env `ROUTING_GRAPHS` (mis. `jakpus-drive-2026-10-17,jakpus-walk-2026-10-17`), bukan otomatis "yang terbaru", supaya deployment dapat direproduksi.

### 6.3 Dijkstra: `app/routing/dijkstra.py`

```python
class NoPathError(Exception): ...

def dijkstra(
    indptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    source: int,
    target: int,
) -> tuple[list[int], list[int], float]:
    """Return (node_path, edge_positions, total_cost)."""
```

Persyaratan:
- Memakai `heapq` dengan *lazy deletion*: lewati entri heap yang biayanya lebih besar dari `dist[node]`.
- Berhenti lebih awal begitu `target` di-pop.
- `source == target` mengembalikan `([source], [], 0.0)`.
- Tidak ada jalur: raise `NoPathError`.
- Fungsi murni, tanpa state global dan tanpa I/O.
- Bobot: `travel_time_s` untuk `drive`, `length_m` untuk `walk`.
- Untuk iterasi di loop panas, konversi array numpy ke `list` Python sekali saat graf dimuat, bukan per request. Catat hasil keduanya di benchmark.
- A* dan bidirectional **tidak** dikerjakan sekarang. Usulkan hanya jika benchmark Fase 4 menunjukkan latensi tidak memadai.

### 6.4 Estimasi waktu (`config/speeds.yaml`)

| `highway` | km/jam (drive) |
|---|---|
| motorway, trunk | 40 |
| primary | 30 |
| secondary | 25 |
| tertiary | 20 |
| residential, unclassified | 15 |
| service, living_street, lainnya | 10 |

Moda `walk` memakai 4,5 km/jam untuk semua jalan. Jika `highway` berupa list (format osmnx), ambil kelas dengan kecepatan tertinggi.

Angka ini **asumsi kasar untuk kota padat**. Respons selalu menyertakan warning `ESTIMATE_NO_TRAFFIC`.

### 6.5 Snapping

- Cek dulu apakah titik berada di dalam bbox graf. Jika tidak → `OUT_OF_COVERAGE`.
- Cari node terdekat lewat KD-tree. Jika jaraknya lebih dari `SNAP_MAX_M` (default 300) → `SNAP_TOO_FAR`.

### 6.6 Integrasi ke `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.graphs = load_configured_graphs(settings)  # dict[mode, RoadGraph]; mode gagal dimuat tidak ada di dict
    yield

app = FastAPI(..., lifespan=lifespan)
app.include_router(routing_router)
```

- Jika sebuah graf gagal dimuat, log nama graf dan alasannya (tanpa data pengguna), lalu lanjutkan startup.
- `/health` tetap mengembalikan `"status": "ok"` dan `"service": "temubaca-ml"` supaya kompatibel. Tambahkan:

```json
"routing": { "drive": "jakpus-drive-2026-10-17", "walk": null, "attribution": "© OpenStreetMap contributors" }
```

### 6.7 Cache

`functools.lru_cache` atau dict LRU berukuran `ROUTE_CACHE_SIZE` (default 1000), dengan kunci `(graph_version, source_node, target_node)`. Kunci memakai node hasil snap, bukan koordinat mentah.

---

## 7. Privasi & keamanan

- Koordinat asal **tidak** disimpan dan tidak masuk log, termasuk log akses Uvicorn untuk body request (body memang tidak di-log secara default; jangan tambahkan middleware yang me-log body).
- Log routing hanya mencatat `mode`, `graph_version`, status, latensi, jumlah node yang diproses, dan `cache_hit`.
- Token internal (sesuai R-07) dibaca dari env `INTERNAL_TOKEN` dan dibandingkan dengan `hmac.compare_digest`.
- Batas ukuran request: tolak body lebih dari 2 KB di `/api/routing/*`.
- Tidak ada CORS untuk `/api/routing/*`; endpoint ini hanya dipanggil server-ke-server.
- File graf hanya dimuat dari `GRAPH_DIR`. Jangan pernah menerima path graf dari request.

---

## 8. Dependensi

| File | Isi | Catatan |
|---|---|---|
| `requirements.txt` | Isi yang ada, dikonversi ke UTF-8 | Runtime routing hanya butuh `numpy`, `scipy`, `PyYAML`, dan `pydantic-settings`, yang **sudah ada**. Tidak perlu paket baru. |
| `requirements-dev.txt` | `pytest`, `networkx` | `networkx` hanya untuk pembanding di test. |
| `requirements-build.txt` | `osmnx` (+ `-r requirements.txt`) | Hanya untuk `scripts/build_graph.py`. Pin versi setelah instalasi berhasil. |

`.env.example`:

```text
APP_ENV=development
GRAPH_DIR=data/graphs
ROUTING_GRAPHS=
SNAP_MAX_M=300
ROUTE_CACHE_SIZE=1000
INTERNAL_TOKEN=
```

---

## 9. Fase kerja

| Fase | Pekerjaan | Selesai jika |
|---|---|---|
| **0. Fondasi & perbaikan kode lama** | Seluruh bagian 13, dikerjakan berurutan 0a → 0c. | Kriteria di 13.6 terpenuhi |
| **1. Dijkstra & graf** | `dijkstra.py`, `graph.py` (load + validasi + KD-tree), `snap.py`, `estimate.py`, fixture graf kecil. **Tanpa OSM.** | Test 10.1 lulus 100%; seluruh test Fase 0 tetap lulus |
| **2. Build graf** | **Tanyakan R-01 dulu.** `coverage.yaml`, `speeds.yaml`, `build_graph.py`, `requirements-build.txt` | Graf area terpilih terbangun; ringkasan node/edge/ukuran dilaporkan |
| **3. Endpoint** | **Tanyakan R-07 dulu.** `service.py`, `router.py`, `errors.py`, `lifespan`, perluasan `/health`, cache, token | Test 10.2 dan 10.3 lulus; service tetap jalan tanpa folder graf |
| **4. Benchmark & dokumentasi** | `bench_route.py`, bagian Routing di README (perintah PowerShell), contoh request/respons | Angka p50/p95/maks dan memori dilaporkan apa adanya |

Fase integrasi dengan backend utama (lampiran A) dikerjakan di repo backend utama, bukan di repo ini.

---

## 10. Pengujian

### 10.1 Unit, tanpa OSM

- `dijkstra` dibandingkan dengan `networkx.shortest_path_length` (dan validitas path-nya) pada:
  - 200 graf acak berarah dan berbobot (seed tetap),
  - graf dengan beberapa jalur berbiaya sama (biaya harus sama; path boleh berbeda),
  - graf tanpa jalur (`NoPathError`),
  - `source == target`,
  - node tanpa edge keluar.
- `load_graph`: menolak array yang ukurannya tidak konsisten dan bobot negatif.
- Snap: titik di dalam batas, melebihi `SNAP_MAX_M`, dan di luar bbox.
- Estimasi: kecepatan per `highway`, termasuk `highway` berupa list.

### 10.2 Service (fixture graf kecil)

- Rute antar dua titik pada fixture menghasilkan jarak yang sudah dihitung manual.
- Geometri dimulai dekat titik asal dan berakhir dekat titik tujuan.
- `via_streets` maksimal 3 nama dan urut sesuai perjalanan.
- Panggilan kedua dengan node yang sama menjadi cache hit.

### 10.3 API (`fastapi.testclient`)

- 200 untuk request valid pada fixture.
- 422 `INVALID_PARAMS`, `OUT_OF_COVERAGE`, `SNAP_TOO_FAR`; 404 `NO_PATH`.
- 503 `ROUTING_UNAVAILABLE` saat graf moda tidak dimuat, **sementara** `/api/recommendations/books` tetap 200.
- `/health` tetap memuat `status` dan `service` dengan nilai lama.
- Perilaku token sesuai R-07.

Fixture dimuat dengan meng-override `app.state.graphs` atau dependency, **bukan** dengan menaruh file di `data/graphs/`.

### 10.4 Benchmark (Fase 4)

`scripts/bench_route.py --graph <versi> --n 500` menjalankan pasangan node acak (seed tetap) dan melaporkan p50, p95, maks latensi, rata-rata node yang di-pop, ukuran graf, dan memori proses setelah graf dimuat. Target latensi belum ditetapkan; usulkan target setelah ada data.

---

## 11. Checklist sebelum fitur ini dirilis

- [ ] R-01 dan R-07 diputuskan; R-10 dan R-11 dicatat di `DECISIONS.md`.
- [ ] Sumber, versi, dan lisensi tabel kode wilayah sudah diverifikasi terhadap publikasi resmi Kemendagri.
- [ ] Backend utama sudah memakai kontrak rekomendasi komunitas yang baru (`user_region_code`), dan `API_SPEC.md` sudah diperbarui.
- [ ] Penempatan routing di ML Service (R-04) disetujui tim, termasuk dampak memori pada instance yang sama.
- [ ] Tidak ada koordinat pengguna di log atau error tracking.
- [ ] Atribusi OSM tampil di peta; kebijakan unduhan data dan provider tile sudah diperiksa.
- [ ] File graf tidak ada di Git; cara mendistribusikannya ke server deploy sudah ditentukan (artefak build, storage, atau build di server).
- [ ] Semua kode error di 5.3 dan A.3 punya state UI di frontend.
- [ ] Hasil benchmark dicatat dan target latensi disepakati.

---

## 12. Prompt pembuka untuk Claude Code

Taruh dokumen ini di `docs/BACKEND_PETA_RUTE.md` pada repo ML Service, lalu jalankan dari root repo:

```text
Baca docs/BACKEND_PETA_RUTE.md sampai selesai, lalu README.md dan seluruh isi app/ serta tests/.
Patuhi bagian 0 (aturan) sepanjang pekerjaan.

Mulai dari Fase 0 (bagian 13) saja, dan kerjakan sub-fasenya berurutan: 0a, lalu 0b, lalu 0c.
Sebelum menulis kode:
1. Jalankan `python -m pytest tests` dan laporkan baseline.
2. Bandingkan kondisi repo dengan bagian 1; laporkan jika ada yang berbeda sejak commit deb8fbb.
3. Jalankan ulang setiap bukti bug di bagian 13.2 dan laporkan apakah bug itu masih bisa direproduksi.
4. Tunjukkan rencana perubahan file untuk sub-fase 0a.
Setelah saya setuju, kerjakan 0a, jalankan test, dan laporkan hasilnya apa adanya.
Berhenti dan minta konfirmasi saya di akhir setiap sub-fase dan setiap fase.
```

---

## 13. Fase 0 — Fondasi & perbaikan kode lama

Fase ini dikerjakan **sebelum** routing, karena memperbaiki hasil rekomendasi yang salah dan menyiapkan fondasi repo yang dipakai fase routing.

### 13.1 Sub-fase

| Sub-fase | Isi | Perilaku API berubah? |
|---|---|---|
| **0a. Fondasi** | 13.4 | Tidak. 10 test lama harus lulus tanpa diubah. |
| **0b. Rekomendasi buku & teks** | 13.2 bug B-1, B-2, B-5, B-6 | Ya, aditif (field baru) dan isi hasil |
| **0c. Komunitas & kode wilayah** | 13.2 bug B-2, B-3, B-4 dan 13.3 | Ya, **breaking** pada request komunitas |

### 13.2 Bug yang diperbaiki

Semua bukti di bawah direproduksi pada commit `deb8fbb`, 17 Okt 2026. Claude Code wajib menjalankan ulang bukti ini sebelum memperbaiki.

| ID | Bug | Bukti | Perbaikan |
|---|---|---|---|
| B-1 | Buku berskor 0 dikembalikan dengan alasan "Memiliki kemiripan dengan minat Anda" | `get_recommendations(["romansa","horor"], 5)` → `book_id` 10000, 9999, 9998, … semua skor 0.0. `["pramoedya"]` dengan `top_n=20` → 19 dari 20 berskor 0. | Lihat algoritma 13.5. |
| B-2 | Alasan dicocokkan per substring | `recommend_communities(["lit"], None, None, 5)` → "Komunitas Literasi Umum", `interest_score` 0.0, alasan "Sesuai dengan minat: lit" ("lit" ada di dalam "literacy"). Fungsi yang sama dipakai di `get_reason` buku. | Pencocokan per token memakai analyzer TF-IDF yang sama dengan skor: sebuah minat hanya disebut cocok jika minimal satu token-nya berbobot > 0 di vektor item tersebut. |
| B-3 | Pencocokan kota memakai string mentah | `"Tangsel"`, `"Kota Tangerang Selatan"`, `" tangerang selatan "` semuanya gagal dianggap kota yang sama (skor lokasi 0.5, bukan 1.0). | Kode wilayah (13.3). |
| B-4 | Komunitas tanpa minat dan tanpa lokasi tetap direkomendasikan | `recommend_communities([], None, None, 3)` → C001, C002, C003 (urutan data mentah), semua skor 0. | R-10: daftar kosong + `notice`. Selain itu, hanya komunitas dengan `score > 0` yang dikembalikan. |
| B-5 | Minat tidak dinormalisasi | `["Fantasy", "fantasy "]` → alasan "Sesuai dengan minat: Fantasy, fantasy ". | `app/text.py`: `strip`, rapikan spasi ganda, `casefold`, buang string kosong, buang duplikat dengan urutan dipertahankan. |
| B-6 | Input tidak dibatasi | `user_interests` tanpa batas jumlah dan panjang. | Schema: maksimal 20 minat, setiap minat 1–50 karakter setelah `strip`. |

### 13.3 Kode wilayah (R-11)

**Data referensi**
- `data/reference/wilayah_kabkota.csv` dengan kolom `code`, `name`, `level` (`kota`/`kabupaten`), `province_code`, `province_name`.
- Sumber resmi: Keputusan/Peraturan Menteri Dalam Negeri tentang kode dan data wilayah administrasi pemerintahan, **versi terbaru**. Dataset komunitas di GitHub boleh dipakai untuk mempercepat, tapi isinya harus dicocokkan dengan publikasi resmi. Sumber, nomor peraturan, tanggal, dan lisensi dicatat di `wilayah_meta.json`. **This needs verification**: nomor dan tahun peraturan terbaru belum saya pastikan.
- Hanya tingkat provinsi dan kabupaten/kota. Kecamatan dan desa tidak diperlukan, dan lebih presisi dari yang dibutuhkan untuk privasi lokasi.
- **Jangan menulis kode wilayah dari ingatan.** Semua kode di data demo dan test harus diambil dari file referensi.

**Format kode**: kabupaten/kota `NN.NN` (mis. `36.74`; contoh ini harus diverifikasi terhadap tabel), provinsi `NN` (dua digit pertama).

**Kontrak baru `POST /api/recommendations/communities`**

```json
{
  "user_interests": ["fantasy", "magic"],
  "user_region_code": "36.74",
  "top_n": 5
}
```

- `user_region_code` opsional. Pola `^\d{2}(\.\d{2})?$`: boleh kode kab/kota atau hanya kode provinsi.
- Kode yang formatnya benar tapi tidak ada di tabel → 422.
- **`user_city` dan `user_province` dihapus.** Schema memakai `extra="forbid"`, sehingga pemanggil lama gagal dengan 422 secara jelas, bukan diam-diam kehilangan skor lokasi. Sebelum menghapus, Claude Code harus menanyakan apakah sudah ada pemanggil yang memakai field lama.

Respons:

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

- `location_score`:
  - 1.0 jika kode kab/kota sama,
  - 0.5 jika kode provinsi sama,
  - 0.0 jika berbeda atau pengguna tidak memberi kode.
- `notice`:
  - `NEEDS_INTERESTS_OR_LOCATION` jika minat (setelah normalisasi) kosong **dan** kode wilayah tidak diberikan; `recommendations` kosong.
  - `NO_MATCH` jika ada input tapi tidak ada komunitas dengan `score > 0`; `recommendations` kosong.
  - `null` jika ada hasil.
- Data komunitas demo diberi `region_code` dari tabel referensi, menggantikan `city` dan `province`.

### 13.4 Sub-fase 0a — Fondasi (tanpa perubahan perilaku)

1. Konversi `requirements.txt` dari UTF-16 ke UTF-8. Commit terpisah; pastikan `pip install -r requirements.txt` menghasilkan paket yang sama.
2. Buat `requirements-dev.txt` berisi `-r requirements.txt`, `pytest`, `networkx`.
3. Tetapkan versi Python yang didukung. Cek versi yang dipakai tim di Windows, lalu tulis di README dan `.python-version`. Repo ini sudah terbukti lulus test di Python 3.13; versi lain belum diuji.
4. `app/config.py` dan `.env.example` (bagian 8). Tambahkan `data/graphs/` ke `.gitignore`.
5. `app/model_store.py`: muat `tfidf_vectorizer.joblib` **sekali**, lalu pakai bersama oleh `recommender.py` dan `community.py`.
6. `models/meta.json`: catat versi scikit-learn yang berhasil memuat model, dan tandai bahwa model berasal dari `notebooks/01_exploration.ipynb`.
7. Konfigurasi pytest supaya `sklearn.exceptions.InconsistentVersionWarning` dianggap error. Model yang dimuat dengan versi scikit-learn berbeda tidak boleh lolos diam-diam.

### 13.5 Sub-fase 0b — Algoritma rekomendasi buku yang diperbaiki

```text
interests = normalize(user_interests)                  # B-5
if interests kosong → kembalikan top_n buku populer (source="popularity")

unmatched = minat yang tidak punya satu pun token di vocabulary TF-IDF
scores    = cosine(tfidf(interests), book_vectors)
picked    = indeks dengan score > 0, urut score menurun, dipotong top_n   # B-1
            (sort stabil; jika skor sama, urut menurut indeks)
if len(picked) < top_n:
    isi sisanya dari urutan popularitas, lewati buku yang sudah terpilih
    item tambahan: score=null, source="popularity",
                   reason="Direkomendasikan berdasarkan popularitas buku"
reason untuk item "interest" = minat yang token-nya berbobot > 0 di vektor buku itu   # B-2
```

Perubahan respons buku (aditif):
- tiap item mendapat field `source`: `"interest"` atau `"popularity"`,
- top-level mendapat field `unmatched_interests: list[str]`, supaya UI bisa menulis "Minat 'romansa' belum dikenali".

### 13.6 Test Fase 0 dan kriteria selesai

`tests/test_regressions.py` berisi minimal satu test per bug:

| Bug | Test |
|---|---|
| B-1 | Untuk `["romansa","horor"]`: tidak ada item `source="interest"` berskor 0; jika kedua kata tidak ada di vocabulary, semua item `source="popularity"` dan `unmatched_interests` berisi keduanya. Untuk `["pramoedya"]` dengan `top_n=20`: semua item `interest` berskor > 0, sisanya `popularity`, tanpa `book_id` ganda. |
| B-2 | `["lit"]` tanpa kode wilayah: tidak ada alasan yang menyebut "lit" kecuali token itu benar berbobot > 0; dengan data demo, hasilnya kosong dengan `notice="NO_MATCH"`. |
| B-3 | Kode kab/kota sama → `location_score` 1.0; provinsi sama → 0.5; kode tidak terdaftar → 422; format salah (`"36-74"`) → 422; field lama `user_city` → 422. |
| B-4 | Minat kosong dan tanpa kode wilayah → `recommendations` kosong, `notice="NEEDS_INTERESTS_OR_LOCATION"`. |
| B-5 | `["Fantasy", "fantasy ", "  "]` diperlakukan sama dengan `["fantasy"]`. |
| B-6 | 21 minat → 422; minat 51 karakter → 422. |
| Umum | Request yang sama dua kali menghasilkan respons identik. |

Penyesuaian test lama yang **diperbolehkan** (laporkan masing-masing):
- `assert c001["score"] == 0.894` diganti `pytest.approx`.
- Test komunitas yang memakai `user_city`/`user_province` diganti ke `user_region_code`.
- `test_empty_interests` komunitas: hasilnya kini mengikuti B-4 / `NO_MATCH`, bukan 5 item berskor 0.

Fase 0 selesai jika:
- semua test lulus,
- setiap bukti di 13.2 sudah tidak bisa direproduksi,
- README diperbarui (versi Python, `requirements-dev.txt`, contoh request komunitas baru, field `source`, `unmatched_interests`, `notice`),
- Claude Code melaporkan daftar perubahan kontrak API untuk diteruskan ke tim backend utama dan untuk memperbarui `API_SPEC.md`.

### 13.7 Di luar Fase 0 (backlog, tanyakan sebelum dikerjakan)

- Memindahkan training dari notebook ke `scripts/train_tfidf.py` yang menghasilkan artefak setara.
- Memfilter komunitas `verified = false` dari rekomendasi (keputusan produk).
- Merampingkan `requirements.txt` hasil `pip freeze` (`sentry-sdk`, `opentelemetry-*`, dan sejenisnya), misalnya dengan file dependensi tingkat atas + lock. Perlu dipastikan `fastapi dev` tetap berjalan.
- Memeriksa lisensi dataset Goodbooks-10k yang ikut di-commit.
- Pemetaan `book_id` Goodbooks dan `community_id` demo ke UUID TemuBaca. (Selesai di ML-T04 dan ML-T05.)
- Menyelaraskan `API_SPEC.md` (saat ini menulis `GET`, repo memakai `POST`).

---

## Lampiran A — Kontrak untuk backend utama (bukan repo ini)

Bagian ini untuk tim/repo backend utama (stack TBD, DEC-01). Disertakan agar kontrak kedua sisi konsisten.

### A.1 Data tempat (`places`)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | uuid PK | |
| `type` | `library \| community \| event \| meeting_point` | |
| `name`, `short_name`, `address_public` | text | Alamat publik saja |
| `location` | geography(Point, 4326) | Titik publik; untuk `area`, titik tengah area yang sudah digeneralisasi |
| `location_precision` | `exact \| area` | |
| `area_radius_m` | int NULL | Wajib jika `area` |
| `is_routable` | bool | `CHECK (location_precision = 'exact' OR (area_radius_m IS NOT NULL AND is_routable = false))` |
| `verification_status`, `publication_status` | enum | Hanya `published` yang tampil |
| `source`, `checked_at` | text, timestamptz | Ditampilkan sebagai "Diperbarui …" |

### A.2 `GET /api/places`

Parameter: `lat`/`lng` atau `bbox`, `radius_m` (default 10000, maks 50000), `types`, `q` (maks 100 karakter), `sort`, `limit` (maks 50), `cursor`.

Respons memuat:
- `counts` per tipe (mengikuti area dan radius, bukan filter tipe),
- `items` dengan `distance_m` garis lurus (dibulatkan 100 m), `location_precision`, `area_radius_m`, `is_routable`, `checked_at`,
- `origin.label` (teks, **tanpa koordinat**).

### A.3 `GET /api/route?from=lat,lng&to_place_id=<uuid>&mode=drive`

1. Validasi input dan rate limit (default 30 request/menit per IP).
2. Ambil tempat. Jika tidak ada atau tidak `published` → 404 `PLACE_NOT_FOUND`. Jika `is_routable = false` → 422 `DESTINATION_NOT_ROUTABLE`.
3. Panggil `POST {ML_SERVICE_URL}/api/routing/route` dengan header `X-Internal-Token` dan timeout 5 detik.
4. Teruskan respons dan tambahkan `external_url` (deep link Google Maps ke koordinat tujuan; formatnya perlu diverifikasi ke dokumentasi resmi Google Maps URLs).
5. Petakan error:
   - `OUT_OF_COVERAGE` dan `SNAP_TOO_FAR` → 422, UI "Di luar cakupan rute",
   - `NO_PATH` → 404, UI "Rute tidak ditemukan",
   - `ROUTING_UNAVAILABLE`, timeout, atau koneksi gagal → 503 atau 504, UI fallback.

   Semua error dengan tujuan yang valid tetap menyertakan `external_url`, supaya UI selalu punya tombol "Buka di Google Maps".
