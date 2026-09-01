from fastapi import APIRouter, HTTPException

from scanner.etherscan import SourceNotVerifiedError, fetch_verified_source
from scanner.onchain import analyze_address

router = APIRouter(tags=["contracts"])


@router.get("/contract/{address}")
def get_contract(address: str) -> dict:
    verified = False
    name = None
    compiler_version = None
    source_error = None
    try:
        info = fetch_verified_source(address)
        verified = True
        name = info.name
        compiler_version = info.compiler_version
    except SourceNotVerifiedError as exc:
        source_error = str(exc)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        onchain = analyze_address(address, verified=verified)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RPC error: {exc}") from exc

    return {
        "address": address,
        "name": name,
        "compiler_version": compiler_version,
        "verified": verified,
        "source_error": source_error,
        "onchain": onchain.to_dict(),
    }
