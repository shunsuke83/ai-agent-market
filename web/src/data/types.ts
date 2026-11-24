export type FitVerdict = "GO" | "REVIEW" | "NO-GO";

/** Row shown in notice lists. Public (spa/notices.json) and internal (/api/notices) share this shape. */
export type NoticeListItem = {
  id: string;
  bid_no: string;
  bid_ord: string;
  title: string | null;
  org: string | null;
  scope?: string | null;
  nature?: string | null;
  fields?: string[];
  budget_eok: number | null;
  notice_date: string | null;
  close_at: string | null;
  open_date?: string | null;
  contract_method?: string | null;
  soft_excluded?: boolean;
  exclude_reason?: string | null;
  fit_verdict?: FitVerdict | null;
  fit_score?: number | null;
  fit_reasons?: string[];
  winner?: string | null;
  first_rank?: string | null;
  bid_count?: number | null;
  award_amount_eok?: number | null;
  win_rate_pct?: number | null;
  g2b_url?: string | null;
};

export type NoticeDetail = NoticeListItem & {
  open_at?: string | null;
  ntce_kind?: string | null;
  winner?: string | null;
  first_rank?: string | null;
  bid_count?: number | null;
  award_amount_eok?: number | null;
  win_rate_pct?: number | null;
  g2b_url?: string | null;
  updated_at?: string | null;
  payload?: Record<string, unknown> | null;
};

export type NoticeListQuery = {
  q?: string;
  fit?: FitVerdict | "";
  openOnly?: boolean;
  includeExcluded?: boolean;
  limit?: number;
  offset?: number;
};

export type NoticeListResult = {
  total: number;
  items: NoticeListItem[];
};

/** Precomputed dashboard summary (public: /data/spa/summary.json). */
export type SpaSummary = {
  generated_at?: string | null;
  total_notices?: number;
  open_notices?: number;
  new_notices?: number;
  go_count?: number;
  review_count?: number;
  closing_soon?: number;
  band_count?: number;
  new?: NoticeListItem[];
  fit?: NoticeListItem[];
  closing?: NoticeListItem[];
};

export type Prespec = {
  prespec_no: string;
  title: string | null;
  org: string | null;
  registered_at: string | null;
  registered_date?: string | null;
  opinion_close_at: string | null;
  asign_budget_eok: number | null;
  scope?: string | null;
  nature?: string | null;
  fields?: string[];
  bid_nos?: string[];
  spec_files?: string[];
  biz_div?: string | null;
  order_org?: string | null;
};

export type OrderPlan = Record<string, unknown>;
export type Firm = Record<string, unknown>;
export type Bidder = Record<string, unknown>;
export type Agency = Record<string, unknown>;

export type CompetitorFirm = {
  name: string;
  bizno?: string;
  group?: "listed" | "outside" | string;
  type?: string;
  own_model?: string;
  procurement?: string;
  region?: string | null;
  employees?: number | null;
  homepage?: string | null;
  bids?: number;
  wins?: number;
  award_amount_eok?: number | null;
  gen_agent_bids?: number;
  bid_to_budget_median_pct?: number | null;
  largest_win?: {
    title?: string | null;
    org?: string | null;
    award_amount_eok?: number | null;
    open_date?: string | null;
  } | null;
  faced?: { name: string; count: number; beat?: number; lost?: number }[];
  faced_listed?: { name: string; count: number }[];
};

export type CompetitorsPayload = {
  generated_at?: string | null;
  analysis?: {
    title?: string;
    as_of?: string;
    author?: string;
    lede?: string;
    bullets?: string[];
    sections?: { id?: string; title?: string; paragraphs?: string[] }[];
    limitations?: string[];
    sources?: string[];
    head_to_head_notes?: { pair?: string[]; note?: string }[];
  };
  summary?: {
    firms?: number;
    listed?: number;
    outside?: number;
    bids?: number;
    wins?: number;
    award_amount_eok?: number;
  };
  type_rollups?: {
    type: string;
    firms: number;
    bids: number;
    wins: number;
    award_amount_eok: number;
  }[];
  firms?: CompetitorFirm[];
  head_to_head?: {
    a: string;
    b: string;
    meetings: number;
    a_ahead: number;
    b_ahead: number;
  }[];
};

export type MetaInfo = {
  stamp: string | null;
};

/** Optional datasets: `null` means the current mode does not provide it. */
export type DataClient = {
  getMeta(): Promise<MetaInfo>;
  getSummary(): Promise<SpaSummary | null>;
  listNotices(query?: NoticeListQuery): Promise<NoticeListResult>;
  getNotice(id: string): Promise<NoticeDetail | null>;
  getPrespecs(): Promise<Prespec[] | null>;
  getOrderPlans(): Promise<OrderPlan[] | null>;
  getFirms(): Promise<Firm[] | null>;
  getCompetitors(): Promise<CompetitorsPayload | null>;
  getBidders(): Promise<Bidder[] | null>;
  getAgencies(): Promise<Agency[] | null>;
  getReports(): Promise<Record<string, unknown> | null>;
};
