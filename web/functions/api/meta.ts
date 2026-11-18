type Env = { DB: D1Database };

export const onRequestGet: PagesFunction<Env> = async (context) => {
  const { results } = await context.env.DB.prepare("SELECT key, value, updated_at FROM meta").all();
  const map: Record<string, string> = {};
  for (const r of results || []) {
    map[String(r.key)] = String(r.value);
  }
  return new Response(JSON.stringify({ meta: map, rows: results || [] }), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
};
