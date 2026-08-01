# M1 Package Foundation Report

## Status

Verified on 2026-08-01.

## Delivered

- Package `src/telco_churn` dengan namespace API, preprocessing, training, evaluation, monitoring, dan public metrics.
- `Settings` immutable serta loader tervalidasi; override dapat berasal dari mapping eksplisit atau environment proses.
- Satu sumber threshold keputusan dan risk bands di `telco_churn.settings`.
- Custom transformer versi baru memiliki module path stabil `telco_churn.preprocessing`.
- `requirements/runtime.in`, `requirements/runtime.lock`, dan `docker/m1-runtime.Dockerfile` untuk runtime reproducible.

## Compatibility evidence

Image `telco-churn-m1-runtime:local` dibangun dari `requirements/runtime.lock` memakai Python `3.10.20` dan scikit-learn `1.6.1`.

| Check | Result |
|---|---|
| Legacy model/preprocessor can load | Pass |
| `InconsistentVersionWarning` count | `0` |
| Artifact SHA-256 matches M0 | Pass |
| M0 scenario outputs and preprocessing metadata | Identical at tolerance `0.0001` |
| Stable package import graph | Pass; no `handler` import |

Evidence runtime lengkap berada di `baseline/expected/m1_runtime_candidate.json`. File itu bukan pengganti `baseline/expected/legacy_snapshot.json`.

## Commands verified

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest tests.test_settings tests.test_dependency_lock

docker run --rm -e PYTHONDONTWRITEBYTECODE=1 `
  --mount "type=bind,source=$((Get-Location).Path),target=/workspace,readonly" `
  --workdir /workspace -e PYTHONPATH=/workspace/src `
  --entrypoint python telco-churn-m1-runtime:local `
  -m unittest tests.test_import_graph tests.test_preprocessing

python baseline/runner.py --image telco-churn-m1-runtime:local `
  --snapshot baseline/expected/m1_runtime_candidate.json --capture
```

## Explicit boundary

M1 does not create a production API, load artifacts through the new package, or migrate old Joblib objects. Those changes require the API contract work in M2 and artifact-contract work in M3.
