const STORAGE_KEY = "chainsentry.history";
const MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
const MAX_ITEMS = 20;

export interface HistoryEntry {
  id: string;
  label: string;
  at: number;
}

function safeParse(raw: string | null): HistoryEntry[] {
  if (!raw) return [];
  try {
    const data = JSON.parse(raw) as unknown;
    if (!Array.isArray(data)) return [];
    const cutoff = Date.now() - MAX_AGE_MS;
    return data.filter((item): item is HistoryEntry => {
      return (
        Boolean(item) &&
        typeof item === "object" &&
        typeof (item as HistoryEntry).id === "string" &&
        typeof (item as HistoryEntry).label === "string" &&
        typeof (item as HistoryEntry).at === "number" &&
        (item as HistoryEntry).at >= cutoff
      );
    });
  } catch {
    return [];
  }
}

export function readScanHistory(): HistoryEntry[] {
  try {
    return safeParse(window.localStorage.getItem(STORAGE_KEY)).slice(0, MAX_ITEMS);
  } catch {
    return [];
  }
}

export function rememberScan(id: string, label: string) {
  try {
    const next = [{ id, label, at: Date.now() }, ...readScanHistory().filter((item) => item.id !== id)].slice(
      0,
      MAX_ITEMS,
    );
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota / private mode */
  }
}
