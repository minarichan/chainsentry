"""SQLite scan store so reports survive API restart and can be shared by id."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from scanner.models import ScanResult
from scanner.settings import ROOT

_CREATE = """
CREATE TABLE IF NOT EXISTS scans (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def db_path() -> Path:
    raw = (os.getenv("SCAN_DB_PATH") or "").strip()
    path = Path(raw) if raw else ROOT / "data" / "scans.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.execute(_CREATE)
    return conn


def save_scan(scan_id: str, result: ScanResult) -> None:
    payload = json.dumps(result.to_dict())
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scans (id, payload) VALUES (?, ?)",
            (scan_id, payload),
        )


def load_scan(scan_id: str) -> ScanResult | None:
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return ScanResult.from_dict(data)
