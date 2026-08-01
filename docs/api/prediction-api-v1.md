# Prediction API v1

## Status dan batas M2

Kontrak ini selesai pada Milestone 2. Aplikasi dibuat melalui `telco_churn.api.create_app()` dan menyediakan kontrak HTTP yang tervalidasi tanpa memuat Joblib saat import atau startup. Penyedia predictor nyata dan pemuatan artefak terverifikasi tetap menjadi scope M3.

Endpoint legacy (`/predict` dan `/`) tidak diubah. Client baru harus memakai `POST /v1/predict`; tidak ada janji kompatibilitas payload longgar maupun respons `{ "status": "error" }` legacy pada API v1.

## Endpoint

| Endpoint | Hasil |
|---|---|
| `GET /health/live` | `200` bila proses API hidup; tidak bergantung pada model atau store monitoring. |
| `GET /health/ready` | `200` bila predictor tersedia, atau `503 MODEL_NOT_READY`. |
| `GET /version` | Metadata service, model, dan schema tanpa path artefak atau detail internal. |
| `POST /v1/predict` | Prediksi batch tervalidasi. |
| `GET /openapi.json` | OpenAPI yang digenerasikan FastAPI; kontrak ringkasnya dijaga di `tests/expected/openapi_v1_snapshot.json`. |

Tidak ada CORS middleware pada M2, sehingga `allow_origins=["*"]` tidak digunakan.

## Request

Body memiliki satu field, `inputs`, berupa array 1 sampai 100 record. Nama field memakai `snake_case`. Semua field harus ada; field tambahan, kategori di luar domain, dan relasi layanan yang tidak konsisten ditolak dengan HTTP `422`.

```json
{
  "inputs": [
    {
      "customer_id": "DEMO-0001",
      "gender": "Female",
      "senior_citizen": 0,
      "partner": "Yes",
      "dependents": "No",
      "tenure": 1,
      "phone_service": "No",
      "multiple_lines": "No phone service",
      "internet_service": "DSL",
      "online_security": "No",
      "online_backup": "Yes",
      "device_protection": "No",
      "tech_support": "No",
      "streaming_tv": "No",
      "streaming_movies": "No",
      "contract": "Month-to-month",
      "paperless_billing": "Yes",
      "payment_method": "Electronic check",
      "monthly_charges": 29.85,
      "total_charges": 29.85
    }
  ]
}
```

`tenure` berada pada rentang 0–72. `monthly_charges` dan `total_charges` harus non-negatif. Bila `phone_service` adalah `No`, maka `multiple_lines` harus `No phone service`; bila `internet_service` adalah `No`, keenam fitur layanan internet harus `No internet service`.

## Response sukses

Respons `200` selalu memiliki `request_id` UUID baru, timestamp UTC berakhiran `Z`, `model_version`, `schema_version: "v1"`, threshold, ringkasan batch, serta satu hasil untuk setiap input.

```json
{
  "request_id": "b7efdc22-6134-4d2c-9a06-b1f548f7ed74",
  "model_version": "legacy-m0-compatible",
  "schema_version": "v1",
  "timestamp_utc": "2026-08-01T12:00:00.000000Z",
  "decision_threshold": 0.6238,
  "summary": {
    "total_customers": 1,
    "predicted_churn": 1,
    "churn_rate_pct": 100.0,
    "avg_churn_probability": 0.8411
  },
  "results": [
    {
      "customer_id": "DEMO-0001",
      "churn_binary": 1,
      "churn_prediction": "CHURN",
      "churn_probability": 0.8411,
      "risk_level": "HIGH"
    }
  ]
}
```

`risk_level` (`SAFE`, `LOW`, `MEDIUM`, `HIGH`) independen dari keputusan biner dan diturunkan dari risk band pada `telco_churn.settings`; threshold keputusan juga berasal dari sana.

## Error catalogue

| HTTP | `error.code` | Makna |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Body tidak memenuhi schema, domain, aturan lintas field, atau batas batch. |
| 503 | `MODEL_NOT_READY` | Predictor tidak tersedia; liveness tetap sehat. |
| 500 | `INTERNAL_ERROR` | Kegagalan internal tak terduga; detail exception dan stack trace tidak dikirim ke client. |

Semua error memakai bentuk berikut dan menyertakan `request_id` untuk korelasi aman:

```json
{
  "request_id": "f1b7bc03-b4c5-4a2a-aeaf-a5624cfb5e5e",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request payload does not satisfy the v1 prediction contract.",
    "details": []
  }
}
```

## Migrasi dari legacy

| Legacy | API v1 |
|---|---|
| `POST /predict` atau `/` | `POST /v1/predict` |
| `inputs` dapat berbentuk list, dict-of-lists, CSV, atau Base64 | `inputs` wajib array JSON record tervalidasi |
| field `camel`/Pascal seperti `customerID`, `MonthlyCharges` | `snake_case` seperti `customer_id`, `monthly_charges` |
| error payload dapat kembali `200` dengan `status: error` | input invalid selalu `422` dengan `VALIDATION_ERROR` |
| label teks `Churn` / `No Churn` dan `High Risk` | enum stabil `CHURN` / `NO_CHURN` dan `HIGH` / `MEDIUM` / `LOW` / `SAFE` |

Integrasi baru tidak boleh bergantung pada endpoint legacy. Endpoint legacy hanya dipertahankan sebagai oracle M0 sampai kebijakan deprecation ditetapkan pada release/deployment mendatang.
