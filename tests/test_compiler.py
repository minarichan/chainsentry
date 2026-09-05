from pathlib import Path

from scanner.compiler import compile_file, compile_source, compile_sources, parse_pragma, resolve_solc_version
from scanner.etherscan import parse_solc_version, parse_source_files
from scanner.parser import parse_compilation

ROOT = Path(__file__).resolve().parents[1]


def test_parse_pragma() -> None:
    source = "pragma solidity ^0.8.0;\ncontract C {}"
    assert parse_pragma(source) == "^0.8.0"
    assert resolve_solc_version(source) == "0.8.20"


def test_resolve_caret_newer_08() -> None:
    source = "pragma solidity ^0.8.24;\ncontract C {}"
    assert resolve_solc_version(source) == "0.8.24"


def test_solc_for_sources_tracks_lib_pragma() -> None:
    from scanner.compiler import solc_for_sources

    sources = {
        "Contract.sol": "pragma solidity ^0.8.0;\ncontract C {}",
        "Lib.sol": "pragma solidity ^0.8.24;\ncontract L {}",
    }
    assert solc_for_sources(sources, None) == "0.8.24"
    assert solc_for_sources(sources, "0.8.26") == "0.8.26"
    assert solc_for_sources(sources, "0.8.20") == "0.8.24"


def test_exact_pragma_uses_that_solc() -> None:
    from scanner.compiler import solc_for_sources

    source = "pragma solidity 0.8.17;\ncontract C {}"
    assert resolve_solc_version(source) == "0.8.17"
    assert solc_for_sources({"Contract.sol": source}, None) == "0.8.17"
    assert solc_for_sources({"Contract.sol": source}, "0.8.20") == "0.8.17"


def test_compile_exact_pragma_0817() -> None:
    source = "pragma solidity 0.8.17;\ncontract Pin { uint256 public x; }"
    result = compile_sources({"Contract.sol": source}, filename="Contract.sol")
    assert result.success, result.errors
    assert result.solc_version == "0.8.17"


def test_old_04_pragma_uses_installable_solc() -> None:
    from scanner.compiler import usable_solc_version

    source = "pragma solidity ^0.4.0;\ncontract C { function f() {} }"
    assert resolve_solc_version(source) == "0.4.26"
    assert usable_solc_version("0.4.6", source) == "0.4.26"


def test_compile_04_caret_pragma() -> None:
    source = "pragma solidity ^0.4.0;\ncontract OldFour { function f() {} }"
    result = compile_sources({"OldFour.sol": source}, filename="OldFour.sol", solc_version="0.4.6")
    assert result.success, result.errors
    assert result.solc_version == "0.4.26"


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


def test_explain_missing_imports() -> None:
    from scanner.compiler import MISSING_LIB_HINT, MISSING_PROJECT_HINT, explain_missing_imports

    raw = 'ParserError: Source "@openzeppelin/contracts/token/ERC20/ERC20.sol" not found.'
    out = explain_missing_imports([raw])
    assert out[0] == MISSING_LIB_HINT
    assert raw in out[1]

    project = 'ParserError: Source "src/interface/IProvider.sol" not found.'
    out = explain_missing_imports([project])
    assert out[0] == MISSING_PROJECT_HINT
    assert "IProvider.sol" in out[1]


def test_paste_oz_without_fetch_explains(monkeypatch) -> None:
    monkeypatch.setenv("SCAN_FETCH_OZ", "0")
    source = (
        "pragma solidity ^0.8.20;\n"
        'import "@openzeppelin/contracts/token/ERC20/ERC20.sol";\n'
        "contract Token is ERC20 { constructor() ERC20(\"T\", \"T\") {} }\n"
    )
    result = compile_sources({"Contract.sol": source}, filename="Contract.sol", solc_version="0.8.20")
    assert not result.success
    blob = "\n".join(result.errors)
    assert "OpenZeppelin" in blob or "flattened" in blob.lower()
    assert "ERC20.sol" in blob


def test_join_relative_oz_import() -> None:
    from scanner.compiler import _join_source, _unresolved_imports

    assert (
        _join_source("@openzeppelin/contracts/token/ERC20/ERC20.sol", "./IERC20.sol")
        == "@openzeppelin/contracts/token/ERC20/IERC20.sol"
    )
    missing = _unresolved_imports(
        {"@openzeppelin/contracts/token/ERC20/ERC20.sol": 'import "./IERC20.sol";\n'},
        [],
    )
    assert "@openzeppelin/contracts/token/ERC20/IERC20.sol" in missing


def test_canonical_short_oz_imports() -> None:
    from scanner.compiler import _canonical_oz

    assert (
        _canonical_oz("access/Ownable.sol")
        == "@openzeppelin/contracts/access/Ownable.sol"
    )
    assert (
        _canonical_oz("TransparentUpgradeableProxy.sol")
        == "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol"
    )


def test_oz_import_compiles_when_sources_included() -> None:
    erc20 = (
        "pragma solidity ^0.8.20;\n"
        "abstract contract ERC20 {\n"
        "    constructor(string memory, string memory) {}\n"
        "}\n"
    )
    source = (
        "pragma solidity ^0.8.20;\n"
        'import "@openzeppelin/contracts/token/ERC20/ERC20.sol";\n'
        "contract Token is ERC20 { constructor() ERC20(\"T\", \"T\") {} }\n"
    )
    result = compile_sources(
        {
            "Contract.sol": source,
            "@openzeppelin/contracts/token/ERC20/ERC20.sol": erc20,
        },
        filename="Contract.sol",
        solc_version="0.8.20",
    )
    assert result.success, result.errors
