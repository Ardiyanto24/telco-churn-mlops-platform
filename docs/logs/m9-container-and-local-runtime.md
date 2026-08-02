# M9 Container and Local Runtime Log

## Context dan assumptions

- M9 implements ADR-0005 only: local verified serving, not cloud deployment.
- M6 bundle is mounted read-only; image contains application/runtime only.

## Plan dan actions

- Added multistage API image, Compose default/registry profile, hardening, and
  separate development override.
- Added bundle-directory and threshold/risk-band runtime settings and policy tests.

## Evidence dan findings

- Compose config resolves the M6 bundle as a read-only mount and localhost port.
- The built API reached `/health/ready` with the exact M6 manifest values.

## Errors dan handling

- Initial clean dependency build exceeded command time; final image reuses the
  already locked M8 runtime rather than resolving dependencies again.
- Initial readiness correctly stayed unavailable because default settings did
  not match the mounted bundle threshold/risk bands. Added validated runtime
  overrides; the image still embeds no model settings.
- The baseline Docker-in-Docker integration test cannot run inside the locked
  M8 test container because it has no Docker binary; M9 Compose smoke was run
  directly through the host Docker daemon instead.

## Decisions dan deviations

- Implemented ADR-0005. The `builder` and `runtime` stages inherit M8's locked
  Python 3.10 runtime, preserving artifact compatibility.

## Risks, limitations, follow-up

- Local measurements are not production SLOs. M10 will automate image and
  Compose verification; M11 owns deployment and remote artifact delivery.

## Trace references

- ADR-0005; `docker/api.Dockerfile`; `compose.yaml`.
