/**
 * Wire types for the BriefAlpha API. The shapes here mirror
 * `apps/api/briefalpha_api/fixtures/brief.py` and MUST stay in sync as the
 * pipeline replaces the fixture.
 */

export type Trend = "up" | "down" | "flat";

export type StatusLevel = "ok" | "active" | "degraded" | "failed";

export type JudgementLevel = "elevated" | "watch" | "info";

export interface BaseCase {
  headline_label: string;
  headline: string;
  summary: string;
  estimate_label: string;
  estimate_value: string;
  estimate_direction: Trend;
  estimate_explainer: string;
  evidence_count: number;
}

export interface PortfolioTile {
  ticker: string;
  label?: string;
  weight_pct: string;
  change_pct: string;
  trend: Trend;
  /** Token name in tailwind theme: e.g. "treemap.nvda" */
  color: string;
  row: 0 | 1;
  col_start: number;
  col_span: number;
}

export interface PortfolioSnapshot {
  as_of_hkt: string;
  tiles: PortfolioTile[];
  watchlist_summary: string;
}

export interface ReasoningChain {
  observed: string;
  portfolio_exposure: string;
  inference: string;
  conclusion: string;
}

export interface EvidenceCard {
  evidence_id: string;
  index_label: string;
  source_label: string;
  title: string;
  quote: string;
  source_link: string;
  conflict?: boolean;
}

export interface SupplementarySource {
  evidence_id: string;
  label: string;
  source_link: string;
}

export interface Judgement {
  id: string;
  rank: number;
  level: JudgementLevel;
  level_label: string;
  title: string;
  metadata: string;
  evidence_count: number;
  requires_review: boolean;
  no_direct_portfolio_link: boolean;
  reasoning_chain: ReasoningChain;
  evidence: EvidenceCard[];
  supplementary_sources: SupplementarySource[];
  suggested_questions: string[];
}

export interface PlaybookEvent {
  time_hkt: string;
  relative_time_hkt: string;
  label: string;
  detail: string;
  related_judgement_ids: string[];
  is_next: boolean;
}

export interface DeepReadEvidenceTrailRow {
  timestamp: string;
  label: string;
}

export interface SourceHealthRow {
  name: string;
  status: StatusLevel;
  detail: string;
}

export interface SourceHealth {
  as_of_hkt: string;
  overall: StatusLevel;
  rows: SourceHealthRow[];
}

export interface Brief {
  brief_id: string;
  brief_date_hkt: string;
  delivered_at_hkt: string;
  freeze_window_hkt: string;
  stale: boolean;
  audit_mode: "demo" | "compliance";
  anonymized: boolean;
  no_direct_portfolio_link: boolean;
  conservative: boolean;
  degraded_sources: string[];
  base_case: BaseCase;
  portfolio_snapshot: PortfolioSnapshot;
  judgements: Judgement[];
  playbook_events: PlaybookEvent[];
  deep_read: {
    evidence_trail: DeepReadEvidenceTrailRow[];
    evidence_total: number;
  };
  macro_pulse_collapsed: {
    label: string;
    expand_label: string;
  };
  footer: { left: string; right: string };
}

export interface QaCitation {
  evidence_id: string;
  label: string;
}

export interface QaResponse {
  answer: string;
  cited_evidence_ids: string[];
  citations: QaCitation[];
  insufficient_evidence: boolean;
  validation_passed: boolean;
}

export interface ParseReportStage {
  name: string;
  status: "ok" | "consent_required" | "partial" | "failed";
  detail: string;
}

export interface ParseReport {
  filename: string;
  size_label: string;
  page_count: number;
  uploaded_at_hkt: string;
  parse_seconds: number;
  stages: ParseReportStage[];
  tickers_in_universe: string[];
  tickers_external: string[];
  low_confidence_chunks: { chunk_id: string; page: number; reason: string; preview: string }[];
}
