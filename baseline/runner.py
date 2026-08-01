"""Minimal, dependency-free helpers for M0 golden-output verification."""

from __future__ import annotations

import json
from numbers import Real
from pathlib import Path
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
