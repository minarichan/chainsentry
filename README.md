# ChainSentry

**Security scanner for the on-chain stack.** Paste a verified address on Ethereum, Base, or Arbitrum; ChainSentry fetches the source, compiles it with `solc`, and reports SWC-class issues with a severity mix, function attack surface, and on-chain context.

This is a defensive static analyzer. It reports findings and recommended fixes. It does not generate exploits, and it does not treat unverified bytecode as a full source audit.

![ChainSentry scan screen](docs/screenshot-scan.png)

## What it does

Address-first in the dashboard: enter `0x…`, get a report. You can still paste a `.sol` file or run the CLI against fixtures.

| Step | What happens |
|---|---|
| Source | Sourcify (no key), then Etherscan V2 if `ETHERSCAN_API_KEY` is set, then Blockscout. Proxies: one hop to the implementation. |
| Compile | Multi-file `solc` with the verified compiler version, optimizer / `viaIR` / runs from the explorer, Foundry remappings, `viaIR` retry on “stack too deep”. Library paths such as OpenZeppelin are skipped in analysis. |
| Detect | One detector module per vulnerability class. Inherited members are analyzed on the most-derived contract so the same body is not reported twice. Duplicate hits across files are collapsed. |
| Report | Verdict from severity mix (heuristic, not a 0–100 rating), plus per-function attack surface. |
| Report | Console, JSON, HTML, Markdown, SARIF, or the React dashboard (overview, findings, functions, on-chain snapshot). |

Unverified contracts stop with a clear error. Bytecode-only analysis is out of scope.

## Detectors

| ID | Issue | SWC |
|---|---|---|
| `SC-REENTRANCY-001` | Low-level or high-level external call before storage update | SWC-107 |
| `SC-REENTRANCY-002` | External call while shared storage is stale; another public function writes it | SWC-107 |
| `SC-ACCESS-001` | Privileged admin surface without access control | SWC-105 |
| `SC-TXORIGIN-001` | Auth via `tx.origin` | SWC-115 |
| `SC-UNCHECKED-001` | Low-level call with ignored return value | SWC-104 |
| `SC-DELEGATECALL-001` | `delegatecall` (worse if the target is a parameter) | SWC-112 |
| `SC-SELFDESTRUCT-001` | `selfdestruct` | SWC-106 |
| `SC-TIMESTAMP-001` | Protocol time gate on `block.timestamp` (not swap deadlines) | SWC-116 |
| `SC-RANDOMNESS-001` | RNG from block attributes | SWC-120 |
| `SC-ERC20-001` | Ignored ERC-20 `transfer` / `transferFrom` / `approve` return | ERC20 |
| `SC-INIT-001` | Public `initialize()` with no initializer guard | initializer |
| `SC-TRANSFERFROM-001` | `transferFrom` `from` is a caller-controlled argument | arbitrary-from |

Each detector lives under `src/scanner/detectors/`. The CLI, FastAPI, and dashboard consume the same findings.

Heuristic scanners still miss issues and can false-positive. Treat findings as a triage signal, not an audit sign-off.

## Compared to Slither (repo fixtures only)

