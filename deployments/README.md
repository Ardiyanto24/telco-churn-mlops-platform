# M11 Deployment Manifest History

`history/` is append-only: each accepted release has exactly one JSON manifest,
named `<release-id>.json`. A manifest binds an immutable non-`latest` image tag
and image digest to the checksum, model version, schema, decision settings, and
M8 evidence of one verified M3 bundle.

`current/` is an operational pointer, deliberately excluded from source control.
The M11 local adapter updates it atomically only after bundle validation and
records it in `history/` first. `events/` records rollback actions. Neither
directory contains model artifacts, credentials, customer data, or prediction
payloads.

Create a history record with `scripts/create_release_manifest.py`, then verify
and activate it with `scripts/activate_release.py`. Restore a complete previous
pair with `scripts/rollback_release.py`; never edit a history manifest or
rollback only the image/model.

The GitHub `Release control` workflow records the reviewed manifest and places
the `production-simulated-approval` job behind the repository's `production`
Environment. Configure one ML Engineer as a required reviewer in GitHub before
using it. It is an approval/evidence control plane, not public deployment:
M11 intentionally has no authorized hosted target or credentials.
