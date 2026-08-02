# ADR-0006: Adopt M10 continuous-integration policy v1

## Status

Accepted

## Date

2026-08-02

## Context

M0–M9 supply deterministic tests, versioned model gates, and a local serving
runtime. M10 must make those controls automatic for every proposed change while
remaining affordable, reproducible, and unable to access customer data or
deployment credentials.

## Decision

M10 adopts these seventeen decisions.

### 1. Platform

Use GitHub Actions. It is native to the repository hosting workflow and keeps
pull-request checks, artifacts, and branch-protection status in one system.

### 2. Triggers

Run on pull requests to `main`, pushes to `main`, and `workflow_dispatch`.
No scheduled heavy run is added until cost/need is demonstrated.

### 3. Required checks

Require `fast`, `model`, `container-smoke`, and `security` before merge. A
failed check blocks merge; manual local evidence cannot waive it.

### 4. Job topology

Use four independently diagnosable parallel jobs: fast checks, locked model
suite, container/Compose smoke, and security. A final `required-checks` job
reports the combined result for branch protection.

### 5. Runtime strategy

Fast checks run on Ubuntu Python 3.10. Model and API tests build/use the locked
Docker runtime so artifact compatibility is tested on the same Python lineage.

### 6. Docker build strategy

Use BuildKit GitHub Actions cache keyed by Dockerfile and lockfile inputs. Tag
CI images with the commit SHA; build and inspect only—M10 never pushes images.

### 7. Smoke-test model artifact

Create a small synthetic verified M3 bundle during the workflow or test setup.
Never download remote data or commit a serving model solely for CI smoke tests.

### 8. Test matrix

Use Ubuntu and Python 3.10 only. A cross-version/OS matrix would not validate
the locked artifact contract and would consume free-tier minutes without a
supported deployment target.

### 9. Negative controls

Run explicit tests for an invalid artifact/readiness failure, a failed M8 gate,
and an intentional failing unittest command. The workflow passes only when each
negative control fails as expected.

### 10. Security controls

Run secret detection and dependency/container vulnerability scans. Secrets are
always blocking. Reachable critical/high findings block; SBOM generation starts
informational and is uploaded as an artifact.

### 11. Cache policy

Cache pip downloads and BuildKit layers using hashes of the lockfiles and
Dockerfiles. Do not cache mutable virtual environments, artifacts, datasets, or
model bundles.

### 12. Timeout, retry, and concurrency

Use `concurrency` keyed by workflow plus PR/ref with `cancel-in-progress: true`.
Set 10 minutes for fast/security and 20 minutes for model/container jobs. Do
not automatically retry test failures; rerun only platform failures manually.

### 13. Artifact retention

Keep PR logs, JUnit/coverage, scan reports, and image metadata for 14 days;
keep successful `main` evidence for 30 days. Do not upload model/data payloads.

### 14. Branch protection

Require the combined check and one approving review on `main`; dismiss stale
approvals after new commits. Admin bypass is exceptional and must be auditable.
The workflow documents this policy if repository permissions cannot set it.

### 15. Permissions and external access

Set workflow `permissions: contents: read`. Use no cloud credentials, package
publish permissions, registry push token, remote data remote, or deployment
secret in M10.

### 16. CI observability

Every job writes a GitHub Actions summary with command, duration, image SHA,
and artifact links. Reports distinguish test/code failure from build or runner
infrastructure failure.

### 17. Definition of a passing CI run

A passing run has all required jobs green, a SHA-tagged image built, Compose
ready against a synthetic verified bundle, negative controls observed, no
blocking security finding, and retained diagnostic artifacts.

## Alternatives Considered

### One serial all-in-one job

Rejected: it delays feedback, wastes minutes after an early failure, and makes
failure ownership unclear.

### Push every PR image or use production credentials

Rejected: M10 validates code, not releases. Least privilege prevents CI from
becoming a deployment path.

### Download the real dataset/model in CI

Rejected: it creates secret, cost, availability, and privacy dependencies. A
synthetic bundle tests the serving contract without those risks.

### Treat all security findings as blocking immediately

Rejected: untriaged informational/low findings create noise. Secrets and
critical/high reachable findings remain hard gates; SBOM starts informational.

## Consequences

- M10 will provide repeatable evidence for merge decisions without creating a
  release or deployment mechanism.
- CI cost is controlled by parallel targeted jobs, cancellation, limited
  retention, and no remote data transfers.
- M11 can add release credentials and image publishing only through a new,
  explicitly reviewed policy.

## References

- https://docs.github.com/actions
- https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
- https://docs.github.com/actions/using-workflows/caching-dependencies-to-speed-up-workflows
