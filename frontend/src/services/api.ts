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
        return (
          "Could not fetch verified source. This public demo looks up Sourcify, then Blockscout " +
          "(no Etherscan key). Try the example address, or paste a .sol file."
        );
      }
      return detail;
    }
    return JSON.stringify(body.detail ?? body);
  } catch {
    return response.statusText;
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
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function scanSource(source: string, filename = "Contract.sol"): Promise<ScanResult> {
  return postScan({ source, filename, include_onchain: false });
}

export async function scanAddress(address: string, chainId = 1): Promise<ScanResult> {
  return postScan({ address, include_onchain: true, chain_id: chainId });
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
