# ADR-0002: Gunakan package stabil dan runtime dependency terkunci

## Status

Accepted

## Date

2026-08-01

## Context

Artefak legacy Joblib menyimpan custom transformer dengan module path `__main__`. Handler legacy mengatasi hal tersebut dengan mendaftarkan class ke `__main__` saat import. Pola itu rapuh: artefak baru tidak mempunyai module path eksplisit, import memiliki side effect tersembunyi, dan proses training, serving, serta test tidak memiliki kontrak kode yang stabil.

Selain itu, requirements legacy hanya memiliki lower bounds. Saat M0 dibangun, resolver memasang scikit-learn `1.7.2`, padahal metadata artefak menyatakan scikit-learn `1.6.1` dan memunculkan enam `InconsistentVersionWarning` saat dimuat.

## Decision

- Source baru memakai `src/telco_churn` dengan namespace terpisah untuk API, preprocessing, training, evaluation, monitoring, dan public metrics.
- Transformer baru berada pada `telco_churn.preprocessing` dan tidak boleh melakukan rebinding ke `__main__`.
- Konfigurasi runtime yang memengaruhi keputusan model berada di `telco_churn.settings` dan divalidasi di satu tempat.
- `requirements/runtime.in` mencatat dependency langsung; `requirements/runtime.lock` mem-pin seluruh dependency runtime secara exact.
- Lock mem-pin scikit-learn `1.6.1`. Image `telco-churn-m1-runtime:local` dibangun dari lock tersebut dan terbukti memuat artefak legacy tanpa warning serta menghasilkan skenario prediksi M0 yang identik.

Package metadata mengikuti panduan resmi [PyPA untuk `pyproject.toml`](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/). Lockfile disimpan sebagai requirements file sesuai [dokumentasi pip](https://pip.pypa.io/en/stable/topics/requirements-files/).

## Alternatives Considered

### Tetap menggunakan rebinding `__main__` untuk source baru

- Pro: migrasi artefak lama lebih singkat.
- Kontra: artefak baru tetap bergantung pada entry point pemuat dan sulit dipakai oleh training atau batch job lain.
- Rejected: masalah yang sama akan diteruskan ke artefak baru.

### Membiarkan semua dependency sebagai batas minimum

- Pro: file dependency lebih singkat.
- Kontra: build ulang dapat memunculkan runtime berbeda dan kompatibilitas Joblib tidak dapat diuji ulang secara deterministik.
- Rejected: tidak memenuhi target reproducibility MLOps.

### Mengubah artefak legacy agar menunjuk ke module package baru sekarang

- Pro: satu mekanisme loading sejak awal.
- Kontra: membutuhkan migrasi/re-serialisasi artefak dan kontrak manifest yang belum tersedia.
- Rejected: merupakan scope Milestone 3; M1 hanya membangun jalur stabil untuk artefak masa depan.

## Consequences

- Implementasi baru tidak boleh mengimpor `legacy-deployment/handler.py`.
- Loader kompatibilitas untuk artefak legacy tetap diperlukan sampai M3 mendefinisikan manifest, checksum, dan strategi migrasinya.
- Perubahan dependency harus memperbarui lock dan menjalankan golden verification sebelum diterima.
- `baseline/expected/m1_runtime_candidate.json` adalah bukti runtime M1; `legacy_snapshot.json` tetap oracle observasional M0 dan tidak ditimpa.
