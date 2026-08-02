# ADR-0005: Adopt M9 container and local-runtime policy v1

## Status

Accepted

## Date

2026-08-02

## Context

M9 must turn the versioned API, verified M3 bundle, and locked M1–M8
dependencies into a reproducible local runtime. It must support a developer
demo and reliable automated verification without implying cloud production
deployment. M11 owns staging/production rollout and rollback; M10 owns CI.

## Decision

M9 implements the following fourteen decisions.

### 1. Base image and Python compatibility

Use the existing locked Python 3.10 Debian-slim lineage until all persisted
artifact manifests and verification images are intentionally migrated. The
runtime Dockerfile must pin its base image by immutable digest in the release
build record. A Python upgrade is a new compatibility decision, not a local
Dockerfile convenience change.

### 2. Dockerfile shape

Use a named multi-stage Dockerfile: `builder` resolves/install dependencies
from the checked-in lock, `runtime` contains only the virtual environment,
application source, and OS runtime libraries. Provide a `test` target only if
it materially reduces duplicated build logic. Build tooling must not remain in
the runtime stage.

### 3. Model artifact delivery

The serving image must not embed a trained model bundle. The default local
Compose stack mounts one explicit, immutable M3 bundle directory read-only at
`/opt/telco-churn/model`. `TELCO_CHURN_BUNDLE_DIR` is required and points to
that mount. Artifact retrieval from remote object storage or MLflow registry is
out of scope until M11; it would add credentials and startup failure modes.

### 4. Registry boundary

The API runs without MLflow. MLflow is an optional `registry` Compose profile
for inspecting M7/M8 lineage, backed by local persistent storage. The serving
API consumes a verified bundle path, never a mutable `champion` alias at
startup. Registry selection and deployment remain separate control planes.

### 5. Compose service topology

Provide a default `api` service and an opt-in `registry` profile. Do not add a
database service in M9: local MLflow may keep its established SQLite metadata
on a named volume. Services share a project-private bridge network; only the
API port is published to the host. Default host binding is `127.0.0.1:8000`.

### 6. Environment configuration

Commit `.env.example`, never `.env`. The example contains safe paths, port,
log level, and image tag only. `TELCO_CHURN_BUNDLE_DIR` has no default in
Compose and fails interpolation if absent; credentials, remote URLs, and
production-like settings are prohibited in M9 configuration. Development and
runtime values live in separate `compose.yaml` and `compose.dev.yaml` files.

### 7. Health and readiness semantics

`/health/live` confirms only that the process is running. `/health/ready`
returns ready only after the M3 verified loader has checked manifest, checksums,
runtime compatibility, feature contract, and a minimal inference path. Compose
uses `/health/ready` as the API healthcheck. Dependent services, if introduced,
must use `depends_on.condition: service_healthy`, never startup order alone.

### 8. Persistent versus ephemeral files

The bundle mount is read-only source evidence; MLflow SQLite and MLflow
artifacts use named volumes when the registry profile is enabled. `/tmp`,
Python bytecode, access logs, and application working files are ephemeral and
must not contain promised metadata. No application writes into the bundle.

### 9. Network and server defaults

Run one Uvicorn worker in the local profile, bind inside the container to
`0.0.0.0:8000`, and publish only localhost as above. Set a 30-second graceful
shutdown timeout and a 60-second request timeout at the future production edge;
M9 itself does not add a reverse proxy or public TLS endpoint.

### 10. Local resource baseline

Document, but do not enforce as a production SLO, a baseline of 1 CPU and
2 GiB RAM for the API container. Compose applies a 2 GiB memory limit and 1 CPU
limit where supported, records cold-start and M0 smoke latency, and treats
measurements as machine-specific local evidence. Worker scaling/load testing is
deferred until production topology exists.

### 11. Image identity and tagging

Every built image receives `telco-churn-api:<git-sha>` and its pushed digest is
recorded in runtime evidence. A human-friendly `local` tag may exist only for
developer convenience; compose documentation must reference the SHA tag or
digest. `latest` is prohibited as an input to verification or promotion.

### 12. Minimum image hardening

Use a non-root `app` user, a restrictive `.dockerignore`, `PYTHONDONTWRITEBYTECODE=1`,
and read-only source/application directories. The Compose API service uses
`read_only: true`, `security_opt: [no-new-privileges:true]`, and a writable
`/tmp` tmpfs unless a dependency proves incompatible. Build context must exclude
data, artifacts, `.env*`, Git metadata, notebooks, test outputs, and secrets.

### 13. Local rollback behaviour

Rollback means changing the pinned image digest/tag and the read-only bundle
path back to a previous verified pair, then running `docker compose up -d`.
Compose must retain the prior named registry volumes and must not mutate either
bundle. Automated production rollback, traffic shifting, and remote artifact
fetch belong to M11.

### 14. Definition of a successful local demo

The documented demo is successful only when a clean-cache build succeeds, the
API becomes ready with a verified bundle, M0 anonymous golden prediction
matches, restart preserves declared registry metadata, an invalid/tampered
bundle stays unready, and image inspection proves prohibited data/secrets are
absent. These are M9 acceptance tests, not production certification.

## Alternatives Considered

### Embed the model in the image

Rejected: it couples application image rebuilds to model promotion, duplicates
large artifacts, and weakens provenance. A read-only verified bundle mount
keeps image and model identities independently auditable.

### Make MLflow mandatory for serving

Rejected: local API startup would depend on registry availability and mutable
alias semantics. M8 intentionally separates approval/registry state from
deployment.

### Use `latest` tags and broad host mounts for convenience

Rejected: both make a supposedly reproducible demo non-reproducible and risk
including source data, credentials, or unintended files in the image/runtime.

### Add Kubernetes or cloud services in M9

Rejected: M9 is a local runtime foundation. Infrastructure rollout belongs to
M11 after CI provides automated checks.

## Consequences

- M9 implementation has clear boundaries: verified local serving first, no
  remote model retrieval or public deployment.
- Developers get a small default stack; lineage inspection remains available
  without coupling it to API availability.
- Future changes to Python, artifact delivery, or image identity must create a
  superseding ADR or versioned migration evidence.

## References

- https://docs.docker.com/build/building/multi-stage/
- https://docs.docker.com/build/building/best-practices/
- https://docs.docker.com/compose/how-tos/startup-order/
- https://docs.docker.com/engine/containers/run/
