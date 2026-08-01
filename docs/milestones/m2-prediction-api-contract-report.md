# M2 Prediction API Contract Report

## Status

Verified on 2026-08-01.

## Delivered

- API v1 melalui `telco_churn.api.create_app()` dengan `/health/live`, `/health/ready`, `/version`, dan `/v1/predict`.
- Pydantic request/response schemas serta validation kategori, numeric range, cross-field, unknown field, dan batch limit 1–100.
- Respons sukses versioned berisi request ID, model version, schema version, timestamp UTC, threshold, batch summary, dan hasil per customer.
- Error catalogue stabil serta handler yang tidak membocorkan exception internal.
- Snapshot kontrak OpenAPI di `tests/expected/openapi_v1_snapshot.json`.
- Dokumentasi API dan migration note di `docs/api/prediction-api-v1.md`.
- Runtime image M2 dengan `httpx2==2.7.0` untuk FastAPI/Starlette test client.

## Test evidence

| Check | Result |
|---|---|
| API contract tests | 9 passed in `telco-churn-m2-runtime:local` |
| M1–M2 locked-runtime suite | 19 passed |
| Host suite | 25 passed; 12 intentional dependency-runtime skips |
| OpenAPI contract snapshot | Pass |
| M0 candidate verification on M2 image | Pass |

## Exit criteria

| Criterion | Evidence |
|---|---|
| Semua endpoint memiliki kontrak dan tests | `src/telco_churn/api/`, `tests/test_prediction_api.py`, dan dokumentasi v1. |
| Tidak ada `allow_origins=["*"]` pada production | M2 tidak memasang CORS middleware. |
| Legacy punya migration/deprecation note | `docs/api/prediction-api-v1.md` menjelaskan endpoint, payload, error, dan enum pengganti. |
| Golden prediction M0 tetap cocok | `baseline/expected/m2_runtime_candidate.json` diverifikasi terhadap image M2. |

## Known limitations

- App factory default sengaja `MODEL_NOT_READY`; model/preprocessor belum dimuat melalui package baru sampai M3 menyelesaikan manifest dan loader kompatibel.
- M2 tidak menentukan policy CORS production, authentication, rate limit, atau hosting. Kebijakan tersebut tetap gate milestone/deployment berikutnya.

## Handoff ke M3

M3 harus membuat release manifest immutable, memverifikasi checksum/runtime/input signature, dan menyediakan adapter predictor untuk `PredictionService`. Perubahan itu harus mempertahankan schema HTTP v1 serta menjalankan M0 golden verification.
