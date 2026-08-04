# Portfolio workflow and design decisions

## Purpose

This is the presentation layer for the Telco Customer Churn MLOps Platform. It
explains the engineering problem, the workflow used to solve it, and the
trade-offs behind the implementation. Detailed evidence remains in the
milestone reports, logs, and ADRs.

## 1. Preserve behaviour before modernising it

The project began with a legacy Telco Churn inference endpoint and serialized
model artifacts. It could make predictions, but did not provide reproducible
training, data lineage, controlled release, monitoring, or a safe public
presentation boundary.

M0 treats the legacy runtime as a **behaviour oracle**. Anonymous fixtures and
expected outputs were frozen before creating the new package.

**Decision:** preserve the baseline before refactoring.

**Why:** a new architecture is not an improvement if it silently changes a
previously accepted inference path. Golden comparisons make deviations explicit
and reviewable.

## 2. Build a reproducible training-to-serving chain

M1–M8 establish the ML lifecycle:

1. Package settings provide one source of truth for thresholds and risk bands.
2. Versioned request/response schemas make inference a stable API contract.
3. Immutable bundles bind model, preprocessor, schema, threshold, and metadata.
4. A data contract and DVC lineage make training inputs inspectable.
5. Config-driven training and MLflow make candidates reproducible and comparable.
6. Evaluation gates, model cards, and approval protect promotion.

**Decision:** release immutable bundles, not standalone model files.

**Why:** serving depends on preprocessing, schema, and decision policy as much
as estimator weights. Bundling and integrity checks prevent incompatible
components from being deployed together.

## 3. Separate model selection from model release

Training may explore model families and parameters, but serving loads only one
approved immutable bundle. Evaluation evidence and approval determine whether a
candidate advances; a release manifest enables rollback.

**Decision:** promote a candidate rather than overwrite a “latest” artifact.

**Why:** it maintains a clear path from data/configuration to deployment and
keeps the prior known-good release available after a failed rollout.

## 4. Make local verification a deployment target

Pinned dependencies, Docker images, Compose definitions, and GitHub Actions
checks make the local container a reproducible demonstration environment—not
just a developer convenience.

**Decision:** local-first, cloud-optional delivery.

**Why:** the portfolio remains inspectable without paid infrastructure or
undocumented cloud state. Hosting can be added later without becoming a hidden
requirement for demonstrating the lifecycle.

## 5. Treat monitoring signals honestly

M12–M17 add privacy-minimised telemetry, reference baselines, statistical
data-quality/drift monitoring, delayed-label performance evaluation, and alert
recommendations. The signals are intentionally distinct:

| Signal | It can show | It cannot prove alone |
| --- | --- | --- |
| Data quality | Whether input violates expectations | Whether model accuracy fell |
| Data/prediction drift | Whether distributions shifted from a baseline | Whether the model is wrong |
| Service health | Whether serving/monitoring works | Whether predictions are useful |
| Delayed-label performance | Whether mature outcomes support a metric claim | Anything before labels mature |

**Decision:** drift triggers investigation, not automatic promotion.

**Why:** population shifts may be benign and churn outcomes arrive later.
Retraining can be recommended, but promotion remains gated and approved.

## 6. Separate internal observability from public evidence

M18 stores and renders aggregate internal evidence. M19 exports a sanitized,
immutable snapshot for a separate public dashboard. The browser uses a small,
GET-only API and never accesses the internal store.

**Decision:** publish snapshot-based public metrics through an allowlist.

**Why:** this prevents future internal fields from becoming public by accident,
supports caching/auditability, and makes privacy controls testable. Small
groups are suppressed, while provenance and freshness keep demo/replayed data
from masquerading as production health.

## 7. What remains

### M20 — Security and privacy hardening

M20 will audit secrets, dependencies, images, permissions, CORS, public data
exposure, redaction, artifact-tamper behaviour, and retention. It also adds a
threat model and accepted-risk register.

### M21 — Operational readiness and end-to-end audit

M21 will prove a repeatable lifecycle: versioned data → candidate training →
evaluation/promotion → serving telemetry → monitoring/alert → public snapshot
→ rollback. It will reconcile the final architecture and model documentation
with the actual implementation.

## Evidence map

| Need | Location |
| --- | --- |
| Roadmap and acceptance criteria | `MLOPS_IMPLEMENTATION_PLAN.md` |
| Architecture and principles | `MLOPS_END_TO_END_DESIGN.md` |
| Durable decision rationale | `docs/decisions/` |
| Completed-milestone evidence | `docs/milestones/` |
| Chronological implementation evidence | `docs/logs/` |
| Test and local runtime instructions | `docs/testing.md`, `docs/m9-local-runtime.md` |

## Claim boundary

The repository demonstrates the design and local verification of an MLOps
lifecycle. Until M20 and M21 are complete, it does not claim a full security
sign-off or end-to-end operational certification. Non-production data origin
is intentionally disclosed in public-facing evidence.
