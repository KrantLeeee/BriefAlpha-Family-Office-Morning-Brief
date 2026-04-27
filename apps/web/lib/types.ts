/**
 * Wire types for the BriefAlpha API. The shapes here mirror
 * `apps/api/briefalpha_api/fixtures/brief.py` and MUST stay in sync as the
 * pipeline replaces the fixture.
 */

export type Mode = "demo" | "live";
export type BriefStatus = "ready" | "generating" | "stale" | "error";
export type DataQuality = "fixture" | "live" | "partial" | "unavailable";
export type LinkKind = "external" | "internal_demo" | "internal_research" | "unavailable";

export interface SystemMeta {
  mode: Mode;
  status: BriefStatus;
  generated_at: string | null;
  last_refreshed_at: string | null;
  data_quality: DataQuality;
}

export interface MacroPulseItem {
  name: string;
  value: string;
  delta: string;
  threshold: string;
  status: "ok" | "watch" | "alert";
}

export interface ReviewMeta {
  reason: "source_conflict" | "portfolio_uncertain" | "threshold_breach" | "data_gap";
  note: string;
  status: "open" | "reviewed";
  reviewed_at: string | null;
  /**
   * How this review was created. `fallback` means the API ran the
   * conservative-fallback path (Stage B LLM was rejected and the
   * judgement is a system placeholder, not an AI-generated insight);
   * the modal copy adapts so users don't think they're confirming an
   * AI judgement when nothing was actually produced.
   *
   * Absent on legacy fixture data and on user-marked overrides where
   * the original judgement wasn't a fallback — treat as undefined.
   */
  kind?: "fallback" | "ai_self_review";
}

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
  source_link?: string;
  link_kind: LinkKind;
  conflict?: boolean;
}

export interface SupplementarySource {
  evidence_id: string;
  label: string;
  source_link?: string;
  link_kind: LinkKind;
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
  review: ReviewMeta | null;
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
  related_evidence_ids: string[];
  is_next: boolean;
}

export interface DeepReadEvidenceTrailRow {
  timestamp: string;
  label: string;
  source_link?: string;
  link_kind?: LinkKind;
  source_tier?: string;
}

export interface SourceHealthRow {
  name: string;
  source_name?: string;
  status: StatusLevel;
  detail: string;
  is_demo: boolean;
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
  macro_pulse: MacroPulseItem[];
  system: SystemMeta;
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
  failure_reason?:
    | "llm_unconfigured"
    | "evidence_insufficient"
    | "out_of_scope"
    | "empty_question"
    | "demo_mode_no_match"
    | "demo_mode_prebaked"
    | "brief_expired";
  is_demo_response?: boolean;
}

export interface ParseReportStage {
  name: string;
  status: "ok" | "consent_required" | "partial" | "failed" | "skipped";
  detail: string;
}

export interface ParseReport {
  status?: "queued" | "parsing" | "reanalyze_queued" | "ok" | "failed";
  filename: string;
  size_label: string;
  page_count: number;
  uploaded_at_hkt: string;
  parse_seconds: number | null;
  stages: ParseReportStage[];
  tickers_in_universe: string[];
  tickers_external: string[];
  ticker_labels?: Record<string, string>;
  low_confidence_chunks: { chunk_id: string; page: number; reason: string; preview: string }[];
}

export interface ResearchFileSummary {
  file_id: string;
  filename: string;
  status: "queued" | "parsing" | "reanalyze_queued" | "ok" | "failed" | string;
  created_at: string | null;
  completed_at: string | null;
}

export interface BriefRefreshStatus {
  brief_id: string;
  status: "idle" | "generating" | "ready" | "error" | string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  cached: boolean;
}
