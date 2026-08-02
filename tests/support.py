"""Shared fixtures that only allocate test-owned temporary resources."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Iterator


@contextmanager
def temporary_workspace() -> Iterator[Path]:
    """Provide an isolated directory; never point tests at production storage."""
    with tempfile.TemporaryDirectory(prefix="telco-churn-test-") as directory:
        yield Path(directory)
