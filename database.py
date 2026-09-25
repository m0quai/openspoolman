"""Central connection and file migration for the OpenSpoolMan database."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from config import DATABASE_NAME, DATABASE_PATH, DATABASE_PATH_OVERRIDE, DATABASE_TYPE


LEGACY_DATABASE_NAME = "3d_printer_logs.db"


def _migrate_legacy_database_file(target_path: Path) -> None:
    default_target = Path(__file__).resolve().parent / "data" / DATABASE_NAME
    if (
        DATABASE_PATH_OVERRIDE
        or DATABASE_NAME != "osm.db"
        or target_path.resolve() != default_target.resolve()
        or target_path.exists()
    ):
        return

    legacy_path = target_path.with_name(LEGACY_DATABASE_NAME)
    if not legacy_path.exists():
        return

    # A previous process must be stopped before this runs. Move SQLite sidecars
    # first so a database left in WAL/journal mode remains consistent.
    moved: list[tuple[Path, Path]] = []
    try:
        for suffix in ("-wal", "-shm", "-journal"):
            source = Path(f"{legacy_path}{suffix}")
            destination = Path(f"{target_path}{suffix}")
            if source.exists():
                if destination.exists():
                    raise FileExistsError(f"Database migration target already exists: {destination}")
                os.replace(source, destination)
                moved.append((source, destination))
        os.replace(legacy_path, target_path)
        moved.append((legacy_path, target_path))
    except Exception:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                os.replace(destination, source)
        raise


def connect_database(path: str | Path | None = None) -> sqlite3.Connection:
    if DATABASE_TYPE != "sqlite":
        raise RuntimeError(
            f"Unsupported OpenSpoolMan database type: {DATABASE_TYPE!r}; only 'sqlite' is available"
        )

    target_path = Path(path).expanduser() if path is not None else DATABASE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_database_file(target_path)
    return sqlite3.connect(str(target_path))
