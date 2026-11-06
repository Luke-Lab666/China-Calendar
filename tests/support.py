"""Shared fixtures that keep tests independent of the live, auto-updated data.

The daily workflow adds new official holiday schedules (for example a new
year's notice each November) and then runs this suite. Tests that describe
"a year whose schedule is not published yet" therefore run against a copy of
the repository frozen at the 2026-10-21 snapshot instead of the live files.
"""
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PUBLISHED_THROUGH = 2026


@contextmanager
def snapshot_root(published_through: int = SNAPSHOT_PUBLISHED_THROUGH) -> Iterator[Path]:
    """A temporary repository copy without holiday notices after ``published_through``."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for folder in ("data", "config", "china_calendar"):
            shutil.copytree(ROOT / folder, root / folder)
        for path in (root / "data" / "holidays").glob("*.json"):
            if int(path.stem) > published_through:
                path.unlink()
        yield root
