"""Minimal, dependency-free helpers for M0 golden-output verification."""

from __future__ import annotations

import json
import argparse
from numbers import Real
from pathlib import Path
import subprocess
from typing import Any


def compare_snapshots(
    actual: Any,
    expected: Any,
    *,
    tolerance: float = 0.0001,
    path: str = "$",
) -> list[str]:
    """Return human-readable differences between two JSON-compatible values."""
    if isinstance(expected, Real) and not isinstance(expected, bool):
        if not isinstance(actual, Real) or isinstance(actual, bool):
            return [f"{path}: expected number {expected!r}, got {actual!r}"]
        if abs(float(actual) - float(expected)) > tolerance:
            return [
                f"{path}: expected {expected!r} ± {tolerance}, got {actual!r}"
            ]
        return []

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]

        mismatches: list[str] = []
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            missing = sorted(expected_keys - actual_keys)
            unexpected = sorted(actual_keys - expected_keys)
            if missing:
                mismatches.append(f"{path}: missing keys {missing}")
            if unexpected:
                mismatches.append(f"{path}: unexpected keys {unexpected}")

        for key in sorted(expected_keys & actual_keys):
            mismatches.extend(
                compare_snapshots(
                    actual[key],
                    expected[key],
                    tolerance=tolerance,
                    path=f"{path}.{key}",
                )
            )
        return mismatches

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected array, got {type(actual).__name__}"]

        mismatches = []
        if len(actual) != len(expected):
            mismatches.append(
                f"{path}: expected {len(expected)} items, got {len(actual)}"
            )
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            mismatches.extend(
                compare_snapshots(
                    actual_item,
                    expected_item,
                    tolerance=tolerance,
                    path=f"{path}[{index}]",
                )
            )
        return mismatches

    if actual != expected:
        return [f"{path}: expected {expected!r}, got {actual!r}"]
    return []


def load_fixture(path: Path) -> dict[str, Any]:
    """Load the versioned M0 fixture and reject ambiguous scenario definitions."""
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != 1:
        raise ValueError("fixture schema_version must be 1")

    scenarios = fixture.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("fixture must contain at least one scenario")

    names: list[str] = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("each scenario must be an object")
        name = scenario.get("name")
        payload = scenario.get("payload")
        if not isinstance(name, str) or not name:
            raise ValueError("each scenario must have a non-empty name")
        if not isinstance(payload, dict) or "inputs" not in payload:
            raise ValueError("each scenario must contain a payload with inputs")
        names.append(name)

    if len(names) != len(set(names)):
        raise ValueError("scenario names must be unique")
    return fixture


def build_capture_command(image: str, baseline_dir: Path) -> list[str]:
    """Build a read-only Docker command that executes the legacy capture script."""
    mount = f"type=bind,source={baseline_dir.resolve()},target=/baseline,readonly"
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "--mount",
        mount,
        "--workdir",
        "/code",
        "--entrypoint",
        "python",
        image,
        "/baseline/container_capture.py",
    ]


def capture_snapshot(
    *, image: str, baseline_dir: Path, fixture: dict[str, Any]
) -> dict[str, Any]:
    """Run the legacy handler in Docker and parse its JSON-only snapshot output."""
    result = subprocess.run(
        build_capture_command(image, baseline_dir),
        input=json.dumps(fixture),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "baseline container failed "
            f"with exit code {result.returncode}: {result.stderr.strip()}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "baseline container did not return valid JSON: "
            f"{result.stdout!r}; stderr: {result.stderr.strip()}"
        ) from error


def _default_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent.joinpath(*parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture or verify the legacy Docker baseline.")
    parser.add_argument("--image", default="telco-churn-baseline:local")
    parser.add_argument("--fixture", type=Path, default=_default_path("fixtures", "golden_inputs.json"))
    parser.add_argument("--snapshot", type=Path, default=_default_path("expected", "legacy_snapshot.json"))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--capture", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    actual = capture_snapshot(
        image=args.image,
        baseline_dir=Path(__file__).resolve().parent,
        fixture=fixture,
    )

    if args.capture:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(
            json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Captured baseline snapshot: {args.snapshot}")
        return 0

    expected = json.loads(args.snapshot.read_text(encoding="utf-8"))
    mismatches = compare_snapshots(actual, expected)
    if mismatches:
        print("Baseline verification failed:")
        print("\n".join(f"- {mismatch}" for mismatch in mismatches))
        return 1

    print(f"Baseline verification passed: {args.snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
