# Engineering Log — M2: Prediction API Contract

## Scope yang direncanakan

Mendefinisikan dan menguji schema, semantik HTTP, versioning, health checks, error stabil, dan OpenAPI untuk Prediction API tanpa mengganti loader artefak legacy. Artifact manifest serta loader Joblib terverifikasi tetap scope M3.

## Asumsi kerja

1. API v1 adalah kontrak baru dan tidak perlu mempertahankan payload longgar atau error-HTTP-200 milik legacy.
2. Predictor disuntikkan melalui `PredictionService`; default app tidak ready hingga M3 memasok loader terverifikasi.
3. Nilai threshold dan risk band tetap dibaca dari `telco_churn.settings`.
4. Kategori telco yang diketahui pada fixture M0 menjadi domain input v1; unknown category sengaja ditolak sebagai HTTP `422` sesuai rencana M2.

## Aktivitas aktual

### 2026-08-01 — Kontrak dan test-first

- Menambahkan test kontrak API sebelum implementasi untuk prediksi single/batch, validation, limit batch 100, health/readiness, version, exception sanitization, dan OpenAPI snapshot.
- Menjalankan test awal di image M1. Test gagal sebelum source API tersedia, sesuai siklus test-first; test client juga menemukan dependency yang belum dikunci, `httpx2`.

### 2026-08-01 — Implementasi API v1

- Menambahkan Pydantic schemas dengan required fields, domain kategori, batas numerik, validasi cross-field, dan larangan field tambahan.
- Menambahkan app factory dengan `/health/live`, `/health/ready`, `/version`, dan `/v1/predict`.
- Menetapkan respons error seragam `VALIDATION_ERROR`, `MODEL_NOT_READY`, dan `INTERNAL_ERROR`; respons internal tidak mengirim stack trace atau pesan exception.
- Menambahkan `PredictionService` yang readiness-aware. Ia menerima predictor injeksi untuk test dan belum memuat artifact—boundary ini menjaga M2 tidak melompati M3.
- Menambahkan dokumentasi kontrak, error catalogue, contoh payload, serta migration note legacy.

### 2026-08-01 — Runtime dan verifikasi

- Starlette `1.3.1` di lock runtime meminta `httpx2` untuk `TestClient`. Menambahkan direct pin `httpx2==2.7.0` dan transitive exact pins `httpcore2==2.7.0`, `truststore==0.10.4`.
- Membangun image `telco-churn-m2-runtime:local`; build melewati timeout awal 120 detik dan selesai pada run dengan batas lebih panjang.
- Menjalankan 9 test API pada image M2: seluruhnya lulus.
- Menjalankan host suite menggunakan executable Python workspace karena `python` maupun `py` tidak terdaftar di shell agent. Hasil: 25 test lulus, 12 skip dependency-runtime yang disengaja.
- Menjalankan 19 test M1–M2 dalam image M2: seluruhnya lulus.
- Menangkap dan memverifikasi `baseline/expected/m2_runtime_candidate.json` terhadap image M2. Verifikasi oracle M0 lulus tanpa menimpa `legacy_snapshot.json`.

## Command verifikasi yang dijalankan

```powershell
docker build --tag telco-churn-m2-runtime:local --file mlops/docker/m1-runtime.Dockerfile .

docker run --rm -e PYTHONDONTWRITEBYTECODE=1 `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m2-runtime:local `
  -m unittest tests.test_import_graph tests.test_preprocessing tests.test_settings `
  tests.test_dependency_lock tests.test_prediction_api -v

& 'C:\Users\LENOVO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  baseline/runner.py --image telco-churn-m2-runtime:local `
  --snapshot baseline/expected/m2_runtime_candidate.json --capture
```

## Penyimpangan dari rencana / kendala

| Item | Dampak | Tindakan |
|---|---|---|
| `TestClient` tidak tersedia pada image M1 | Test API tidak dapat mulai | Mengunci `httpx2` beserta dependency transitif dan membangun image M2. |
| Build runtime melewati timeout 120 detik | Verifikasi tertunda | Build diulang dengan batas waktu lebih panjang dan selesai. |
| `python` dan `py` tidak tersedia di shell agent | Host suite tidak dapat memakai command pendek | Memakai executable Python workspace; ini tidak mengubah source atau runtime proyek. |

## Handoff ke milestone berikutnya

- M3 harus menyediakan manifest dan loader terverifikasi lalu memasok predictor nyata ke `PredictionService` tanpa mengubah kontrak HTTP v1.
- Kontrak `docs/api/prediction-api-v1.md` dan snapshot OpenAPI adalah baseline perubahan API berikutnya.
- Endpoint legacy tetap read-only dan tidak menjadi dependency package baru.
