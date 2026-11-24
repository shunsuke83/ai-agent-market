-- Post-hoc go/skip decisions for fit-score validation (internal).
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  notice_id TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('go', 'skip', 'consortium')),
  fit_score_at_decision INTEGER,
  fit_verdict_at_decision TEXT,
  outcome TEXT CHECK (outcome IN ('won', 'lost', 'first', 'n/a', NULL)),
  notes TEXT,
  budget_eok REAL,
  listed3_present INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_decisions_notice ON decisions(notice_id);
CREATE INDEX IF NOT EXISTS idx_decisions_action ON decisions(action, outcome);
