# Engineering Log — M4: Test Foundation

## Scope yang direncanakan

Menyediakan kerangka automated testing yang konsisten untuk milestone berikutnya: kategori test, fixture terisolasi, command per kategori, coverage artifact, dan aturan determinisme tanpa menambah perilaku model atau API.

## Asumsi kerja yang dipakai

1. `unittest` tetap dipakai sebagai framework utama agar M4 tidak menambah dependency test framework baru pada runtime lock.
2. Kategori test didefinisikan oleh runner proyek karena struktur `tests/` bukan package Python dan belum memakai marker framework.
3. Coverage awal menggunakan `trace` standard library; output hanya artifact lokal dan tidak di-commit.
4. Baseline Docker tetap integration test host, sedangkan API/model test yang membutuhkan dependency terkunci berjalan di image runtime.

## Aktivitas aktual

### 2026-08-01 — Runner kategori dan fixture

- Menambahkan `scripts/run_tests.py` dengan kategori `fast`, `unit`, `api`, `model`, `integration`, dan `all`.
- Menambahkan `tests.support.temporary_workspace`, fixture context manager yang selalu membuat directory sementara milik test dan tidak dapat menunjuk ke storage production.
- Menambahkan `docs/testing.md` untuk command test, aturan penamaan `test_`, determinisme, secret handling, dan pemisahan kategori.
- Menambahkan `coverage/` ke `.gitignore` karena artifact coverage bersifat generated.

### 2026-08-01 — Temuan runner dan verifikasi

- Runner awal mencoba memuat `tests.test_*`; gagal karena `tests/` bukan package Python. Runner diperbaiki agar memakai `unittest` discovery berbasis path file.
- Integration runner kemudian gagal mengimpor `baseline`; root repository ditambahkan ke `sys.path` secara eksplisit. Perbaikan ini hanya memengaruhi test runner.
- Menjalankan fast suite dua kali berturut-turut: masing-masing 7 test lulus.
- Menjalankan model suite: 7 test lulus di `telco-churn-m2-runtime:local`.
- Menjalankan API suite: 9 test lulus di image runtime terkunci.
- Menjalankan integration suite dari host: 6 test baseline Docker lulus; 9 API test di-skip secara eksplisit karena FastAPI tidak tersedia di host dan sudah dijalankan pada image terkunci.
- Menghasilkan coverage artifact pada `coverage/fast/`.
- Memverifikasi command test yang sengaja tidak ada menghasilkan exit code non-zero.

## Command verifikasi yang dijalankan

```powershell
# Locked runtime: fast, model, dan API categories
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m2-runtime:local scripts/run_tests.py model

docker run --rm -e PYTHONDONTWRITEBYTECODE=1 `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m2-runtime:local scripts/run_tests.py api

# Host: Docker baseline integration, coverage, dan repeatability
& 'C:\Users\LENOVO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/run_tests.py integration
& 'C:\Users\LENOVO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/run_tests.py fast --coverage-dir coverage/fast
```

## Penyimpangan dari rencana / kendala

| Item | Dampak | Tindakan |
|---|---|---|
| `tests/` bukan package Python | Runner tidak dapat mengimpor nama modul kategori | Menggunakan discovery berdasarkan nama file. |
| `baseline` berada di root repo | Integration runner gagal saat root tidak ada di `sys.path` | Menambahkan root proyek secara eksplisit dalam runner. |
| Host tidak memiliki FastAPI | API test tidak dapat dieksekusi pada host | Skip tetap eksplisit; kategori API dijalankan pada image runtime terkunci. |

## Handoff ke milestone berikutnya

- M5 menggunakan kategori test dan fixture M4 untuk data contract serta data-versioning test.
- M10 dapat memakai `scripts/run_tests.py` sebagai dasar command CI tanpa mengubah kontrak M0–M3.
