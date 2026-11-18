type Env = { DB: D1Database };

type NoticeRow = {
  bid_no: string;
  bid_ord: string;
  title: string | null;
  org: string | null;
  scope: string | null;
  nature: string | null;
  budget_eok: number | null;
  notice_date: string | null;
  close_at: string | null;
  open_date: string | null;
  contract_method: string | null;
  soft_excluded: number;
  exclude_reason: string | null;
  fit_verdict: string | null;
  fit_score: number | null;
  fit_reasons_json: string | null;
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export const onRequestGet: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  const q = url.searchParams.get("q")?.trim() || "";
  const showExcluded = url.searchParams.get("excluded") === "1";
  const openOnly = url.searchParams.get("open") !== "0";
  const fit = url.searchParams.get("fit"); // GO|REVIEW|NO-GO
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit") || 80), 1), 200);
  const offset = Math.max(Number(url.searchParams.get("offset") || 0), 0);

  const where: string[] = [];
  const params: (string | number)[] = [];

  if (!showExcluded) {
    where.push("soft_excluded = 0");
  }
  if (openOnly) {
    where.push("close_at IS NOT NULL AND close_at >= datetime('now', 'localtime')");
  }
  if (fit) {
    where.push("fit_verdict = ?");
    params.push(fit);
  }
  if (q) {
    where.push("(title LIKE ? OR org LIKE ? OR bid_no LIKE ?)");
    const like = `%${q}%`;
    params.push(like, like, like);
  }

  const whereSql = where.length ? `WHERE ${where.join(" AND ")}` : "";
  const order =
    "ORDER BY CASE fit_verdict WHEN 'GO' THEN 0 WHEN 'REVIEW' THEN 1 WHEN 'NO-GO' THEN 2 ELSE 9 END, fit_score DESC, close_at ASC";

  const countSql = `SELECT COUNT(*) AS n FROM notices ${whereSql}`;
  const listSql = `SELECT bid_no, bid_ord, title, org, scope, nature, budget_eok, notice_date, close_at, open_date,
    contract_method, soft_excluded, exclude_reason, fit_verdict, fit_score, fit_reasons_json
    FROM notices ${whereSql} ${order} LIMIT ? OFFSET ?`;

  const countRow = await context.env.DB.prepare(countSql)
    .bind(...params)
    .first<{ n: number }>();
  const { results } = await context.env.DB.prepare(listSql)
    .bind(...params, limit, offset)
    .all<NoticeRow>();

  return json({
    total: countRow?.n ?? 0,
    limit,
    offset,
    items: (results || []).map((r) => ({
      ...r,
      soft_excluded: !!r.soft_excluded,
      fit_reasons: r.fit_reasons_json ? JSON.parse(r.fit_reasons_json) : [],
      id: `${r.bid_no}-${r.bid_ord}`,
    })),
  });
};