Ran ChainSentry and [Slither](https://github.com/crytic/slither) **0.11.6** on every file under `contracts/vulnerable` and `contracts/safe`, compiled with **solc 0.8.20** (3 Sep 2026). Slither informational noise is omitted (`solc-version`, `low-level-calls`, naming, `immutable-states`). These contracts were written as ChainSentry tests, so this is not an independent bake-off and it is not a substitute for Slither on a real protocol.

**Both flag the intended bug**

| Fixture | ChainSentry | Slither |
|---|---|---|
| `Reentrancy.sol`, `InheritedReentrancy.sol`, `InheritedBaseReentrancy.sol` | `SC-REENTRANCY-001` | `reentrancy-eth` |
| `TokenReentrancy.sol` | `SC-REENTRANCY-001`, `SC-ERC20-001` | `reentrancy-no-eth`, `unchecked-transfer` |
| `TxOrigin.sol` | `SC-TXORIGIN-001` | `tx-origin` |
| `UncheckedCall.sol` | `SC-UNCHECKED-001` | `unchecked-lowlevel` |
| `DelegateCall.sol` | `SC-DELEGATECALL-001` | `controlled-delegatecall` |
| `SelfDestruct.sol` | `SC-SELFDESTRUCT-001` | `suicidal` |
| `Timestamp.sol` | `SC-TIMESTAMP-001` | `timestamp` |
| `UncheckedErc20.sol` | `SC-ERC20-001` | `unchecked-transfer` |
| `ArbitraryTransferFrom.sol` | `SC-TRANSFERFROM-001` | `arbitrary-send-erc20` |
| `AccessControl.sol` | `SC-ACCESS-001` | `arbitrary-send-eth` |
| `Randomness.sol` | `SC-RANDOMNESS-001` | `weak-prng` |

Safe twins for those patterns (`SafeReentrancy`, `SafeTokenReentrancy`, `SafeAccessControl`, `AmmMint`, `SafeErc20Return`, `SafeInheritedReentrancy`, `SafeCrossFunctionReentrancy`) were clean in both tools.

**ChainSentry-only on this set**

| Fixture | What happened |
|---|---|
| `CrossFunctionReentrancy.sol` | `SC-REENTRANCY-002` on `harvest` / `claim`. Slither 0.11.6 emitted no reentrancy detector (`harvest` is a high-level `notify`, not ETH or ERC-20). |
| `AdminMint.sol` | `SC-ACCESS-001` on `mint(address,uint256)`. Slither has no matching “unrestricted mint” check here. |
| `UnprotectedInitialize.sol` | `SC-INIT-001`. Slither only reported `missing-zero-check` on the new owner, not an unguarded initializer. |

**Slither-only, or ChainSentry is quieter**

| Fixture | What happened |
|---|---|
| `SwapDeadline.sol` | Slither `timestamp`. We skip caller-supplied swap deadlines on purpose. |
| `SafeTransferFrom.sol` | Slither `arbitrary-send-erc20` on `depositFor` even with `require(from == msg.sender)`. We treat that as `msg.sender`. |
| `SafeInitialize.sol` | Slither `missing-zero-check`. Both tools accept the toy `initializer` modifier as enough. |

On the same function, ChainSentry keeps the more specific card: `SC-RANDOMNESS-001` without a second timestamp/access hit, `SC-SELFDESTRUCT-001` / `SC-TXORIGIN-001` without a duplicate access card, and reentrancy without a second `delegatecall` card when that call is already the reentrancy finding.

Slither’s catalog is much larger than twelve AST checks (encoding, upgrades, data races, optimizations, …). Use ChainSentry for address-first triage. Run Slither — and a human review — before you treat a contract as safe.

## Quick start (dashboard)

Python 3.10+ (3.12 in CI). `py-solc-x` downloads `solc` on first compile.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

API (from the repo root):

```bash
# Windows
set PYTHONPATH=src
uvicorn api.main:app --app-dir src --host 127.0.0.1 --port 8000

# macOS/Linux
PYTHONPATH=src uvicorn api.main:app --app-dir src --host 127.0.0.1 --port 8000
```

UI:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to the process on port 8000.

A finished report lives at `#/report/<id>` and is stored in SQLite (`data/scans.sqlite`) so refresh and copy-link work after the API restarts.

Try a Sourcify-verified mainnet address (no Etherscan key). On the dashboard, **Try Multicall3 on Ethereum** fills this in:

`0xcA11bde05977b3631167028862bE2a173976CA11` — [Multicall3](https://www.multicall3.com/), solc 0.8.12, same address on Base and Arbitrum.

Contracts that exist only on Etherscan need `ETHERSCAN_API_KEY` in `.env` and a restarted API process. The hosted demo does not set that key.

## CLI

```bash
python -m scanner scan contracts/example.sol
python -m scanner scan contracts/vulnerable/Reentrancy.sol --format all
python -m scanner scan contracts/safe/SafeReentrancy.sol --fail-on high

python -m scanner scan --address 0xcA11bde05977b3631167028862bE2a173976CA11
python -m scanner scan --chain-id 8453 --address 0x...
python -m scanner scan contracts/example.sol --format json --output reports
python -m scanner scan contracts/example.sol --format html
python -m scanner scan contracts/vulnerable/Reentrancy.sol --format markdown
python -m scanner scan contracts/vulnerable/Reentrancy.sol --format sarif
```

`--fail-on high` exits `1` if high or critical findings exist (used in CI). Unverified or unsupported compilers exit `3`.

## GitHub Action

Other repos can run ChainSentry on their Solidity and publish Markdown + SARIF. It does **not** scan every repository on an account — only a repo that adds this workflow.

```yaml
# .github/workflows/chainsentry.yml
name: ChainSentry
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: minarichan/chainsentry@main
        with:
          path: contracts
          fail-on: high
          comment-pr: true
```

`path` is a file or directory (`.sol` files; `node_modules` / `lib` / `out` are skipped). Leave `fail-on` empty to report without failing the job. SARIF upload needs Code Scanning enabled; the step is allowed to fail if the repo cannot upload.

## API

- `POST /scan` – `{ "address": "0x...", "chain_id": 1 }` (`8453` Base, `42161` Arbitrum) or `{ "source": "pragma ..." }`
- `GET /scan/{id}` – stored result
- `GET /scan/{id}/report.md` – Markdown report
- `GET /scan/{id}/report.sarif` – SARIF 2.1.0
- `GET /contract/{address}?chain_id=1` – verification + on-chain signals
- `GET /health`

## Configuration

Copy `.env.example` to `.env` (gitignored):

| Variable | Role |
|---|---|
| `ETHERSCAN_API_KEY` | Etherscan V2 fallback + tx stats. Optional if Sourcify has the source. |
| `ETHERSCAN_CHAIN_ID` | CLI default when `--chain-id` is omitted. UI sends `chain_id` per scan (`1` / `8453` / `42161`). |
| `ETH_RPC_URL` | Ethereum RPC for balance, EIP-1967 slots, `owner()`. |
| `BASE_RPC_URL` | Base RPC (default `https://mainnet.base.org`). |
| `ARB_RPC_URL` | Arbitrum One RPC (default `https://arb1.arbitrum.io/rpc`). |

Local `.sol` scans never need a key.

## Tests and CI

Fixtures in `contracts/vulnerable/` must produce the matching finding. Fixtures in `contracts/safe/` must not false-positive at high severity.

```bash
pytest
```

GitHub Actions (`.github/workflows/security.yml`) runs pytest, gates on safe contracts with `--fail-on high`, and uploads HTML/JSON/Markdown/SARIF reports.

## Docker

Requires Docker Desktop (or another Compose-capable engine). From the repo root:

```bash
docker compose up --build
```

- UI: http://localhost:3000
- API: http://localhost:8000/health

The UI proxies `/api` to the API container. Stop a local uvicorn on port 8000 first if that port is already in use.

## Production (InterServer VPS)

The UI and API are one image (`Dockerfile`). Hash routes (`/#/`, `/#/report/<id>`) stay in the browser.

On your Windows PC: copy `deploy/secrets.env.example` → `deploy/secrets.env`, then see **`deploy/README.md`** for SSH keys, backup, `bootstrap.ps1` / `push.ps1` / `watch.ps1`, Cloudflare DNS for `chainsentry.dev`, and `chainsentry.eth` records. Do not put SSH passwords in git.

## Layout

```
src/scanner/          engine, compiler, parser, detectors, scoring, reports, CLI
src/api/              FastAPI
frontend/             React + TypeScript dashboard
contracts/            example + vulnerable / safe fixtures
tests/                compiler, parser, detectors, API
.github/workflows/    pytest + scan gate
```

## License

MIT
