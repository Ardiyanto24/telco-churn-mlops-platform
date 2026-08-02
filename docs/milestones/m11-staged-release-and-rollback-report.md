# Milestone M11 Completion Report

Status: blocked
Tanggal: 2026-08-02

## Deliverable

- Immutable deployment-manifest and append-only release history control.
- Atomic complete-pair activation/rollback commands and service-version
  verification command.
- Manual GitHub staging/production-simulated approval workflow and deployment
  history documentation.

## Test evidence

- `python -m unittest tests.test_release_control -v`: 3 pass.
- `python -m unittest tests.test_ci_workflow tests.test_release_control -v`: 6 pass.
- M8 replay for `m6-logistic-v1`: `not_comparable`, then explicit approved
  initial-baseline decision. This is offline release eligibility evidence.

## Exit criteria

- [x] Production-simulated promotion has immutable manifest and approval gate.
- [x] Model/image pairing and mismatch rejection are tested.
- [x] Rollback logic restores a previous whole release pair without retraining.
- [x] Deployment history is append-only and auditable.
- [ ] Fresh-image Compose staging and rollback drill is still required.

## Decisions made

- ADR-0007.

## Known limitations

- No hosted target, provider credentials, billing authority, or public API
  exposure is authorized; M11 is explicitly `production_simulated`.
- The local fresh image build did not finish inside this execution window, so
  no false staging-success claim is made.

## Handoff

- Complete the current-source image build, create a manifest using its real
  digest, run staging verification, then exercise rollback with a prior
  manifest before changing this status to `done`.
