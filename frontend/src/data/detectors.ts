export const DETECTORS = [
  {
    id: "SC-REENTRANCY-001",
    swc: "SWC-107",
    title: "Reentrancy",
    summary: "Flags low-level and high-level external calls that happen before storage is updated (checks-effects-interactions).",
  },
  {
    id: "SC-REENTRANCY-002",
    swc: "SWC-107",
    title: "Cross-function reentrancy",
    summary: "Flags an external call while storage already read is still stale, when another public function can write that state in the same transaction.",
  },
  {
    id: "SC-ACCESS-001",
    swc: "SWC-105",
    title: "Missing access control",
    summary: "Flags privileged admin surfaces (pause, upgrade, drain, mint with an amount) that lack msg.sender checks. Public AMM-style mint(address) is ignored.",
  },
  {
    id: "SC-TXORIGIN-001",
    swc: "SWC-115",
    title: "tx.origin authentication",
    summary: "Flags authorization that uses tx.origin instead of msg.sender.",
  },
  {
    id: "SC-UNCHECKED-001",
    swc: "SWC-104",
    title: "Unchecked low-level calls",
    summary: "Flags call / send / transfer results that are ignored.",
  },
  {
    id: "SC-DELEGATECALL-001",
    swc: "SWC-112",
    title: "Dangerous delegatecall",
    summary: "Flags delegatecall to an address that is not a compile-time constant.",
  },
  {
    id: "SC-SELFDESTRUCT-001",
    swc: "SWC-106",
    title: "Unprotected selfdestruct",
    summary: "Flags selfdestruct reachable without access control.",
  },
  {
    id: "SC-TIMESTAMP-001",
    swc: "SWC-116",
    title: "Timestamp dependence",
    summary: "Flags block.timestamp used as a protocol time gate. Caller-supplied deadline checks are ignored.",
  },
    {
        id: "SC-RANDOMNESS-001",
        swc: "SWC-120",
        title: "Weak on-chain randomness",
        summary: "Flags keccak/modulo mixes of block attributes used as entropy.",
    },
    {
        id: "SC-ERC20-001",
        swc: "ERC20",
        title: "Unchecked ERC-20 return",
        summary: "Flags token.transfer / transferFrom / approve when the bool return is ignored. SafeERC20 or require(...) is the usual fix.",
    },
    {
        id: "SC-INIT-001",
        swc: "initializer",
        title: "Unprotected initializer",
        summary: "Flags public initialize() without an initializer modifier, initialized flag, or caller check. Typical proxy takeover.",
    },
    {
        id: "SC-TRANSFERFROM-001",
        swc: "arbitrary-from",
        title: "Arbitrary transferFrom source",
        summary: "Flags transferFrom(from, ...) when from is a function argument. Pull from msg.sender, or require(from == msg.sender).",
    },
] as const;
