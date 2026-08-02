# ADR-0007: Adopt M11 staged release and rollback policy v1

## Status

Accepted

## Date

2026-08-02

## Context

M8 approves an offline model candidate, M9 provides a reproducible local API,
and M10 provides CI evidence. M11 must connect these controls into an auditable
release process without treating a mutable registry alias or a successful build
as a deployment. No paid cloud account, deployment credentials, or production
endpoint has been authorized yet.

## Decision

M11 adopts the following nineteen decisions.

### 1. Deployment platform: GitHub Actions control plane with container target adapter

Use GitHub Actions deployment workflows and environment protection as the
control plane. Implement a local/ephemeral Compose target adapter first; a
future hosted container target is an explicit adapter, not a rewrite.

Kubernetes is not selected because this portfolio project has no cluster or
operational need. Direct shell deployment from developer machines is not
selected because it bypasses CI evidence and audit history.

### 2. Production scope: release simulation until hosting authority exists

M11 validates the full staging→approval→production-manifest→rollback sequence
against isolated local/CI targets, labelled `production_simulated`. A public
production endpoint is not claimed or created without provider, billing, DNS,
and secret authority.

Deploying an unaudited free-tier service is not selected because it confuses a
demo with production and expands security exposure. Skipping production flow
entirely is not selected because manifests and rollback require an end-to-end
control-plane drill.

### 3. Model delivery: immutable verified bundle paired with release

Deploy a read-only M3 bundle identified by manifest checksum alongside each
release manifest. The target fetches/mounts only that explicit bundle.

A mutable MLflow alias is not selected as a serving input because it can change
without a corresponding image release. Baking the bundle into every image is
not selected because it couples model promotion to image rebuild and duplicates
artifact identity.

### 4. Image registry: GitHub Container Registry when publishing is authorized

Use GHCR with immutable digest references for hosted release publishing. Until
registry write permission is explicitly granted, M11 validates local SHA-tagged
images and records their digest.

Docker Hub is not selected because it adds another account, quota, and access
boundary. A provider-specific registry is deferred because no provider has been
selected.

### 5. Manifest: versioned signed-content JSON in Git and release evidence

Use one versioned JSON deployment manifest containing image digest/SHA, model
manifest SHA, model version, schema, threshold, source Git SHA, evaluation
report digest, environment, and creation time. Commit manifests and attach the
exact released copy to workflow evidence.

Database-only history is not selected because Git review/history is needed
before deployment. Image tag alone is not selected because it cannot prove the
paired model or evaluation evidence.

### 6. Release identity: image digest plus model checksum plus source SHA

Treat `(image_digest, model_manifest_sha256, source_git_sha)` as the immutable
release identity; a human-readable release ID is derived from those values.

`latest`, branch names, or model version alone are not selected because each is
mutable or incomplete. A timestamp-only ID is not selected because it cannot
reconstruct content.

### 7. Staging environment: isolated, ephemeral release instance

Create an isolated staging Compose project per release attempt with its own
name, ports, temporary state, and read-only bundle. Destroy it after evidence
collection.

A shared mutable staging environment is not selected because releases can
interfere and its state obscures causality. Per-PR public environments are not
selected because M11 has no public-hosting requirement.

### 8. Staging eligibility: M8 passed or approved baseline only

Allow a candidate into staging only when its M8 report is `passed`, or when an
explicit `not_comparable` initial-baseline approval exists. The release workflow
verifies the decision/report digest before staging.

Training success alone is not selected because it bypasses M8 quality gates.
Requiring a production approval before staging is not selected because staging
is the evidence step needed for informed approval.

### 9. Production approval: GitHub Environment reviewer plus approval artifact

Require both the immutable M8 promotion decision and a GitHub `production`
Environment reviewer before production-simulated promotion. The workflow records
the approving actor and manifest digest.

Automatic promotion after staging is not selected because gates are evidence,
not accountable release authorization. A free-form chat/manual note is not
selected because it is not bound to immutable release content.

### 10. Staging acceptance: hard service and behavior checks

Require liveness, readiness, `/version` manifest equality, M2 contract tests,
M0 anonymous golden prediction comparison, image/model compatibility, and a
bounded latency smoke check.

