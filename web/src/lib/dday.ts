/** KST wall-clock stamp comparable to notice close_at ("YYYY-MM-DD HH:MM"). */
export function nowKstStamp(): string {
  const d = new Date(Date.now() + 9 * 3600 * 1000);
  return d.toISOString().slice(0, 16).replace("T", " ");
}

/** Days until close_at (date part). null if missing/past/unparseable. */
export function ddayLabel(closeAt: string | null | undefined, now = nowKstStamp()): string | null {
  if (!closeAt) return null;
  const day = closeAt.slice(0, 10);
  const today = now.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !/^\d{4}-\d{2}-\d{2}$/.test(today)) return null;
  if (closeAt < now) return null;
  const t0 = Date.parse(`${today}T00:00:00+09:00`);
  const t1 = Date.parse(`${day}T00:00:00+09:00`);
  if (!Number.isFinite(t0) || !Number.isFinite(t1)) return null;
  const days = Math.round((t1 - t0) / 86400000);
  if (days < 0) return null;
  if (days === 0) return "D-Day";
  return `D-${days}`;
}
