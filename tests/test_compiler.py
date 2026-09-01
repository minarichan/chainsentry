from pathlib import Path

from scanner.compiler import compile_file, compile_source, compile_sources, parse_pragma, resolve_solc_version
from scanner.etherscan import parse_solc_version, parse_source_files
from scanner.parser import parse_compilation

ROOT = Path(__file__).resolve().parents[1]


def test_parse_pragma() -> None:
    source = "pragma solidity ^0.8.0;\ncontract C {}"
    assert parse_pragma(source) == "^0.8.0"
    assert resolve_solc_version(source) == "0.8.20"


def test_parse_solc_version() -> None:
    assert parse_solc_version("v0.8.20+commit.a1b79de6") == "0.8.20"
    assert parse_solc_version("0.8.19") == "0.8.19"
    assert parse_solc_version("vyper:0.3.7") is None


def test_parse_single_file_source() -> None:
    raw = "pragma solidity ^0.8.0;\ncontract Foo {}"
    files, primary, optimizer, remappings, evm_version = parse_source_files(raw, "Foo")
    assert primary == "Foo.sol"
    assert files[primary] == raw
    assert optimizer is None
    assert remappings == []
    assert evm_version is None


def test_parse_standard_json_double_wrapped() -> None:
    inner = {
        "language": "Solidity",
        "sources": {
            "contracts/Token.sol": {"content": "pragma solidity ^0.8.0; contract Token {}"},
            "contracts/Lib.sol": {"content": "pragma solidity ^0.8.0; library Lib {}"},
        },
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "remappings": ["@oz/=lib/oz/"],
            "evmVersion": "paris",
        },
    }
    import json

    raw = "{" + json.dumps(inner) + "}"
    files, primary, optimizer, remappings, evm_version = parse_source_files(raw, "Token")
    assert primary == "contracts/Token.sol"
    assert "contracts/Lib.sol" in files
    assert optimizer == {"enabled": True, "runs": 200}
    assert remappings == ["@oz/=lib/oz/"]
    assert evm_version == "paris"


def test_compile_example() -> None:
    result = compile_file(ROOT / "contracts" / "example.sol")
    assert result.success, result.errors
    assert result.ast.get("nodeType") == "SourceUnit"
    assert "Example" in result.abis
    assert result.abis["Example"]
    assert result.file_asts


def test_compile_invalid_source() -> None:
    from scanner.compiler import compile_source

    result = compile_source("pragma solidity ^0.8.0; contract {", filename="Bad.sol")
    assert not result.success
    assert result.errors
    blob = "\n".join(result.errors)
    assert "stdout:" not in blob
    assert len(blob) < 2000


def test_solc_error_drops_json_dump() -> None:
    import json

    from solcx.exceptions import SolcError

    from scanner.compiler import messages_from_solc_error

    stdout = json.dumps(
        {
            "contracts": {"Foo.sol": {"Foo": {"abi": [{"type": "function", "name": "x"}] * 50}}},
            "errors": [
                {
                    "severity": "error",
                    "formattedMessage": "CompilerError: Stack too deep.\n --> Foo.sol:10:5\n",
                    "message": "Stack too deep.",
                }
            ],
        }
    )
    exc = SolcError(
        message="Compilation failed",
        command=["solc", "--standard-json"],
        return_code=0,
        stdout_data=stdout,
        stderr_data="",
    )
    messages = messages_from_solc_error(exc)
    assert any("Stack too deep" in item for item in messages)
    assert all("abi" not in item and "stdout:" not in item for item in messages)


def test_infer_forge_std_at_prefix() -> None:
    from scanner.compiler import infer_remappings, normalize_remappings

    remaps = normalize_remappings([":forge-std/=lib/forge-std/src/"])
    assert "forge-std/=lib/forge-std/src/" in remaps
    assert "@forge-std/=lib/forge-std/src/" in remaps

    sources = {
        "src/vendor/Lib.sol": 'pragma solidity ^0.8.0;\nimport {IERC20} from "@forge-std/interfaces/IERC20.sol";\n',
        "lib/forge-std/src/interfaces/IERC20.sol": (
            "pragma solidity ^0.8.0; interface IERC20 { function balanceOf(address) external view returns (uint256); }\n"
        ),
    }
    inferred = infer_remappings(sources, [":forge-std/=lib/forge-std/src/"])
    assert any(item.startswith("@forge-std/=") for item in inferred)


