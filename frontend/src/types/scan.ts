export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  id: string;
  title: string;
  severity: Severity;
  confidence: number;
  description: string;
  location: { file: string; line: number; column: number; end_line: number | null };
  function: string | null;
  recommendation: string;
  classification: string;
  contract: string | null;
  snippet?: string | null;
  snippet_start_line?: number;
  muted?: boolean;
}

export interface FunctionSurface {
  name: string;
  contract: string;
  visibility: string;
  mutability: string;
  payable: boolean;
  modifies_state: boolean;
  has_external_call: boolean;
  sends_eth: boolean;
  has_reentrancy_guard: boolean;
  has_access_control: boolean;
  risk: "HIGH" | "MEDIUM" | "LOW" | string;
  notes: string[];
  line: number;
}

export interface CategoryScore {
  name: string;
  score: number;
  finding_count: number;
}

export interface OnChain {
  address: string;
  network: string;
  verified: boolean;
  transaction_count: number | null;
  unique_users: number | null;
  eth_balance: string | null;
  is_proxy: boolean;
  implementation?: string | null;
  has_privileged_owner: boolean;
  owner: string | null;
  signals: string[];
  notes: string[];
}

export interface ScanResult {
  id: string;
  score: number;
  score_kind?: string;
  verdict?: string;
  verdict_label?: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  findings: Finding[];
  contracts: Array<{
    name: string;
    kind: string;
    inheritance: string[];
    functions: number;
    state_variables: number;
    events: number;
    modifiers: number;
    line: number;
  }>;
  functions: FunctionSurface[];
  onchain: OnChain | null;
  filename: string;
  network: string;
  address: string | null;
  implementation_address?: string | null;
  analyzed_address?: string | null;
  analyzed_name?: string | null;
  source_role?: string;
  proxy_note?: string | null;
  verified: boolean;
  compiler_errors: string[];
  solc_version?: string;
  scorecard: {
    score: number;
    score_kind?: string;
    verdict?: string;
    verdict_label?: string;
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
    categories: CategoryScore[];
  };
}
