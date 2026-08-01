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

## Daftar log

- [M0 — Baseline legacy](m0-legacy-baseline.md)
- [M1 — Package foundation dan runtime lock](m1-package-foundation.md)
