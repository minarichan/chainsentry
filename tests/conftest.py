from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


@pytest.fixture(scope="session", autouse=True)
def solc_ready() -> None:
    from solcx import install_solc, set_solc_version

    install_solc("0.8.20")
    set_solc_version("0.8.20")


@pytest.fixture(scope="session", autouse=True)
def solc_ready() -> None:
    from solcx import install_solc, set_solc_version

    install_solc("0.8.20")
    set_solc_version("0.8.20")
