# Engineering Log — M5: Data Contract dan Data Versioning

## Scope yang direncanakan

Mendefinisikan contract training data yang terversi, validasi Pandera, manifest
checksum/lineage, dan stage DVC tanpa memasukkan data pelanggan ke Git.

## Asumsi kerja

1. Fixture pengujian hanya berisi satu record sintetis dan bukan data pelanggan.
2. Dataset sumber serta remote DVC belum ditentukan, sehingga keduanya tidak
   diisi atau disimulasikan sebagai data production.
3. Nama kolom canonical mengikuti dataset Telco dan legacy preprocessor agar
   M6 tidak membutuhkan translasi field tersembunyi.

## Aktivitas aktual

### 2026-08-02 — Contract, manifest, dan pipeline stage

- Menambahkan `telco_churn.data_contract` dengan Pandera schema
  `telco-churn-training/v1`, domain kategori, range numerik, uniqueness
  `id`, dan aturan lintas field layanan telepon/internet.
- Menambahkan checksum SHA-256 dan `DatasetManifest` yang mencatat versi
  schema, source name, dimensions, dan Git revision. `load_verified_dataset`
  menolak checksum, source, shape, atau schema yang tidak cocok.
- Menambahkan `scripts/validate_dataset.py`; script memvalidasi CSV, menulis
  output validated, lalu manifestnya.
- Menambahkan stage `validate_data` di `dvc.yaml`, ignore rule untuk data raw
  dan validated, serta pin DVC sebagai tooling M5 (`requirements/tooling.in`).
- Memperbarui runtime lock dengan Pandera `0.32.1` beserta dependency transitif
  dan membangun image `telco-churn-m5-runtime:local` dari runtime M2 yang
  sudah terverifikasi.

## Test evidence

| Check | Result |
|---|---|
| RED data-contract tests sebelum modul dibuat | 6 error `ModuleNotFoundError` seperti yang diharapkan. |
| M5 data-contract/model suite | 14 passed di `telco-churn-m5-runtime:local`. |
| Fast suite | 7 passed di host. |
| API suite | 9 passed di `telco-churn-m5-runtime:local`. |

## Kendala yang teratasi

- DVC awalnya mencoba memakai cache global Windows yang tidak dapat ditulis.
  Tooling DVC S3 kemudian dipasang di direktori lokal yang diabaikan Git,
  sehingga inisialisasi dan sinkronisasi dapat dijalankan.

## Penyelesaian aktual

### 2026-08-02 — Dataset nyata dan Cloudflare R2

- Memeriksa header `../data/train.csv` tanpa mencetak record. Dataset memakai
  `id`, bukan `customerID`; contract, fixture, dan dokumentasi disesuaikan
  karena stable preprocessor memang mendukung `id` sebagai identifier yang
  dibuang sebelum training.
- Validasi penuh lulus untuk 594194 baris dan 21 kolom.
- Menyelesaikan inisialisasi DVC subdirectory, menambahkan remote default `r2`
  dengan URL bucket `s3://telco-churn-data`, endpoint R2, dan region `auto`.
  Credentials hanya dibaca dari `.env` sebagai environment proses dan tidak
  ditulis ke `.dvc/config`.
- Menambahkan raw dataset sebagai `data/raw/telco_churn.csv.dvc` dengan MD5
  `1c6cfe5e7567ac95bb13547da91f6ce7`, lalu menjalankan stage `validate_data`.
- Stage menghasilkan `dvc.lock`, `data/validated/telco_churn.csv`, dan manifest
  dengan SHA-256 `0eea83d4d4641f0158d5286fa1415fdfb912d73cc7b6fb5c13c6837a4d52da5c`.
- `dvc push` mengunggah raw dataset, validated dataset, dan manifest; `dvc
  status --cloud` menyatakan cache dan remote `r2` sinkron.

## Handoff

- M6 wajib memanggil `load_verified_dataset` sebelum split/training dan mencatat
  manifest dataset pada setiap training run.
