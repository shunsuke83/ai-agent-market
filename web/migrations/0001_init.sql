-- Core notice rows for internal list/detail + fit columns filled at sync time.
CREATE TABLE IF NOT EXISTS notices (
  bid_no TEXT NOT NULL,
  bid_ord TEXT NOT NULL DEFAULT '000',
  title TEXT,
  org TEXT,
  scope TEXT,
  nature TEXT,
  fields_json TEXT,
  budget_eok REAL,
  notice_date TEXT,
  close_at TEXT,
  open_date TEXT,
  open_at TEXT,
  contract_method TEXT,
  ntce_kind TEXT,
  winner TEXT,
  first_rank TEXT,
  bid_count INTEGER,
  award_amount_eok REAL,
  win_rate_pct REAL,
  g2b_url TEXT,
  soft_excluded INTEGER NOT NULL DEFAULT 0,
  exclude_reason TEXT,
  fit_verdict TEXT,
  fit_score INTEGER,
  fit_reasons_json TEXT,
  payload_json TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (bid_no, bid_ord)
);

CREATE INDEX IF NOT EXISTS idx_notices_close_at ON notices(close_at);
CREATE INDEX IF NOT EXISTS idx_notices_notice_date ON notices(notice_date);
CREATE INDEX IF NOT EXISTS idx_notices_soft ON notices(soft_excluded);
CREATE INDEX IF NOT EXISTS idx_notices_fit ON notices(fit_verdict, fit_score DESC);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT NOT NULL
);
