# M4 Test Foundation Report

## Status

Verified on 2026-08-01.

## Delivered

- `scripts/run_tests.py` dengan kategori `fast`, `unit`, `api`, `model`, `integration`, dan `all`.
- `tests.support.temporary_workspace` untuk resource temporary yang test-owned dan terisolasi.
- Dokumentasi command, determinism rules, naming, dan batas keamanan di `docs/testing.md`.
- Coverage artifact berbasis `trace` standard library dengan output `coverage/` diabaikan Git.

## Test evidence

| Check | Result |
|---|---|
| Fast suite | 7 passed, kemudian 7 passed lagi pada run kedua. |
| Model suite | 7 passed di `telco-churn-m2-runtime:local`. |
| API suite | 9 passed di `telco-churn-m2-runtime:local`. |
| Integration suite | 6 baseline Docker tests passed; 9 API tests intentionally skipped di host karena dependency runtime tidak tersedia. |
| Coverage artifact | `coverage/fast/` berhasil dihasilkan. |
| Intentional failure | `tests.does_not_exist` menghasilkan exit code non-zero. |

## Exit criteria

| Criterion | Evidence |
|---|---|
| Test suite dapat digunakan CI | Runner kategori dan command terdokumentasi di `scripts/run_tests.py` serta `docs/testing.md`. |
| Fixture tidak menulis production database/storage | `temporary_workspace` hanya menggunakan `tempfile.TemporaryDirectory`. |
| Secret tidak diperlukan untuk fast tests | Fast suite hanya memuat settings dan dependency lock tests. |
| Test report dan coverage dapat dihasilkan | Output `unittest` per kategori serta `coverage/fast/` dari runner. |

## Known limitations

- Coverage M4 adalah artifact `trace` berbasis file, belum berupa percentage threshold; kebijakan threshold dapat diperketat saat CI M10 tersedia.
- API tests membutuhkan image runtime terkunci dan secara sengaja skip pada host dependency-free.

## Handoff ke M5

M5 dapat menambahkan data contract dan data-versioning tests ke kategori yang ada. M10 kemudian dapat menjalankan kategori fast pada PR dan kategori runtime/integration pada job terpisah.
