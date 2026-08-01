"""Minimal, dependency-free helpers for M0 golden-output verification."""

from __future__ import annotations

from numbers import Real
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
