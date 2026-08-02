# Engineering Logs

Folder ini adalah catatan proses kerja per milestone. Ia berbeda dari `docs/milestones/`:

| Lokasi | Tujuan |
|---|---|
| `docs/milestones/` | Ringkasan hasil, exit criteria, dan cara verifikasi milestone yang sudah selesai. |
| `docs/logs/` | Urutan pekerjaan aktual: asumsi, aktivitas, temuan, perubahan rencana, command verifikasi, dan commit. |

## Aturan pencatatan

- Satu file per milestone: `m<nomor>-<slug>.md`.
- Tambahkan entri selama pekerjaan berlangsung, bukan hanya saat selesai.
- Bedakan secara eksplisit antara rencana dan pekerjaan aktual.
- Catat command yang dijalankan, hasil penting, error/penyimpangan, serta keputusan tindak lanjut.
- Jangan mencatat secret, payload pelanggan, token, atau data sensitif.
- Log tidak menggantikan ADR: keputusan arsitektur yang bertahan lama tetap dicatat di `docs/decisions/`.

## Struktur trace wajib

Setiap log milestone memakai heading yang relevan dari daftar berikut. Heading boleh
digabung untuk pekerjaan kecil, tetapi tidak boleh menghilangkan fakta material.

| Kategori | Wajib dicatat |
|---|---|
| Context dan assumptions | Tujuan, scope, constraint, dan asumsi yang dipakai. |
| Plan dan actions | Langkah aktual, file yang diubah, serta command penting. |
| Evidence dan findings | Hasil test, measurement, inspeksi artefak, atau bukti lain. |
| Errors dan handling | Gejala, penyebab (jika diketahui), penanganan, hasil verifikasi, dan dampak tersisa. |
| Decisions dan deviations | Keputusan yang berbeda dari rancangan/plan awal, alasan, alternatif material, serta sumber otoritasnya. |
| Risks, limitations, follow-up | Klaim yang tidak dapat dibuat, dependency/keputusan yang belum ada, dan handoff ke milestone/owner berikutnya. |
| Trace references | Versi config/data/model/artifact, commit, ADR, dan command reproduksi. |

Untuk keputusan arsitektur yang tahan lama, buat atau perbarui ADR dan tautkan dari
log. Jangan memakai log untuk menyembunyikan kegagalan: kegagalan yang relevan
tetap dicatat walau sudah ditangani.

## Daftar log

- [M9 container dan local runtime](m9-container-and-local-runtime.md)
- [M8 evaluation dan promotion gates](m8-evaluation-and-promotion-gates.md)
- [M7 experiment tracking dan model registry](m7-experiment-tracking-and-registry.md)

- [M0 — Baseline legacy](m0-legacy-baseline.md)
- [M1 — Package foundation dan runtime lock](m1-package-foundation.md)
- [M2 — Prediction API contract](m2-prediction-api-contract.md)
- [M3 — Artifact contract dan model loading](m3-artifact-contract.md)
- [M4 — Test foundation](m4-test-foundation.md)
- [M5 — Data contract dan data versioning](m5-data-contract-and-versioning.md)
