import type { ScanResult } from "../types/scan";

const API_BASE = "/api";

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail.replaceAll("`", "");
    return JSON.stringify(body.detail ?? body);
  } catch {
    return response.statusText;
  }
}

export async function scanSource(source: string, filename = "Contract.sol"): Promise<ScanResult> {
  const response = await fetch(`${API_BASE}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, filename, include_onchain: false }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function scanAddress(address: string): Promise<ScanResult> {
  const response = await fetch(`${API_BASE}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address, include_onchain: true }),
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
