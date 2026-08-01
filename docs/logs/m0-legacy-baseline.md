# Engineering Log — M0: Baseline Legacy

## Scope yang direncanakan

Membekukan perilaku deployment legacy sebelum refactor: runtime yang dapat menjalankan artefak, fixture anonim, snapshot output, dan verifier toleran terhadap perbedaan numerik kecil.

## Aktivitas aktual

### 2026-08-01 — Inisialisasi dokumentasi dan oracle perbandingan

- Menambahkan rancangan MLOps end-to-end serta rencana implementasi milestone.
- Menambahkan `baseline/runner.py` untuk membandingkan JSON snapshot secara rekursif dengan toleransi `0.0001`.
- Menambahkan test unit untuk perbandingan snapshot dan validasi fixture.

Commit terkait:

- `6a833ba` — rancangan arsitektur dan implementation plan.
- `3251f0c` — comparator snapshot.

### 2026-08-01 — Hardening fixture dan capture baseline

- Menambahkan `.gitignore` untuk cache Python setelah cache test sempat muncul di worktree.
- Menambahkan lima skenario input anonim: single, boundary tenure nol, batch, dict-of-lists, dan dataframe kosong.
- Menambahkan `container_capture.py` dan runner Docker read-only untuk mengeksekusi handler legacy di image baseline.
- Mencatat checksum kedua artefak, versi runtime, warning deserialisasi, response, serta metadata fitur hasil preprocessing.

Commit terkait:

- `4ec1915` — ignore cache Python.
- `51c3ebb` — fixture anonim.
- `ffb3682` — capture baseline melalui Docker.

### 2026-08-01 — Temuan kompatibilitas

- Docker image `telco-churn-baseline:local` berhasil dimulai dari Dockerfile legacy.
- Artefak dimuat dan seluruh skenario inference berjalan.
- Ditemukan metadata artefak memakai scikit-learn `1.6.1`, sedangkan requirements legacy yang tidak dipin menyelesaikan ke `1.7.2`.
- Capture menghasilkan enam `InconsistentVersionWarning` untuk transformer dan estimator scikit-learn.
- Tidak ada perubahan pada source legacy atau snapshot untuk “memperbaiki” warning tersebut; temuan disimpan untuk M1.

### 2026-08-01 — Bukti dan penutupan M0

- Menyimpan snapshot di `baseline/expected/legacy_snapshot.json`.
- Menjalankan unit test runner dan `baseline/runner.py --verify`.
- Menulis laporan hasil dan ADR observasional legacy.

Commit terkait:

- `0a6e859` — laporan M0 dan ADR-0001.

## Penyimpangan dari rencana / kendala

| Item | Dampak | Tindakan |
|---|---|---|
| Requirements legacy hanya lower-bound | Build masa depan berpotensi memberi runtime lain | Snapshot diberi status observasional; dependency lock dipindah ke M1. |
| Build Docker awal melampaui batas waktu shell singkat | Tidak mengubah hasil | Memeriksa image akhir lalu melanjutkan verifikasi setelah build selesai. |
| Cache bytecode muncul saat test awal | Berisiko ikut ter-commit | Mengabaikan cache dan memakai `PYTHONDONTWRITEBYTECODE=1` pada runner/container. |

## Handoff ke milestone berikutnya

- M0 adalah oracle perilaku legacy, bukan bukti environment training yang sepenuhnya reproduced.
- M1 wajib menguji lock dependency terhadap oracle ini tanpa menimpa snapshot legacy.
- Migrasi artifact loader belum dilakukan; itu scope M3.

Lihat hasil final di [M0 Baseline Report](../milestones/m0-baseline-report.md) dan alasan keputusan di [ADR-0001](../decisions/0001-legacy-baseline-runtime.md).
