type Env = { DB: D1Database };

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
  const raw = context.params.id;
  const id = Array.isArray(raw) ? raw[0] : raw;
  if (!id) return json({ error: "missing id" }, 400);

  const m = /^(.+)-(\d{3})$/.exec(id);
  const bidNo = m ? m[1] : id;
  const bidOrd = m ? m[2] : "000";

  const row = await context.env.DB.prepare(
    `SELECT bid_no, bid_ord, title, org, scope, nature, fields_json, budget_eok, notice_date,
      close_at, open_date, open_at, contract_method, ntce_kind, winner, first_rank, bid_count,
      award_amount_eok, win_rate_pct, g2b_url, soft_excluded, exclude_reason, fit_verdict,
      fit_score, fit_reasons_json, payload_json, updated_at
     FROM notices WHERE bid_no = ? AND bid_ord = ?`
  )
    .bind(bidNo, bidOrd)
    .first();

  if (!row) return json({ error: "not_found" }, 404);

  const payload = row.payload_json ? JSON.parse(String(row.payload_json)) : null;
  return json({
    ...row,
    soft_excluded: !!row.soft_excluded,
    fields: row.fields_json ? JSON.parse(String(row.fields_json)) : [],
    fit_reasons: row.fit_reasons_json ? JSON.parse(String(row.fit_reasons_json)) : [],
    payload,
    id: `${row.bid_no}-${row.bid_ord}`,
  });
};
