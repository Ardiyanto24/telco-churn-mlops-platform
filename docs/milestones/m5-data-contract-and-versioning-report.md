# M5 Data Contract and Data Versioning Report

## Status

Verified on 2026-08-02.

## Delivered

- Pandera contract `telco-churn-training/v1` for the real Telco training data.
- Deterministic CSV validation CLI, SHA-256 dataset manifest, and verified-data
  loader for the upcoming training pipeline.
- DVC raw-data pointer, validation stage, and `dvc.lock` lineage record.
- Cloudflare R2 S3-compatible remote `r2`; credentials remain in local `.env`.

## Test evidence

| Check | Result |
|---|---|
| M5 contract tests | 7 passed in `telco-churn-m5-runtime:local`. |
| Existing model/artifact/data suite | 14 passed. |
| Fast suite | 7 passed. |
| API suite | 9 passed. |
| Real dataset validation | 594194 rows, 21 columns, schema v1. |
| DVC remote verification | Raw and validated outputs pushed; `dvc status --cloud` reports in sync. |

## Exit criteria

- [x] Training input can be gated by `load_verified_dataset`; invalid contract
  or manifest checksum raises `DataContractError`.
- [x] Raw dataset pointer, DVC lockfile, checksum manifest, schema version, and
  Git revision provide deterministic data lineage.
- [x] Contract version and v2 migration policy are documented in
  `docs/data-contract-v1.md`.
- [x] M5 performs no split or fitting; M6 must create the split before fitting
  transformers, so no M5 split mechanism can introduce leakage.

## Known limitations

- The exact local Python path used for this workstation's DVC stage is an
  environment concern. CI/M6 must use the locked M5 runtime with `python` on
  `PATH`.

## Handoff to M6

- Use `load_verified_dataset(data/validated/telco_churn.csv,
  data/validated/dataset-manifest.json)` as the only data entry point.
- Keep the raw/validated split immutable; fit preprocessing only on the M6
  training partition.
