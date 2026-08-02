# M10 Continuous Integration Log

## Context dan assumptions

- GitHub Actions is selected by ADR-0006; branch-protection changes require
  repository admin access and are documented rather than claimed as applied.
- CI receives no remote data, credentials, or image-push permission.

## Plan dan actions

- Added CI workflow, synthetic verified bundle generator, workflow contract test,
  and a clean-build correction for the M9 API Dockerfile.

## Evidence dan findings

- Workflow-policy tests pass locally in the locked runtime.
- Synthetic bundle generation succeeds and emits the manifest thresholds needed
  by the Compose smoke test.

## Errors dan handling

- M9 image initially depended on a developer-local M8 image. It was changed to
  install the checked-in runtime lock, allowing clean GitHub runner builds.

## Decisions and deviations

- Implemented ADR-0006. CI uses SHA tags, no image push, and fails closed via
  aggregate required checks.

## Risks, limitations, follow-up

- Remote GitHub execution and branch protection cannot be verified from this
  local workspace; first pull request should confirm action availability/quota.

## Trace references

- ADR-0006; `.github/workflows/ci.yml`; `scripts/create_ci_bundle.py`.
