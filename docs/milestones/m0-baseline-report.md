# M0 Baseline Compatibility Report

## Status

Verified on 2026-08-01. M0 establishes an observational regression baseline for the legacy deployment; it does not certify a fully reproduced training environment.

## Environment captured

| Item | Value |
|---|---|
| Docker image | `telco-churn-baseline:local` |
| Image ID | `sha256:4a1da82f4e0aaf7b1a23f5cda4afda72e503199a034c7d22158775caf5d33d71` |
| Python | `3.10.20` |
| scikit-learn | `1.7.2` |
| LightGBM | `4.7.0` |
| XGBoost | `3.2.0` |
| pandas | `2.3.3` |
| NumPy | `2.2.6` |
| FastAPI | `0.141.1` |
| Joblib | `1.5.3` |

## Artifact identity

| Artifact | SHA-256 |
|---|---|
| `model_final.joblib` | `a59f87cdf6a1270dffa1e011da03547ed8663f26fed5fc2aabd2a1fd1adc08c8` |
| `preprocessor.joblib` | `07cd2d7aaa0a2d8f60a4cc257d8145d2dd67a34c7c9a0c72813469aaab0c7ec2` |

## Golden scenarios

| Scenario | Expected behavior | Evidence |
|---|---|---|
| `single_standard` | One successful prediction | One result, 29 transformed features |
| `boundary_zero_tenure` | Zero-tenure input remains processable | One result, 29 transformed features |
| `batch_customers` | Batch preserves one output per customer | Two results, 29 transformed features per input frame |
| `dict_of_lists` | Alternate payload form is accepted | One result, 29 transformed features |
| `invalid_empty_inputs` | Legacy rejects empty dataframe | `status: error`, no processed features |

The complete expected response, including probabilities and risk labels, is stored in `baseline/expected/legacy_snapshot.json`. Numeric values are compared using absolute tolerance `0.0001`.

## Commands executed

```powershell
python -m unittest tests.test_baseline_runner
python baseline/runner.py --capture
python baseline/runner.py --verify
```

The suite contains six tests: snapshot comparison, fixture contract, Docker command hardening, and end-to-end capture of the legacy image.

## Known risks and required follow-up

1. The Joblib artifacts were serialized with scikit-learn `1.6.1`, while the unpinned legacy requirements resolved to `1.7.2` during capture. Six `InconsistentVersionWarning` warnings were captured: OneHotEncoder, StandardScaler, three LabelEncoder instances, and VotingClassifier.
2. The unpinned requirements also resolved to current versions of all major libraries. Rebuilding the image at a later time can change the runtime and therefore needs a new recorded image digest and verification.
3. The legacy Docker image includes the copied source/artifacts at build time. The snapshot proves that image, not an arbitrary future checkout of `legacy-deployment`.
4. API error semantics are only documented here; M0 does not fix them. The empty-input behavior is intentionally preserved as evidence for M1/M2.

## Exit criteria mapping

| M0 exit criterion | Evidence |
|---|---|
| Golden dataset/output readable by test runner | `baseline/fixtures/golden_inputs.json`, `baseline/expected/legacy_snapshot.json`, `baseline/runner.py --verify` |
| No customer data or secret in fixture | Anonymized `BASELINE-*` IDs plus fixture contract test |
| Baseline runs from documented clean environment | Dockerfile-derived image, documented at `baseline/README.md` |
| Future predictions can be compared | Versioned snapshot, feature metadata, checksums, and tolerance-aware verifier |
