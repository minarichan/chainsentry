from fastapi import APIRouter, HTTPException, Query

from scanner.chains import UnsupportedChainError, resolve_chain
from scanner.etherscan import SourceNotVerifiedError, fetch_verified_source
from scanner.onchain import analyze_address

router = APIRouter(tags=["contracts"])


@router.get("/contract/{address}")
def get_contract(
    address: str,
    chain_id: int = Query(default=1, description="1 Ethereum, 8453 Base, 42161 Arbitrum"),
) -> dict:
    try:
        spec = resolve_chain(chain_id)
    except UnsupportedChainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    verified = False
    name = None
    compiler_version = None
    source_error = None
    try:
        info = fetch_verified_source(address, chain_id=spec.id)
        verified = True
        name = info.name
        compiler_version = info.compiler_version
    except SourceNotVerifiedError as exc:
        source_error = str(exc)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        onchain = analyze_address(
            address,
            verified=verified,
            rpc_url=spec.rpc_url(),
            network=spec.network,
            chain_id=spec.id,
        )
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
