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

_CREATE_MUTES = """
CREATE TABLE IF NOT EXISTS mutes (
    scope TEXT NOT NULL,
    finding_key TEXT NOT NULL,
    PRIMARY KEY (scope, finding_key)
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
    conn.execute(_CREATE_MUTES)
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


def finding_mute_key(finding_id: str, contract: str | None, function: str | None) -> str:
    return f"{finding_id}|{contract or ''}|{function or ''}"


def mute_scopes(scan_id: str, result: ScanResult) -> list[str]:
    scopes = [f"scan:{scan_id}"]
    if result.address:
        chain = result.chain_id or 1
        scopes.append(f"addr:{chain}:{result.address.lower()}")
    return scopes


def list_muted_keys(scan_id: str, result: ScanResult) -> set[str]:
    scopes = mute_scopes(scan_id, result)
    placeholders = ",".join("?" * len(scopes))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT finding_key FROM mutes WHERE scope IN ({placeholders})",
            scopes,
        ).fetchall()
    return {str(row[0]) for row in rows}


def set_muted(
    scan_id: str,
    result: ScanResult,
    finding_key: str,
    muted: bool,
) -> None:
    scopes = mute_scopes(scan_id, result)
    with _connect() as conn:
        if muted:
            conn.executemany(
                "INSERT OR IGNORE INTO mutes (scope, finding_key) VALUES (?, ?)",
                [(scope, finding_key) for scope in scopes],
            )
        else:
            conn.executemany(
                "DELETE FROM mutes WHERE scope = ? AND finding_key = ?",
                [(scope, finding_key) for scope in scopes],
            )
