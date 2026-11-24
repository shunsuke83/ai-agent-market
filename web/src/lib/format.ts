export function fmtEok(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return "-";
  return `${Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}억`;
}

export function fmtDateTime(v: string | null | undefined): string {
  return v ? v.slice(0, 16) : "-";
}

export function fmtNum(v: number | null | undefined): string {
  return v == null ? "-" : v.toLocaleString("ko-KR");
}

/** Display 낙찰률: prefer win_rate_pct, else award_to_budget_pct. */
export function fmtWinRate(
  winRate: number | null | undefined,
  awardToBudget?: number | null | undefined,
): string {
  const v = winRate ?? awardToBudget;
  if (v == null || !Number.isFinite(Number(v))) return "-";
  return `${Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

/** 나라장터 원문 URL — stored or synthesized from bid_no/ord. */
export function g2bUrl(n: {
  g2b_url?: string | null;
  bid_no?: string | null;
  bid_ord?: string | null;
}): string | null {
  const stored = (n.g2b_url || "").trim();
  if (stored) return stored;
  const bid = (n.bid_no || "").trim();
  if (!bid) return null;
  const ord = String(n.bid_ord || "000").padStart(3, "0");
  return `https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=${encodeURIComponent(bid)}&bidPbancOrd=${encodeURIComponent(ord)}`;
}