def test_compile_forge_std_remap() -> None:
    lib = (
        "pragma solidity ^0.8.0;\n"
        'import {IERC20} from "@forge-std/interfaces/IERC20.sol";\n'
        "library TokenLib { function bal(IERC20 t, address a) internal view returns (uint256) { return t.balanceOf(a); } }\n"
    )
    token = "pragma solidity ^0.8.0;\ninterface IERC20 { function balanceOf(address) external view returns (uint256); }\n"
    main = (
        "pragma solidity ^0.8.0;\n"
        'import "./vendor/Lib.sol";\n'
        "contract Holder { }\n"
    )
    compilation = compile_sources(
        {
            "src/vendor/Lib.sol": lib,
            "lib/forge-std/src/interfaces/IERC20.sol": token,
            "src/Holder.sol": main,
        },
        filename="src/Holder.sol",
        solc_version="0.8.20",
        remappings=[":forge-std/=lib/forge-std/src/"],
    )
    assert compilation.success, compilation.errors
    names = {c.name for c in parse_compilation(compilation)}
    assert "Holder" in names


def test_compile_multi_file() -> None:
    lib = "pragma solidity ^0.8.0;\nlibrary Math { function add(uint a, uint b) internal pure returns (uint) { return a + b; } }\n"
    main = (
        "pragma solidity ^0.8.0;\n"
        'import "./Math.sol";\n'
        "contract Counter { function sum(uint a, uint b) public pure returns (uint) { return Math.add(a, b); } }\n"
    )
    compilation = compile_sources(
        {"Math.sol": lib, "Counter.sol": main},
        filename="Counter.sol",
        solc_version="0.8.20",
    )
    assert compilation.success, compilation.errors
    contracts = parse_compilation(compilation)
    names = {c.name for c in contracts}
    assert names == {"Counter"}


def test_normalize_optimizer() -> None:
    from scanner.compiler import normalize_optimizer

    assert normalize_optimizer(None) == {"enabled": False, "runs": 200}
    assert normalize_optimizer({"enabled": True, "runs": 1_000_000}) == {
        "enabled": True,
        "runs": 1_000_000,
    }
    assert normalize_optimizer({"enabled": "1", "runs": "200"}) == {"enabled": True, "runs": 200}
    assert normalize_optimizer({"enabled": "0"}) == {"enabled": False, "runs": 200}


def test_scan_verified_uses_explorer_compile_settings(monkeypatch) -> None:
    from scanner.compiler import CompilationResult
    from scanner.engine import scan_verified
    from scanner.etherscan import VerifiedContract

    captured: dict = {}

    def fake_compile_sources(sources, **kwargs):
        captured["sources"] = sources
        captured.update(kwargs)
        src = "pragma solidity ^0.8.0; contract Logic {}"
        ast = {"nodeType": "SourceUnit", "nodes": []}
        return CompilationResult(
            success=True,
            source=src,
            filename="Logic.sol",
            solc_version="0.8.20",
            ast=ast,
            file_asts={"Logic.sol": ast},
            file_sources={"Logic.sol": src},
        )

    monkeypatch.setattr("scanner.engine.compile_sources", fake_compile_sources)
    verified = VerifiedContract(
        address="0x0000000000000000000000000000000000000001",
        name="Logic",
        source="pragma solidity ^0.8.0; contract Logic {}",
        compiler_version="v0.8.20+commit.a1b79de6",
        solc_version="0.8.20",
        verified=True,
        sources={"Logic.sol": "pragma solidity ^0.8.0; contract Logic {}"},
        primary_file="Logic.sol",
        optimizer={"enabled": True, "runs": 999},
        via_ir=True,
        evm_version="paris",
    )
    scan_verified(verified)
    assert captured["optimizer"] == {"enabled": True, "runs": 999}
    assert captured["via_ir"] is True
    assert captured["evm_version"] == "paris"
    assert captured["solc_version"] == "0.8.20"
