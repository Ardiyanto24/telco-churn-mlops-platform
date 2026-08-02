"""Verify M11 liveness, readiness, and served model version against a release manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from telco_churn.release_control import ReleaseControlError, ReleaseManifest  # noqa: E402


def verify(base_url: str, release: ReleaseManifest, timeout_seconds: float) -> None:
    base = base_url.rstrip("/")
    for endpoint in ("/health/live", "/health/ready"):
        payload = _get_json(base + endpoint, timeout_seconds)
        if payload != {"status": "ok"}:
            raise ReleaseControlError(f"{endpoint} returned an unexpected health payload")
    version = _get_json(base + "/version", timeout_seconds)
    if version.get("model_version") != release.model_version:
        raise ReleaseControlError("served model version does not match release")
    if version.get("schema_version") != release.schema_version:
        raise ReleaseControlError("served schema version does not match release")


def _get_json(url: str, timeout_seconds: float) -> dict[str, object]:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310 - localhost/release target supplied by operator
            if response.status != 200:
                raise ReleaseControlError(f"release check returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as error:
        raise ReleaseControlError(f"release endpoint is unavailable: {url}") from error
    if not isinstance(payload, dict):
        raise ReleaseControlError("release endpoint returned a non-object JSON payload")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("timeout must be positive")
    release = ReleaseManifest.from_dict(json.loads(args.manifest.read_text(encoding="utf-8")))
    verify(args.base_url, release, args.timeout_seconds)
    print(json.dumps({"release_id": release.release_id, "status": "verified"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
