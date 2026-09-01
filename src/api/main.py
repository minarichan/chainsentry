from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scanner.settings import load_environment

load_environment()

from api.routes.contracts import router as contracts_router
from api.routes.scan import router as scan_router

app = FastAPI(
    title="Smart Contract Security Scanner",
    description="Static analysis API for Solidity contracts.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan_router)
app.include_router(contracts_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
