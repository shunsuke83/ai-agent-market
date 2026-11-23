import type {
  DataClient,
  NoticeDetail,
  NoticeListItem,
  NoticeListQuery,
  NoticeListResult,
  SpaSummary,
} from "./types";

async function api<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return (await res.json()) as T;
}

type ApiList = { total: number; items: NoticeListItem[] };

function qs(query: NoticeListQuery): string {
  const p = new URLSearchParams();
  const q = query.q?.trim();
  if (q) p.set("q", q);
  if (query.fit) p.set("fit", query.fit);
  if (query.includeExcluded) p.set("excluded", "1");
  if (query.openOnly === false) p.set("open", "0");
  p.set("limit", String(Math.min(query.limit ?? 100, 200)));
  p.set("offset", String(query.offset ?? 0));
  return p.toString();
}

export const internalClient: DataClient = {
  async getMeta() {
    try {
      const data = await api<{ meta?: Record<string, string> }>("/api/meta");
      const stamp = data.meta?.synced_at || data.meta?.collect_success_at || null;
      return { stamp: stamp ? `D1 sync ${stamp}` : null };
    } catch {
      return { stamp: null };
    }
  },

  /** No precomputed summary in internal mode: derive it from a few list queries. */
  async getSummary(): Promise<SpaSummary> {
    const [all, go, review, byClose] = await Promise.all([
      api<ApiList>(`/api/notices?${qs({ limit: 1 })}`),
      api<ApiList>(`/api/notices?${qs({ fit: "GO", limit: 8 })}`),
      api<ApiList>(`/api/notices?${qs({ fit: "REVIEW", limit: 1 })}`),
      api<ApiList>(`/api/notices?${qs({ limit: 200 })}`),
    ]);
    const closing = [...byClose.items]
      .filter((n) => n.close_at)
      .sort((a, b) => (a.close_at ?? "").localeCompare(b.close_at ?? ""))
      .slice(0, 8);
    const newest = [...byClose.items]
      .sort((a, b) => (b.notice_date ?? "").localeCompare(a.notice_date ?? ""))
      .slice(0, 8);
    return {
      open_notices: all.total,
      go_count: go.total,
      review_count: review.total,
      new: newest,
      fit: go.items,
      closing,
    };
  },

  async listNotices(query: NoticeListQuery = {}): Promise<NoticeListResult> {
    const data = await api<ApiList>(`/api/notices?${qs({ ...query, openOnly: query.openOnly ?? true })}`);
    return { total: data.total, items: data.items };
  },

  async getNotice(id: string): Promise<NoticeDetail | null> {
    const res = await fetch(`/api/notices/${encodeURIComponent(id)}`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`/api/notices/${id} → HTTP ${res.status}`);
    return (await res.json()) as NoticeDetail;
  },

  // Not served by the D1 API (public JSON only).
  getPrespecs: async () => null,
  getOrderPlans: async () => null,
  getFirms: async () => null,
  getBidders: async () => null,
  getAgencies: async () => null,
  getReports: async () => null,
};
