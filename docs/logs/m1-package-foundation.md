# Engineering Log — M1: Package Foundation dan Runtime Lock

## Scope yang direncanakan

Membuat package Python terstruktur, settings tervalidasi, module path stabil untuk custom transformer, dan dependency runtime deterministik tanpa mengubah kontrak API legacy atau loader artefak legacy.

## Asumsi kerja yang dipakai

1. Source baru berada di `src/telco_churn`; `legacy-deployment` bersifat read-only.
2. Endpoint FastAPI baru ditunda ke M2; artifact manifest dan loader baru ditunda ke M3.
3. Runtime perlu kembali ke scikit-learn `1.6.1` karena itulah versi serialisasi artefak yang terdeteksi pada M0.
4. Settings memakai standard library pada M1 agar tidak menambah framework konfigurasi sebelum API/runtime contract ada.

## Aktivitas aktual

### 2026-08-01 — Fondasi package dan konfigurasi

- Membuat `pyproject.toml` dan package `src/telco_churn`.
- Membuat `Settings` immutable serta `load_settings`; default aman tersedia untuk development dan override environment divalidasi.
- Memusatkan decision threshold dan risk-band di `telco_churn.settings`.
- Menulis test terlebih dahulu untuk default, override, nilai nonnumerik, nilai di luar risk-band, dan pembacaan environment proses.

Commit terkait:

- `9592aa9` — settings tervalidasi.

### 2026-08-01 — Module preprocessing stabil

- Menulis test kontrak yang awalnya gagal karena `telco_churn.preprocessing` belum ada.
- Memindahkan definisi transformer ke `telco_churn.preprocessing` dan feature metadata ke `telco_churn.constants`.
- Sengaja tidak melakukan rebinding class ke `__main__`; mekanisme itu hanya tetap di handler legacy sampai M3.
- Menjalankan test transformasi feature engineering dan test module path dalam container baseline.

Commit terkait:

- `835cd5d` — stable preprocessing module.

### 2026-08-01 — Dependency lock dan bukti kompatibilitas

- Menulis test awal yang gagal karena `requirements/runtime.lock` belum tersedia.
- Membuat `runtime.in`, `runtime.lock`, dan `docker/m1-runtime.Dockerfile`.
- Membangun `telco-churn-m1-runtime:local` dari lock dengan scikit-learn `1.6.1`.
- Menjalankan capture kandidat ke `baseline/expected/m1_runtime_candidate.json`, tanpa menimpa oracle M0.
- Membandingkan hanya bagian skenario prediksi dan metadata preprocessing terhadap snapshot M0: seluruhnya identik pada toleransi `0.0001`.
- Memverifikasi bahwa warning deserialisasi pada runtime kandidat berjumlah nol.
- Membandingkan lockfile dengan `pip freeze` dari image verifikasi: hasil identik.

### 2026-08-01 — Struktur package dan test matrix

- Menambahkan namespace placeholder untuk API, training, evaluation, monitoring, dan public metrics agar import graph target sudah eksplisit.
- Menambahkan test import graph untuk memastikan package M1 tidak mengimpor `legacy-deployment/handler.py`.
- Menemukan bahwa Python host untuk baseline hanya standard library; test preprocessing/import gagal karena tidak ada scikit-learn.
- Mengubah test agar skip secara eksplisit hanya saat dependency runtime tidak tersedia di host. Test yang sama tetap dijalankan dan lulus dalam image M1 terkunci.
- Menambahkan laporan M1 dan ADR-0002.

Commit terkait:

- `9068e54` — runtime lock, image verifikasi, bukti kompatibilitas, dan dokumentasi.

## Command verifikasi yang dijalankan

```powershell
# Host: baseline dan test yang tidak membutuhkan dependency project
python -m unittest discover -s tests -v

# Container M1: test yang membutuhkan dependency runtime terkunci
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m1-runtime:local `
  -m unittest tests.test_import_graph tests.test_preprocessing tests.test_settings tests.test_dependency_lock -v
```

Hasil akhir: host suite 16 test lulus dengan 3 skip dependency-runtime yang disengaja; container M1 menjalankan 10 test dan seluruhnya lulus.

## Penyimpangan dari rencana / kendala

| Item | Dampak | Tindakan |
|---|---|---|
| Build image verifikasi pertama melewati timeout 120 detik | Image belum terbentuk pada percobaan pertama | Menjalankan build ulang dengan timeout lebih panjang; build selesai. |
| Host tidak memiliki pandas/scikit-learn | Full discovery awal gagal pada import test | Memisahkan matriks host dan container secara eksplisit; test dependency tetap wajib lulus di image M1. |
| Artefak lama memakai module path `__main__` | Memindahkan class saja tidak membuat Joblib legacy dapat dimuat package baru | Tidak mengubah loader; dicatat sebagai dependency M3. |

## Handoff ke milestone berikutnya

- M2 dapat membangun API dari `telco_churn` tanpa menyentuh handler legacy.
- M3 harus mendefinisikan manifest artefak, checksum, dan compatibility loader/migration dari `__main__` ke package path stabil.
- Setiap perubahan lock wajib membangun image verifikasi dan membandingkan terhadap oracle M0.

Lihat hasil final di [M1 Package Foundation Report](../milestones/m1-package-foundation-report.md) dan keputusan arsitektur di [ADR-0002](../decisions/0002-stable-package-and-runtime-lock.md).
