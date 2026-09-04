const STORAGE_KEY = "chainsentry.etherscanApiKey";

export function readEtherscanKey(): string {
  try {
    return (window.localStorage.getItem(STORAGE_KEY) || "").trim();
  } catch {
    return "";
  }
}

export function storeEtherscanKey(value: string) {
  const trimmed = value.trim();
  try {
    if (!trimmed) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, trimmed);
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearEtherscanKey() {
  storeEtherscanKey("");
}
