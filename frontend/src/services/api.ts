import { readEtherscanKey } from "../data/etherscanKey";
import type { Finding, ScanResult } from "../types/scan";

const API_BASE = "/api";
const SCAN_TIMEOUT_MS = 125_000;

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      const detail = body.detail.replaceAll("`", "");
      if (detail === "Internal Server Error") {
        return "Scanner backend failed. If this is localhost, start the API on port 8000.";
      }
      if (detail.startsWith("Verified source lookup failed")) {
        const hasKey = Boolean(readEtherscanKey());
        return hasKey
          ? "Could not fetch verified source from Sourcify, Etherscan, or Blockscout. Try another address, or paste a .sol file."
          : "Could not fetch verified source. This public demo looks up Sourcify, then Blockscout (no Etherscan key unless you add one in Settings). Try the example address, or paste a .sol file.";
      }
      return detail;
    }
    return JSON.stringify(body.detail ?? body);
  } catch {
    if (response.status >= 500) {
      return "Cannot reach the scanner API. Start it on port 8000 (the UI on 5173 only proxies /api).";
    }
    return response.statusText || "Request failed";
  }
}

async function postScan(payload: Record<string, unknown>): Promise<ScanResult> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), SCAN_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(await parseError(response));
    return response.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Scan timed out. First solc download can take a while — try again.");
    }
    if (err instanceof TypeError) {
      throw new Error("Cannot reach the scanner API. Start it on port 8000.");
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function scanSource(source: string, filename = "Contract.sol"): Promise<ScanResult> {
  return postScan({ source, filename, include_onchain: false });
}

export async function scanAddress(
  address: string,
  chainId = 1,
  etherscanApiKey = "",
): Promise<ScanResult> {
  const payload: Record<string, unknown> = {
    address,
    include_onchain: true,
    chain_id: chainId,
  };
  const key = etherscanApiKey.trim() || readEtherscanKey();
  if (key) payload.etherscan_api_key = key;
  return postScan(payload);
}

export async function getScan(id: string): Promise<ScanResult> {
  const response = await fetch(`${API_BASE}/scan/${id}`);
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function setFindingMute(
  id: string,
  finding: Pick<Finding, "id" | "contract" | "function">,
  muted: boolean,
): Promise<ScanResult> {
  const response = await fetch(`${API_BASE}/scan/${id}/mute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      finding_id: finding.id,
      contract: finding.contract,
      function: finding.function,
      muted,
    }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function downloadScanExport(id: string, kind: "markdown" | "sarif"): Promise<void> {
  const suffix = kind === "markdown" ? "report.md" : "report.sarif";
  const response = await fetch(`${API_BASE}/scan/${id}/${suffix}`);
  if (!response.ok) throw new Error(await parseError(response));
  const blob = await response.blob();
  const header = response.headers.get("Content-Disposition") || "";
  const matched = header.match(/filename="([^"]+)"/);
  const filename = matched?.[1] || (kind === "markdown" ? "report.md" : "report.sarif");
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
