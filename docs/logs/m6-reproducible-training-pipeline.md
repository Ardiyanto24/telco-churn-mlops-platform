# Engineering Log — M6: Reproducible Training Pipeline

## Scope dan asumsi

- Kandidat M6 adalah `LogisticRegression`, bukan pengganti model production dan belum melewati promotion gate M8.
- Split stratified dikonfigurasi 70% train, 15% validation, dan 15% test dengan seed `42`.
- Preprocessor hanya di-fit pada train; threshold F1 hanya dipilih dari validation; metric final hanya berasal dari test.

## Aktivitas aktual — 2026-08-02

- Menambahkan config versi `configs/training/m6-logistic-v1.json`, pipeline `telco_churn.training.pipeline`, dan CLI `scripts/train_model.py`.
- Pipeline mewajibkan `load_verified_dataset` sebelum membuat output; checksum atau contract yang gagal menghentikan training.
- Menyimpan model, preprocessor, manifest M3, metrics JSON, run record JSON, dan grafik precision-recall SVG dalam satu candidate directory immutable.
- Menambahkan tes repeatability, metadata perubahan seed, batas split, penolakan dataset tampered, dan loading candidate oleh M3.
- Tes RED pertama gagal karena modul M6 belum ada. Tes GREEN awal menemukan threshold validation dapat bertentangan dengan risk-band statis. Risk band kandidat kemudian diderivasi secara terpusat oleh `settings` agar manifest M3 selalu valid, tanpa mengubah nilai production.
- Training penuh selesai pada dataset tervalidasi 594194 baris. Candidate lokal tetap diabaikan Git dan bukan artifact production/registry.

## Bukti verifikasi sementara

| Check | Result |
|---|---|
| RED training-module test | `ModuleNotFoundError` seperti diharapkan. |
| M6 model/contract suite | 18 passed di `telco-churn-m5-runtime:local`. |
| Full suite | 41 passed; satu baseline integration tidak dapat menjalankan Docker dari dalam container. |
| Final full CLI training | selesai dari commit `e4da1aa`; 155.5 detik. |
| M3 bundle verification | load sukses; 29 feature output. |

## Handoff

- M7 harus meregistrasikan metadata `training_run.json`, manifest bundle, dan artifact URI sebagai run immutable; M6 tidak menyediakan registry atau gate.

## Revisi multi-model — 2026-08-02

- Keputusan pengguna: ensemble default mengikuti artefak legacy aktual, yaitu
  LightGBM dan dua XGBoost berbobot `5/3/1`; Logistic Regression tetap kandidat
  mandiri. Dokumentasi lama yang menyebut Logistic Regression sebagai anggota
  ensemble dikoreksi.
- Menambahkan model factory untuk empat `model.type`, contoh config masing-masing,
  metadata `model_family`, dan manifest v2. Loader tetap menerima manifest v1
  legacy dengan family `legacy_unknown`.
- Image `telco-churn-m6-runtime:local` menambahkan `libgomp1`, karena wheel
  LightGBM tidak dapat diimpor pada image M5 tanpa runtime OpenMP.
- Tes RED gagal seperti diharapkan sebelum factory/model family tersedia; tes
  GREEN multi-model lulus 19 tests di image M6.
