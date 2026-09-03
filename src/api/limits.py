"""Bound concurrent scans and per-IP rate so a public demo cannot wedge."""

from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request

_rate_lock = threading.Lock()
_hits: dict[str, list[float]] = {}
_gate_lock = threading.Lock()
_in_flight = 0


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_scan_rate(request: Request) -> None:
    per_min = _env_int("SCAN_RATE_PER_MIN", 12)
    per_hour = _env_int("SCAN_RATE_PER_HOUR", 40)
    if per_min <= 0:
        return

    key = client_ip(request)
    now = time.monotonic()
    with _rate_lock:
        recent = [stamp for stamp in _hits.get(key, []) if now - stamp < 3600]
        minute = sum(1 for stamp in recent if now - stamp < 60)
        if minute >= per_min or len(recent) >= per_hour:
            raise HTTPException(
                status_code=429,
                detail="Too many scans from this address. Wait a minute and try again.",
                headers={"Retry-After": "60"},
            )
        recent.append(now)
        _hits[key] = recent


def acquire_scan_slot() -> None:
    global _in_flight
    cap = max(1, _env_int("SCAN_MAX_IN_FLIGHT", 4))
    with _gate_lock:
        if _in_flight >= cap:
            raise HTTPException(
                status_code=503,
                detail="Scanner is busy. Wait for the current compile to finish, then retry.",
                headers={"Retry-After": "15"},
            )
        _in_flight += 1


def release_scan_slot() -> None:
    global _in_flight
    with _gate_lock:
        _in_flight = max(0, _in_flight - 1)


def reset_limits_for_tests() -> None:
    global _in_flight
    with _rate_lock:
        _hits.clear()
    with _gate_lock:
        _in_flight = 0
