# ADR-0001: Gunakan snapshot Docker sebagai baseline observasional legacy

## Status

Accepted

## Date

2026-08-01

## Context

Deployment legacy hanya menyediakan `Dockerfile`, `requirements.txt` dengan batas minimum, dan artefak Joblib. Model serta preprocessor dapat dimuat pada image `telco-churn-baseline:local`, tetapi artefak menyatakan dibuat dengan scikit-learn `1.6.1`, sedangkan resolusi requirements saat capture memasang `1.7.2`.

M0 perlu membekukan perilaku yang sedang dapat dijalankan sebelum M1 melakukan refactor. Menunda seluruh baseline sampai environment training persis ditemukan akan menghilangkan titik pembanding untuk refactor awal.

## Decision

Gunakan image Docker Python 3.10 dari Dockerfile legacy untuk membuat snapshot inference observasional. Snapshot wajib menyimpan:

- fixture anonim;
- output inference dan urutan/count fitur preprocessing;
- checksum model serta preprocessor;
- versi runtime dependency aktual;
- warning deserialisasi;
- skenario invalid legacy.

Snapshot diverifikasi dengan eksekusi kedua pada image yang sama. Ia tidak diberi label sebagai reproduksi training yang deterministik.

## Alternatives Considered

### Menunggu seluruh versi environment training ditemukan

- Pro: baseline dapat langsung disebut reproduksi training bila seluruh versi cocok.
- Kontra: M1 tidak memiliki regression oracle selama investigasi berlangsung.
- Rejected: terlalu menunda baseline perilaku yang tetap dibutuhkan sekarang.

### Menggunakan Python host 3.12

- Pro: tidak membutuhkan Docker.
- Kontra: tidak cocok dengan Dockerfile legacy yang mendeklarasikan Python 3.10 dan sebelumnya tidak memiliki dependency proyek.
- Rejected: risiko kompatibilitas lebih besar.

### Mengubah requirements legacy pada M0

- Pro: dapat langsung mem-pin versi dependency.
- Kontra: mengubah source legacy sebelum perilaku awalnya dibekukan.
- Rejected: di luar scope M0.

## Consequences

- M0 memiliki golden-output oracle yang dapat dipakai M1.
- Warning `InconsistentVersionWarning` adalah known risk, bukan error yang diabaikan.
- M1 harus membuat dependency lock yang kompatibel dengan artefak atau secara eksplisit membuktikan kompatibilitas versi baru.
- Perubahan pada image/tag atau artefak harus menghasilkan snapshot/baseline baru, bukan menimpa bukti lama tanpa catatan.
