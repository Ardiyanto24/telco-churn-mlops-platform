# M3 Artifact Contract Report

## Status

Verified on 2026-08-01.

## Delivered

- Immutable `model_manifest.json` schema with model, preprocessor, checksums, runtime, feature signature, threshold, risk bands, and baseline ID.
- `VerifiedArtifactLoader` verifies the trusted manifest and SHA-256 digests before calling Joblib.
- Explicit `migrate_legacy_bundle` creates artifacts with stable `telco_churn.preprocessing` references; `__main__` aliases exist only during migration.
- API service can construct a ready predictor only from a verified artifact directory.

## Test evidence

- Five artifact-loader contract tests pass: valid bundle, checksum failure, missing manifest, and two signature mismatch cases.
- Fourteen M2–M3 API/artifact tests pass in `telco-churn-m2-runtime:local`.
- Clean-container migration from `/code` legacy artifacts loaded through `VerifiedArtifactLoader` without a serving dependency on `handler` or `__main__`.
- Migrated bundle probabilities match the M1/M0 golden candidate within `0.0001`.

## Exit criteria

All M3 exit criteria are met by the verified loader, immutable-manifest guard, failure tests, migration smoke test, and golden prediction comparison.

## Known limitations

Joblib remains a pickle-based format and must only load artifacts from the trusted immutable release directory. Manifest checks detect tampering relative to the trusted manifest; they do not make untrusted Joblib safe.

## Handoff

M4 can add broader test categorisation and coverage without changing the M3 artifact contract.
