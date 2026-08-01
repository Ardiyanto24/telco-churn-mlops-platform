# Engineering Log — M3: Artifact Contract dan Model Loading

## Scope yang direncanakan

Membuat bundle artefak immutable dengan manifest, checksum, runtime compatibility, feature signature, dan migrasi satu-kali artefak legacy ke module path stabil.

## Aktivitas aktual

### 2026-08-01 — Manifest dan verified loader

- Menulis test-first untuk bundle valid, manifest hilang, checksum artifact berubah, feature signature manifest salah, serta model/preprocessor dengan feature count berbeda.
- Test awal gagal karena `telco_churn.artifacts` belum tersedia.
- Menambahkan `ArtifactManifest`, `VerifiedArtifactLoader`, dan `write_manifest`.
- Loader memverifikasi manifest, runtime Python/Joblib/scikit-learn, nama file aman, SHA-256, dan signature sebelum atau setelah deserialisasi sesuai batas pemeriksaannya. Joblib hanya dipanggil setelah manifest dan digest kedua artifact cocok.
- Menjalankan `docker run ... -m unittest tests.test_artifact_bundle -v`: 5 test lulus pada `telco-churn-m2-runtime:local`.

## Keputusan sementara

- Bundle release akan menyimpan artifact `model.joblib` dan `preprocessor.joblib` serta `model_manifest.json` yang tidak boleh ditimpa.
- Serving loader tidak boleh melakukan rebinding `__main__`. Kompatibilitas `__main__` hanya boleh ada dalam migrator eksplisit yang menghasilkan artifact baru ber-module `telco_churn.preprocessing`.

## Handoff internal

- Berikutnya: implementasi dan test migrator legacy, kemudian hubungkan bundle terverifikasi ke `PredictionService`/readiness M2.
