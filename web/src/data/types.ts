export type FitVerdict = "GO" | "REVIEW" | "NO-GO";

export type NoticeBidder = {
  rank?: number | null;
  name?: string | null;
  bizno?: string | null;
  amount_eok?: number | null;
  rate_pct?: number | null;
  price_score?: number | null;
  tech_score?: number | null;
  total_score?: number | null;
};

export type NoticePayload = {
  notice_files?: { name?: string; url?: string }[];
  price_rate?: number | null;
  tech_rate?: number | null;
  award_method?: string | null;
  industry_limit?: string | null;
  participation_limit?: string | null;
  record_limit?: string | null;
  joint_method?: string | null;
  prespec_no?: string | null;
  plan_no?: string | null;
  biz?: string | null;
  asign_budget_eok?: number | null;
  presmpt_eok?: number | null;
  base_amount_eok?: number | null;
  budget_kind?: string | null;
  source?: string | null;
  bidders?: NoticeBidder[];
  [key: string]: unknown;
};

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
  open_at?: string | null;
  contract_method?: string | null;
  ntce_kind?: string | null;
  soft_excluded?: boolean;
  exclude_reason?: string | null;
  hw_included?: boolean;
  fit_verdict?: FitVerdict | null;
  fit_score?: number | null;
  fit_reasons?: string[];
  winner?: string | null;
  first_rank?: string | null;
  second?: string | null;
  status?: string | null;
  bid_count?: number | null;
  award_amount_eok?: number | null;
  award_to_budget_pct?: number | null;
  win_rate_pct?: number | null;
  g2b_url?: string | null;
  bidders?: NoticeBidder[];
  payload?: NoticePayload | null;
};

export type NoticeDetail = NoticeListItem & {
  updated_at?: string | null;
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

export type BidderRival = {
  bizno: string;
  name: string;
  faced: number;
  ahead: number;
  behind: number;
};

export type BidderChange = {
  date?: string;
  text?: string;
  confirmed?: boolean;
};

export type BidderHistoryItem = {
  notice_idx: number;
  rank?: number | null;
  rate_pct?: number | null;
  price_score?: number | null;
  amount_eok?: number | null;
};

export type Bidder = {
  bizno: string;
  name?: string;
  firm?: string;
  bidder?: string;
  region?: string | null;
  bids?: number;
  bid_count?: number;
  wins?: number;
  win_count?: number;
  firsts?: number;
  avg_win_rate?: number | null;
  median_bid_rate?: number | null;
  bid_rate_n?: number;
  median_budget_share?: number | null;
  budget_share_n?: number;
  history?: BidderHistoryItem[];
  rivals?: BidderRival[];
  changes?: BidderChange[];
};

export type BidderNotice = {
  date?: string | null;
  org?: string;
  title?: string | null;
  budget_eok?: number | null;
  id?: string | null;
  winner_bizno?: string;
  status?: string | null;
  bidder_count?: number;
};

export type BiddersPayload = {
  generated_at?: string | null;
  summary?: { firms?: number; notices?: number; bids?: number; wins?: number };
  firms?: Bidder[];
  bidders?: Bidder[];
  notices?: BidderNotice[];
};

export type AgencyWinner = {
  name: string;
  bizno?: string | null;
  wins: number;
  award_amount_eok?: number | null;
};

export type Agency = {
  name: string;
  org?: string;
  notices?: number;
  count?: number;
  wins?: number;
  budget_eok?: number | null;
  total_budget_eok?: number | null;
  award_amount_eok?: number | null;
  award_known?: number;
  gen_agent_notices?: number;
  avg_bid_count?: number | null;
  latest_date?: string | null;
  top_winners?: AgencyWinner[];
};

export type AgencyNotice = {
  date?: string | null;
  org: string;
  title?: string | null;
  budget_eok?: number | null;
  id?: string | null;
  winner?: string | null;
  winner_bizno?: string | null;
  award_amount_eok?: number | null;
  status?: string | null;
  bid_count?: number | null;
  gen_agent?: boolean;
};

export type AgenciesPayload = {
  generated_at?: string | null;
  summary?: { orgs?: number; notices?: number; wins?: number };
  agencies?: Agency[];
  notices?: AgencyNotice[];
};

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

export type ConsortiumFirmRollup = {
  name?: string | null;
  bizno?: string | null;
  contracts?: number;
  amount_eok?: number | null;
  listed?: boolean;
};

export type ConsortiumEdge = {
  lead_name?: string | null;
  lead_bizno?: string | null;
  member_name?: string | null;
  member_bizno?: string | null;
  count?: number;
  amount_eok_sum?: number | null;
  sample_contract_no?: string | null;
  member_listed?: boolean;
  lead_listed?: boolean;
};

export type ConsortiumJointContract = {
  contract_no?: string | null;
  title?: string | null;
  org?: string | null;
  amount_eok?: number | null;
  signed_date?: string | null;
  bid_no?: string | null;
  url?: string | null;
  firms?: { name?: string; role?: string | null; share?: number | null; bizno?: string | null }[];
};

export type ConsortiumPayload = {
  generated_at?: string | null;
  summary?: {
    contracts?: number;
    multi_firm?: number;
    large_joint?: number;
    large_joint_min_eok?: number;
    external_lead_to_listed?: number;
    xenon_lead?: number;
    xenon_member?: number;
  };
  edges?: ConsortiumEdge[];
  leaders?: ConsortiumFirmRollup[];
  members?: ConsortiumFirmRollup[];
  large_joint?: ConsortiumJointContract[];
  xenon?: {
    bizno?: string;
    lead?: number;
    member?: number;
    contracts?: {
      contract_no?: string | null;
      title?: string | null;
      org?: string | null;
      amount_eok?: number | null;
      role?: string | null;
      share?: number | null;
      signed_date?: string | null;
    }[];
  };
};

export type DecisionRow = {
  notice_id: string;
  decided_at?: string | null;
  action?: "go" | "skip" | "consortium" | string;
  fit_score_at_decision?: number | null;
  fit_verdict_at_decision?: string | null;
  outcome?: "won" | "lost" | "first" | "n/a" | string | null;
  notes?: string | null;
  budget_eok?: number | null;
  listed3_present?: boolean;
};

export type DecisionsPayload = {
  schema_version?: number;
  company?: string;
  bizno?: string;
  as_of?: string | null;
  notes?: string | null;
  decisions?: DecisionRow[];
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
    auto?: number;
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
  getBidders(): Promise<BiddersPayload | null>;
  getAgencies(): Promise<AgenciesPayload | null>;
  getConsortium(): Promise<ConsortiumPayload | null>;
  getDecisions(): Promise<DecisionsPayload | null>;
  getReports(): Promise<Record<string, unknown> | null>;
};
