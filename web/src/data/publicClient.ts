import type {
  AgenciesPayload,
  Agency,
  Bidder,
  BiddersPayload,
  CompetitorsPayload,
  DataClient,
  Firm,
  NoticeDetail,
  NoticeListItem,
  NoticeListQuery,
  NoticeListResult,
  OrderPlan,
  Prespec,
  SpaSummary,
} from "./types";

const base = import.meta.env.BASE_URL.replace(/\/$/, "");

async function fetchJson<T>(path: string): Promise<T | null> {
  const res = await fetch(`${base}${path}`, { headers: { accept: "application/json" } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  const ct = res.headers.get("content-type") || "";
  // SPA fallback (_redirects) answers missing files with index.html; treat as not found.
  if (ct.includes("text/html")) return null;
  return (await res.json()) as T;
}

function withId<T extends { id?: string; bid_no?: string; bid_ord?: string }>(n: T): T & { id: string } {
  return { ...n, id: n.id ?? `${n.bid_no ?? ""}-${n.bid_ord ?? "000"}` };
}

function unwrapList<T>(raw: unknown, key: string): T[] | null {
  if (raw == null) return null;
  if (Array.isArray(raw)) return raw as T[];
  const v = (raw as Record<string, unknown>)[key];
  return Array.isArray(v) ? (v as T[]) : [];
}

let noticesCache: Promise<NoticeListItem[]> | null = null;

function loadAllNotices(): Promise<NoticeListItem[]> {
  if (!noticesCache) {
    noticesCache = fetchJson<unknown>("/data/spa/notices.json")
      .then((raw) => (unwrapList<NoticeListItem>(raw, "notices") ?? []).map(withId))
      .catch((e) => {
        noticesCache = null;
        throw e;
      });
  }
  return noticesCache;
}

const FIT_ORDER: Record<string, number> = { GO: 0, REVIEW: 1, "NO-GO": 2 };

function nowKst(): string {
  // "YYYY-MM-DD HH:MM" in KST, comparable to close_at strings.
  const d = new Date(Date.now() + 9 * 3600 * 1000);
  return d.toISOString().slice(0, 16).replace("T", " ");
}

export const publicClient: DataClient = {
  async getMeta() {
    const s = await fetchJson<SpaSummary>("/data/spa/summary.json").catch(() => null);
    return { stamp: s?.generated_at ?? null };
  },

  getSummary() {
    return fetchJson<SpaSummary>("/data/spa/summary.json");
  },

  async listNotices(query: NoticeListQuery = {}): Promise<NoticeListResult> {
    const all = await loadAllNotices();
    const q = (query.q ?? "").trim().toLowerCase();
    const now = nowKst();
    let items = all.filter((n) => {
      if (!query.includeExcluded && n.soft_excluded) return false;
      if (query.openOnly && !(n.close_at && n.close_at >= now)) return false;
      if (query.fit && n.fit_verdict !== query.fit) return false;
      if (q) {
        const hay = `${n.title ?? ""} ${n.org ?? ""} ${n.bid_no ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    items = [...items].sort((a, b) => {
      const fa = FIT_ORDER[a.fit_verdict ?? ""] ?? 9;
      const fb = FIT_ORDER[b.fit_verdict ?? ""] ?? 9;
      if (fa !== fb) return fa - fb;
      const sa = a.fit_score ?? -1;
      const sb = b.fit_score ?? -1;
      if (sa !== sb) return sb - sa;
      return (a.close_at ?? "9").localeCompare(b.close_at ?? "9");
    });
    const total = items.length;
    const offset = query.offset ?? 0;
    const limit = query.limit ?? total;
    return { total, items: items.slice(offset, offset + limit) };
  },

  async getNotice(id: string): Promise<NoticeDetail | null> {
    const d = await fetchJson<NoticeDetail>(`/data/spa/notices/${encodeURIComponent(id)}.json`);
    if (d) return withId(d);
    // Fallback: list payload already carries detail fields used by BidDetailPage.
    const all = await loadAllNotices();
    const hit = all.find((n) => n.id === id || `${n.bid_no}-${n.bid_ord}` === id);
    return hit ? withId(hit) : null;
  },

  async getPrespecs() {
    return unwrapList<Prespec>(await fetchJson<unknown>("/data/prespecs.json"), "prespecs");
  },

  async getOrderPlans() {
    return unwrapList<OrderPlan>(await fetchJson<unknown>("/data/order_plans.json"), "plans");
  },

  async getFirms() {
    const raw = await fetchJson<unknown>("/data/firms.json");
    if (!raw) return [];
    if (Array.isArray(raw)) return raw as Firm[];
    const firms = (raw as Record<string, unknown>).firms;
    if (Array.isArray(firms)) return firms as Firm[];
    if (firms && typeof firms === "object") return Object.values(firms as Record<string, Firm>);
    return [];
  },

  getCompetitors() {
    return fetchJson<CompetitorsPayload>("/data/spa/competitors.json");
  },

  async getBidders(): Promise<BiddersPayload | null> {
    const spa = await fetchJson<BiddersPayload>("/data/spa/bidders-index.json");
    if (spa && (Array.isArray(spa.firms) || Array.isArray(spa.bidders))) {
      return {
        ...spa,
        firms: spa.firms ?? spa.bidders ?? [],
        notices: spa.notices ?? [],
      };
    }
    // Legacy compact firms map → thin payload (no shared notices).
    const raw = await fetchJson<Record<string, unknown>>("/data/bidders.json");
    if (!raw) return null;
    const firmsMap = raw.firms;
    if (firmsMap && typeof firmsMap === "object" && !Array.isArray(firmsMap)) {
      const firms: Bidder[] = Object.entries(firmsMap as Record<string, unknown>).map(
        ([bizno, v]) => {
          const row = Array.isArray(v) ? v : [];
          return {
            bizno,
            name: String(row[0] ?? bizno),
            region: String(row[1] ?? ""),
            bids: Array.isArray(row[2]) ? row[2].length : 0,
            wins: 0,
            history: [],
          };
        },
      );
      firms.sort((a, b) => Number(b.bids ?? 0) - Number(a.bids ?? 0));
      return {
        summary: { firms: firms.length, notices: 0, bids: 0, wins: 0 },
        firms,
        notices: [],
      };
    }
    const list = unwrapList<Bidder>(raw, "bidders") ?? [];
    return { firms: list, notices: [] };
  },

  async getAgencies(): Promise<AgenciesPayload | null> {
    const spa = await fetchJson<AgenciesPayload>("/data/spa/agencies-index.json");
    if (spa && Array.isArray(spa.agencies)) return spa;
    // Legacy agencies.json: compact notice rows → build a minimal payload.
    const raw = await fetchJson<unknown>("/data/agencies.json");
    if (!raw) return null;
    const noticesRaw = unwrapList<unknown>(raw, "notices") ?? [];
    const byOrg = new Map<string, Agency>();
    for (const row of noticesRaw) {
      if (!Array.isArray(row)) continue;
      const org = String(row[1] ?? "");
      if (!org) continue;
      const cur = byOrg.get(org) || { name: org, notices: 0, wins: 0, budget_eok: 0 };
      cur.notices = Number(cur.notices ?? 0) + 1;
      const budget = Number(row[3] ?? 0);
      if (Number.isFinite(budget)) cur.budget_eok = Number(cur.budget_eok ?? 0) + budget;
      if (row[8] === "낙찰") cur.wins = Number(cur.wins ?? 0) + 1;
      byOrg.set(org, cur);
    }
    const agencies = [...byOrg.values()].sort(
      (a, b) => Number(b.notices ?? 0) - Number(a.notices ?? 0),
    );
    return {
      summary: {
        orgs: agencies.length,
        notices: noticesRaw.length,
        wins: agencies.reduce((s, a) => s + Number(a.wins ?? 0), 0),
      },
      agencies,
      notices: [],
    };
  },

  getReports() {
    return fetchJson<Record<string, unknown>>("/data/reports.json");
  },
};
