# ADR-0006: Adopt M10 continuous-integration policy v1

## Status

Accepted

## Date

2026-08-02

## Context

M0–M9 provide deterministic tests, versioned model gates, and a local serving
runtime. M10 must make those controls automatic for every proposed change while
remaining reproducible, affordable, and unable to access customer data or
deployment credentials.

## Decision

M10 adopts the following seventeen decisions.

### 1. CI platform: GitHub Actions

Use GitHub Actions because checks, pull requests, artifacts, and branch
protection are co-located with the repository and need no separate CI service.

GitLab CI, Jenkins, and hosted third-party CI are not selected: they add either
a hosting migration, operational maintenance, or credentials/billing before the
project needs those capabilities.

### 2. Triggers: PR, main push, and manual dispatch

Run CI for pull requests targeting `main`, pushes to `main`, and
`workflow_dispatch`. This validates proposed changes, records the post-merge
state, and permits controlled reruns.

Scheduled runs are not selected in v1 because there is no external dependency
or production service that needs continuous polling; they would consume
free-tier minutes without a changed input.

### 3. Required checks: four controls plus an aggregate

Require `fast`, `model`, `container-smoke`, and `security`; an aggregate
`required-checks` status is the branch-protection target. The split reflects
independent failure domains and the M4/M8/M9 exit criteria.

A single generic test check is not selected because it hides whether a failure
is code, model contract, runtime, or security related. Optional checks alone
are not selected because M10's purpose is to remove dependence on manual merge
judgment.

### 4. Job topology: parallel, focused jobs

Use four parallel jobs so a fast failure is visible quickly and expensive model
or container work does not obscure its cause. Each job has its own command,
timeout, summary, and artifact set.

One serial all-in-one job is not selected: it delays feedback, spends minutes
after an early failure, and provides poor ownership. A larger micro-job graph is
also not selected because this project has four material control boundaries,
not enough independent work to justify orchestration overhead.

### 5. Runtime: host Python for fast, locked Docker for compatibility

Fast checks use Ubuntu Python 3.10; model/API checks use locked Docker runtimes
to preserve the artifact-compatible Python and dependency lineage.

Host-only CI is not selected because it can silently differ from the pinned
scikit-learn runtime. Docker-only CI is not selected because cheap static tests
would pay container build/startup cost with no extra confidence.

### 6. Docker build: BuildKit cache, SHA tag, no push

Build with BuildKit cache keyed by Dockerfile and lockfile inputs and tag every
CI image with the commit SHA. Inspect it and use it for smoke tests, but do not
push it.

`latest` and mutable PR tags are not selected because they cannot reproduce an
image. Pushing every PR image is not selected because M10 validates changes; it
does not yet authorize release, registry credentials, or retention cost.

### 7. Smoke artifact: generated synthetic verified bundle

Generate a small synthetic M3-compatible bundle during the workflow/test setup.
It exercises the verified-loader and serving contract without remote services.

Downloading a real dataset/model is not selected because it introduces data,
privacy, credentials, cost, and availability dependencies. Committing a
dedicated serving bundle is not selected because it risks stale binary artifacts
and unnecessary repository growth.

### 8. Test matrix: Ubuntu and Python 3.10 only

Use one supported Linux runner and Python 3.10, matching the locked artifact
runtime and M9 container lineage.

A multi-OS or multi-Python matrix is not selected before those platforms are
deployment targets; it would multiply CI time yet cannot certify serialized
artifact compatibility outside the supported runtime.

### 9. Negative controls: prove critical controls fail closed

Explicitly verify an invalid artifact/readiness failure, an M8 gate failure,
and an intentional failing unittest command. The CI job passes only when each
negative command fails for the expected reason.

Only positive tests are not selected because they cannot show that guards block
bad input. Intentionally leaving a workflow red is not selected because a
negative control is evidence only when its expected failure is handled and the
workflow itself reports success.

### 10. Security gates: secrets mandatory; triaged vulnerabilities

Secret detection always blocks. Dependency and container scans block reachable
critical/high findings; SBOM generation is informational and uploaded.

No security scan is not selected because CI would miss a basic release gate.
Blocking every informational/low finding is not selected because untriaged
noise produces alert fatigue and weakens attention to material issues.

### 11. Cache: immutable-input keyed downloads/layers only

Cache pip downloads and BuildKit layers using lockfile/Dockerfile hashes. Never
cache virtual environments, datasets, artifacts, or model bundles.

Unkeyed broad caches are not selected because they can hide dependency drift.
No cache is not selected because repeated locked dependency and Docker work
would needlessly consume CI minutes without increasing reproducibility.

### 12. Timeouts, retries, and concurrency

Use PR/ref concurrency with `cancel-in-progress: true`; fast/security jobs get
10 minutes and model/container jobs get 20 minutes. Do not automatically retry
test failures; maintainers may rerun identified platform failures.

Unlimited jobs are not selected because hung Docker/build commands consume
quota. Automatic retries are not selected because they can mask flaky tests;
blindly retaining superseded PR runs is not selected because their result is no
longer relevant.

### 13. Artifact retention: bounded diagnostic evidence

Retain PR logs, JUnit/coverage, scan reports, and image metadata for 14 days;
retain successful `main` evidence for 30 days. Do not upload model or data
payloads.

Indefinite retention is not selected because it consumes limited storage and
retains stale diagnostics. No artifact retention is not selected because it
makes failures impossible to investigate after a runner is gone.

### 14. Branch protection: review plus required CI

Protect `main` with the aggregate required check, one approving review, and
stale-approval dismissal after new commits. Admin bypass is exceptional and
must be auditable.

CI-only merge is not selected because model changes still require accountable
human review. Unprotected main is not selected because it permits bypassing all
M10 controls. If repository permissions are unavailable, M10 documents this
policy rather than claiming the setting was applied.

### 15. Permissions and external access: least privilege

Set workflow permissions to `contents: read`; M10 uses no cloud credentials,
package publishing rights, registry push token, remote data remote, or
deployment secret.

Write-all default tokens are not selected because a test workflow should not
mutate repository or release state. Remote data/registry access is not selected
because it would make CI non-deterministic and expand its credential boundary.

### 16. CI observability: structured job summaries

Each job writes a GitHub Actions summary with command, duration, image SHA, and
artifact links; failures are classified as test/code, build, scan, or runner
infrastructure failure.

Raw console output alone is not selected because it is difficult to scan and
does not preserve the key release evidence. An external observability platform
is not selected because M10 does not need production-scale telemetry.

### 17. Passing CI definition: complete evidence, not just green tests

A passing run requires all required jobs green, a SHA-tagged image built,
Compose ready with a synthetic verified bundle, negative controls observed, no
blocking security finding, and diagnostic artifacts retained.

“Unit tests passed” alone is not selected because it omits model gates,
container readiness, security, and reproducibility. A successful image build
alone is not selected because it does not prove the image can serve a verified
model.

## Consequences

- M10 provides repeatable merge evidence without creating a release or
  deployment mechanism.
- CI costs are bounded by parallel targeted jobs, cancellation, caching, and
  short retention; no customer data or deployment credential enters CI.
- M11 may add release credentials or image publishing only through a new,
  explicitly reviewed policy.

## References

- https://docs.github.com/actions
- https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
- https://docs.github.com/actions/using-workflows/caching-dependencies-to-speed-up-workflows