Health-only checks are not selected because a process may be healthy while
serving the wrong model. Full load testing is not selected because M11 has no
production traffic baseline; it belongs to later operational readiness work.

### 11. Post-deploy policy: automatic hard rollback recommendation

Readiness, contract, golden, or manifest mismatch is a hard failure: production
promotion stops and the workflow automatically restores the previous manifest
when a previous target exists. Latency-only degradation produces a blocked
release and explicit rollback recommendation pending review.

Ignoring post-deploy checks is not selected because it defeats staged release.
Blind rollback for every warning is not selected because transient host noise
could create unnecessary churn.

### 12. Rollback unit: the complete release manifest pair

Rollback always restores the previous image and verified model bundle together
from the recorded manifest. It never retrains, edits artifacts, or changes only
one side of the pair.

Image-only or model-only rollback is not selected because compatibility and
threshold/schema behavior can diverge. Retraining during rollback is not
selected because recovery must be fast and reproducible.

### 13. Deployment history: append-only manifest directory and workflow record

Store accepted manifests in an append-only `deployments/` history and retain
workflow logs/evidence. Superseding a release creates a new manifest; old
manifests remain readable for audit and rollback.

Overwriting one current-production file is not selected because it destroys
rollback evidence. Ephemeral workflow logs alone are not selected because their
retention is bounded and they are not reviewed source artifacts.

### 14. Identity and secrets: OIDC preferred, scoped environment secret fallback

For a future hosted target, use GitHub OIDC short-lived credentials with
environment-scoped policy. If the provider lacks OIDC, use a minimum-permission
GitHub Environment secret and document rotation/owner.

Long-lived broad repository secrets are not selected because they are harder to
rotate and expose every workflow. Developer-machine credentials are not selected
because they are not auditable or reproducible.

### 15. Network exposure: staging private; public release deferred

Keep staging localhost/private to the runner. A future public production API
must terminate TLS, restrict origins/ingress, and pass M20 security hardening;
M11 does not expose a public endpoint by default.

Public staging is not selected because it unnecessarily exposes an unapproved
candidate. Plain HTTP public serving is not selected because TLS is mandatory
for an internet-facing prediction API.

### 16. Persistent state: external only for promised history and artifacts

Deployment manifests, artifact storage, and any registry metadata promised for
rollback must be Git/versioned storage or provider persistence; container
filesystems are disposable. Staging temporary files are explicitly ephemeral.

Container-local persistence is not selected because replacement/restart loses
the very evidence needed for rollback. Persisting raw prediction payloads is not
selected because telemetry minimization is an M12 policy concern.

### 17. Failure ownership and runbook: ML Engineer controls release

An ML Engineer approves promotion and can execute/recommend rollback; CI creates
evidence but never invents a waiver. Each failed deployment records the manifest,
check, time, operator, action, and follow-up in the release log/runbook.

Unowned automatic operations are not selected because operational accountability
would be unclear. Ad-hoc recovery without a recorded decision is not selected
because it makes audit and incident learning impossible.

### 18. Cost and quota: ephemeral staging, no always-on paid dependency

Use GitHub Actions runners and local/ephemeral Compose staging; build/publish
only approved release candidates. Record runner minutes, image size, and
artifact retention; do not require an always-on paid service in M11.

Always-on staging is not selected because it incurs cost without traffic. A
free-tier public host is not selected before its sleep, storage, and security
limits are evaluated against the release policy.

### 19. Release success: manifest, evidence, approval, and rollback drill

A release succeeds only if the manifest is internally consistent, staging hard
checks pass, approvals are recorded, production-simulated `/version` matches,
post-deploy checks pass, and a rollback drill restores the prior manifest and
golden behavior.

“Image deployed” is not selected as success because it omits model pairing and
behavior. “Approval received” alone is not selected because approval cannot
replace technical evidence or rollback proof.

## Consequences

- M11 creates a deployable, auditable release-control plane without making an
  unsupported claim of public production hosting.
- Every serving change is a reversible image–model pair, not a mutable alias.
- A later hosted deployment requires a provider-specific ADR/addendum and
  explicit credentials/billing authority, while preserving these invariants.

## References

- https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment
- https://docs.github.com/actions/security-for-github-actions/security-guides/about-security-hardening-with-openid-connect
- https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
