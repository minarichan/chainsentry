import type { ScanChainId } from "./chains";

/** Sourcify full match, solc 0.8.12, same address on several L2s. No Etherscan key. */
export const DEMO_SCAN = {
  chainId: 1 as ScanChainId,
  address: "0xcA11bde05977b3631167028862bE2a173976CA11",
  label: "Multicall3",
  network: "Ethereum",
} as const;
