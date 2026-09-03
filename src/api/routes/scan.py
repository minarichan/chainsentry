from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from api.limits import acquire_scan_slot, enforce_scan_rate, release_scan_slot
from api.schemas.scan import ScanRequest, result_to_summary
from api.store import load_scan, save_scan
from scanner.chains import UnsupportedChainError, resolve_chain
from scanner.engine import scan_source, scan_verified
from scanner.etherscan import SourceNotVerifiedError, UnsupportedCompilerError
from scanner.models import ScanResult
from scanner.onchain import analyze_address
from scanner.proxy import apply_scan_target, fetch_scan_target
from scanner.reporting import render_markdown, render_sarif

router = APIRouter(tags=["scan"])
_SCAN_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scan")


def _timeout_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("SCAN_TIMEOUT_SEC", "120")))
    except ValueError:
        return 120.0


def _execute_scan(body: ScanRequest) -> ScanResult:
    if body.address:
        spec = resolve_chain(body.chain_id)
        target = fetch_scan_target(body.address, chain_id=spec.id)
        result = apply_scan_target(scan_verified(target.analyzed, network=spec.network), target)
        if body.include_onchain:
            try:
                onchain = analyze_address(
                    body.address,
                    verified=True,
                    rpc_url=spec.rpc_url(),
                    network=spec.network,
                    chain_id=spec.id,
                )
                if target.implementation:
                    onchain.implementation = onchain.implementation or target.implementation
                    onchain.is_proxy = True
                    if "Upgradeable proxy" not in onchain.signals:
                        onchain.signals.append("Upgradeable proxy")
                result.onchain = onchain
            except Exception:
                result.onchain = None
        return result
    result = scan_source(body.source or "", filename=body.filename)
    result.network = "Local"
    return result


@router.post("/scan")
def create_scan(body: ScanRequest, request: Request) -> dict:
    if not body.source and not body.address:
        raise HTTPException(status_code=400, detail="Provide source or address.")

    enforce_scan_rate(request)
    acquire_scan_slot()
    try:
        future = _SCAN_POOL.submit(_execute_scan, body)
        result = future.result(timeout=_timeout_seconds())
    except FuturesTimeout:
        raise HTTPException(
            status_code=504,
            detail="Scan timed out. First-time solc download can be slow; try again, or set SCAN_TIMEOUT_SEC.",
        ) from None
    except (SourceNotVerifiedError, UnsupportedCompilerError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnsupportedChainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        if body.address:
            raise HTTPException(status_code=502, detail=f"Verified source lookup failed: {exc}") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        release_scan_slot()

    scan_id = str(uuid.uuid4())
    save_scan(scan_id, result)
    return result_to_summary(scan_id, result)


@router.get("/scan/{scan_id}")
def get_scan(scan_id: str) -> dict:
    result = load_scan(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return result_to_summary(scan_id, result)


def _stored_scan(scan_id: str) -> ScanResult:
    result = load_scan(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return result


def _export_stem(result: ScanResult) -> str:
    name = (result.filename or "report").replace("\\", "/").split("/")[-1]
    return name.rsplit(".", 1)[0] or "report"


@router.get("/scan/{scan_id}/report.md")
def export_markdown(scan_id: str) -> Response:
    result = _stored_scan(scan_id)
    stem = _export_stem(result)
    return Response(
        content=render_markdown(result),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}.md"'},
    )


@router.get("/scan/{scan_id}/report.sarif")
def export_sarif(scan_id: str) -> Response:
    result = _stored_scan(scan_id)
    stem = _export_stem(result)
    body = json.dumps(render_sarif(result), indent=2)
    return Response(
        content=body,
        media_type="application/sarif+json",
        headers={"Content-Disposition": f'attachment; filename="{stem}.sarif"'},
    )
