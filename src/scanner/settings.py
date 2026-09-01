"""Load project .env so CLI, API, and scripts share the same keys."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[2]
_ENV_KEYS = ("ETHERSCAN_API_KEY", "ETHERSCAN_CHAIN_ID", "ETH_RPC_URL", "BLOCKSCOUT_API_URL")


def sync_empty_keys_from_dotenv() -> None:
    """Pick up keys added to .env after process start when the process env is empty."""
    path = ROOT / ".env"
    if not path.is_file():
        return
    values = dotenv_values(path)
    for name in _ENV_KEYS:
        file_val = (values.get(name) or "").strip()
        env_val = (os.getenv(name) or "").strip()
        if file_val and not env_val:
            os.environ[name] = file_val


def load_environment() -> Path:
    load_dotenv(ROOT / ".env")
    load_dotenv()
    sync_empty_keys_from_dotenv()
    return ROOT


load_environment()
