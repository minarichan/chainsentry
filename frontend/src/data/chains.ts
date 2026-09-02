export const SCAN_CHAINS = [
  { id: 1, label: "Ethereum" },
  { id: 8453, label: "Base" },
  { id: 42161, label: "Arbitrum" },
] as const;

export type ScanChainId = (typeof SCAN_CHAINS)[number]["id"];

const STORAGE_KEY = "chainsentry.chainId";

export function isScanChainId(value: number): value is ScanChainId {
  return SCAN_CHAINS.some((chain) => chain.id === value);
}

export function readStoredChainId(): ScanChainId {
  try {
    const raw = Number(window.localStorage.getItem(STORAGE_KEY));
    if (isScanChainId(raw)) return raw;
  } catch {
    /* ignore */
  }
  return 1;
}

export function storeChainId(chainId: ScanChainId) {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(chainId));
  } catch {
    /* ignore */
  }
}
