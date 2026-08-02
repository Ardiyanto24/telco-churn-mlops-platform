# M11 Staged Release and Rollback Log

## Context dan assumptions

- M11 follows ADR-0007: the permitted target is isolated local/CI
  `production_simulated`, not a public hosted API.
- The available M6 candidate and validated dataset are local, non-secret
  project inputs. No model bundle is committed to Git.

## Plan dan actions

- Added `telco_churn.release_control`: a versioned deployment manifest whose
  identity is `(image_digest, model_manifest_sha256, source_git_sha)`, an
  append-only history, atomic current pointer, and complete-pair rollback.
- Added manifest creation, activation, rollback, and `/health` + `/version`
  verification commands under `scripts/`.
- Added the manual GitHub release-control workflow. Its `production` job must
  be configured with a required ML Engineer reviewer in repository settings.
- Replayed the M8 evaluation of `m6-logistic-v1` against its verified M5
  dataset and recorded an initial-baseline M8 approval locally.

## Evidence dan findings

- `tests.test_release_control`: 3 pass; covers immutable identity, model
  mismatch rejection, and restoration of the previous complete pair.
- `tests.test_ci_workflow` plus release-control tests: 6 pass.
- M8 replay completed with `not_comparable`; an M8 promotion decision was
  created with `initial_baseline: true`. This is offline evidence, not a
  production-performance claim.

## Errors dan handling

- The first M8 replay failed because the existing M6 training record used
  historical flat model parameters (`model.C`) while the current reader
  expected `model.params`. Added a read-only compatibility path and a
  regression test; replay then succeeded.
- A fresh M11 API image build exceeded the local command time budget before
  an image was produced. The existing `m9-local` image cannot be paired with
  the current source SHA without falsifying release identity, so it was not
  used for the M11 staging drill.
- GitHub initially rejected `release.yml` before scheduling jobs because
  expressions were embedded in YAML flow mappings. Converted those mappings
  to block-style `env` entries and quoted expression-bearing scalars; the
  subsequent push created a normal `CI` run instead of a workflow-file run.

## Decisions dan deviations

- The GitHub workflow is intentionally an approval/evidence control plane.
  It does not pretend to deploy a model bundle that GitHub has not been given
  through an authorized artifact store. This implements ADR-0007 rather than
  introducing an unaudited public target.

## Risks, limitations, follow-up

- The final Compose staging and rollback drill remains pending a completed
  current-source image build. M11 cannot be marked `done` until that evidence
  is recorded.
- Configure the GitHub `production` Environment with a required ML Engineer
  reviewer before manually dispatching the release workflow.

## Trace references

- ADR-0007; `src/telco_churn/release_control.py`; `.github/workflows/release.yml`.
- Commands: `scripts/evaluate_candidate.py`, `scripts/approve_candidate.py`,
  `scripts/create_release_manifest.py`, `scripts/activate_release.py`, and
  `scripts/rollback_release.py`.
