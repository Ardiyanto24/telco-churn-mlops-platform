# Legacy Inference Baseline

Folder ini membekukan perilaku deployment legacy sebelum M1 mengubah struktur kode atau dependency.

## Isi

- `fixtures/golden_inputs.json`: lima payload anonim yang mencakup single record, boundary, batch, dict-of-lists, dan input invalid.
- `expected/legacy_snapshot.json`: output golden, runtime dependency, checksum artefak, warning, serta metadata fitur hasil preprocessing.
- `container_capture.py`: dijalankan di image legacy untuk memuat artefak dan menghasilkan JSON evidence.
- `runner.py`: capture dan verification runner yang dijalankan dari host.

## Prasyarat

- Docker Desktop aktif.
- Image baseline lokal `telco-churn-baseline:local` telah dibangun dari sibling repository `../legacy-deployment`.
- Python host 3.10+ untuk menjalankan `runner.py`; runner hanya memakai standard library.

## Perintah

Capture hanya dilakukan bila baseline legacy memang perlu diperbarui secara sengaja:

```powershell
python baseline/runner.py --capture
```

Setiap perubahan berikutnya harus memakai verification, bukan overwrite snapshot:

```powershell
python baseline/runner.py --verify
```

Runner memasang folder baseline ke container secara read-only dan mengatur `PYTHONDONTWRITEBYTECODE=1`, sehingga test/capture tidak menulis cache ke repository.

## Batas interpretasi

Snapshot ini membuktikan perilaku deployment pada image Docker yang direkam, bukan membuktikan bahwa environment tersebut identik dengan environment saat model dilatih. Detail ketidakcocokan versi dan mitigasi M1 dicatat pada [ADR-0001](../docs/decisions/0001-legacy-baseline-runtime.md).
