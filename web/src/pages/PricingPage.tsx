import { Link } from "react-router-dom";
import { useMemo, useState } from "react";
import {
  Button,
  Card,
  DashboardPageLayout,
  DataTable,
  EmptyState,
  ListControl,
  StatCard,
  Text,
  type DataTableColumn,
} from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import FitBadge from "../components/FitBadge";
import { dataClient, type NoticeBidder, type NoticeListItem } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { usePaged } from "../hooks/usePaged";
import { downloadCsv } from "../lib/csv";
import { fmtEok, fmtNum, fmtWinRate } from "../lib/format";

type SortKey = "open" | "bids";

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function winnerBidder(n: NoticeListItem): NoticeBidder | null {
  const list = n.bidders ?? [];
  if (!list.length) return null;
  if (n.winner) {
    const byName = list.find((b) => (b.name || "").includes(n.winner!) || (n.winner || "").includes(b.name || ""));
    if (byName) return byName;
  }
  return list.find((b) => b.rank === 1) ?? list[0] ?? null;
}

function isRatePct(v: number | null | undefined): boolean {
  return v != null && v >= 50 && v <= 110;
}

type PricingRow = NoticeListItem & {
  winner_tech?: number | null;
  winner_price_score?: number | null;
  winner_bid_rate?: number | null;
};

export default function PricingPage() {
  const [search, setSearch] = useState("");
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const [negotiatedOnly, setNegotiatedOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("open");
  const q = useDebounced(search);
  const state = useAsync(
    () => dataClient.listNotices({ openOnly: false, includeExcluded: true, limit: 5000 }),
    [],
  );

  const enriched = useMemo(() => {
    if (state.status !== "ready") return [] as PricingRow[];
    return state.data.items
      .filter(
        (n) =>
          n.bid_count != null ||
          n.win_rate_pct != null ||
          n.award_to_budget_pct != null ||
          n.winner ||
          (n.bidders && n.bidders.length > 0),
      )
      .map((n) => {
        const w = winnerBidder(n);
        const rate = w?.rate_pct;
        return {
          ...n,
          winner_tech: w?.tech_score ?? null,
          winner_price_score: w?.price_score ?? (rate != null && rate < 50 ? rate : null),
          winner_bid_rate: isRatePct(rate) ? rate : null,
        } as PricingRow;
      });
  }, [state]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let list = enriched;
    if (!includeExcluded) list = list.filter((n) => !n.soft_excluded);
    if (negotiatedOnly) {
      list = list.filter((n) => n.winner_tech != null || n.winner_price_score != null);
    }
    if (needle) {
      list = list.filter((n) => {
        const hay = `${n.title ?? ""} ${n.org ?? ""} ${n.winner ?? ""} ${n.nature ?? ""}`.toLowerCase();
        return hay.includes(needle);
      });
    }
    return [...list].sort((a, b) => {
      if (sortKey === "bids") {
        const byBids = (b.bid_count ?? 0) - (a.bid_count ?? 0);
        if (byBids) return byBids;
      }
      const byDate = (b.open_date ?? b.notice_date ?? "").localeCompare(a.open_date ?? a.notice_date ?? "");
      if (byDate) return byDate;
      return (b.bid_count ?? 0) - (a.bid_count ?? 0);
    });
  }, [enriched, q, includeExcluded, negotiatedOnly, sortKey]);

  const paged = usePaged(rows, 50, `${q}|${includeExcluded}|${negotiatedOnly}|${sortKey}`);

  const stats = useMemo(() => {
    const live = includeExcluded ? enriched : enriched.filter((n) => !n.soft_excluded);
    const counts = live.map((n) => n.bid_count).filter((c): c is number => c != null);
    const rates = live
      .map((n) => n.win_rate_pct ?? n.award_to_budget_pct)
      .filter((r): r is number => r != null && r >= 50 && r <= 110);
    const withTech = live.filter((n) => n.winner_tech != null).length;
    const solo = counts.filter((c) => c === 1).length;
    return {
      notices: live.length,
      medianBids: median(counts),
      medianRate: median(rates),
      withTech,
      soloPct: counts.length ? Math.round((100 * solo) / counts.length) : null,
    };
  }, [enriched, includeExcluded]);

  const columns: DataTableColumn<PricingRow>[] = [
    { key: "open", header: "개찰일", render: (r) => r.open_date ?? r.notice_date ?? "-" },
    {
      key: "fit",
      header: "적합도",
      render: (r) => <FitBadge verdict={r.fit_verdict} score={r.fit_score} />,
    },
    {
      key: "title",
      header: "사업명",
      render: (r) => (
        <span>
          <Link to={`/bids/${r.id}`}>{r.title ?? r.bid_no}</Link>
          {r.soft_excluded ? (
            <Text as="span" variant="muted">
              {" "}
              · 제외
            </Text>
          ) : null}
          {r.hw_included ? (
            <Text as="span" variant="muted">
              {" "}
              · HW
            </Text>
          ) : null}
        </span>
      ),
    },
    { key: "org", header: "수요기관", render: (r) => r.org ?? "-" },
    { key: "nature", header: "성격", render: (r) => r.nature ?? "-" },
    {
      key: "status",
      header: "상태",
      render: (r) => r.status ?? (r.winner ? "낙찰" : r.first_rank ? "1순위" : "-"),
    },
    {
      key: "bids",
      header: "투찰 수",
      align: "right",
      render: (r) => fmtNum(r.bid_count ?? undefined),
    },
    {
      key: "tech",
      header: "낙찰 기술점",
      align: "right",
      render: (r) => (r.winner_tech != null ? r.winner_tech.toFixed(2) : "-"),
    },
    {
      key: "price",
      header: "낙찰 가격점",
      align: "right",
      render: (r) => (r.winner_price_score != null ? r.winner_price_score.toFixed(3) : "-"),
    },
    {
      key: "rate",
      header: "낙찰률",
      align: "right",
      render: (r) => fmtWinRate(r.win_rate_pct, r.award_to_budget_pct),
    },
    {
      key: "award",
      header: "낙찰(억)",
      align: "right",
      render: (r) => fmtEok(r.award_amount_eok),
    },
    { key: "budget", header: "예산(억)", align: "right", render: (r) => fmtEok(r.budget_eok) },
    {
      key: "winner",
      header: "낙찰자",
      render: (r) => {
        const name = r.winner || (r.first_rank ? `${r.first_rank} (1순위)` : null);
        if (!name) return "-";
        return <Link to={`/bidders?q=${encodeURIComponent(r.winner || r.first_rank || "")}`}>{name}</Link>;
      },
    },
  ];

  return (
    <DashboardPageLayout
      title="투찰·경쟁"
      description="개찰일·투찰 수·낙찰률과 협상계약 기술·가격점수를 함께 봅니다. 경비·GPU 구매 등 목록 제외분은 기본으로 숨깁니다."
      stats={
        <>
          <StatCard label="개찰 공고" value={fmtNum(stats.notices)} />
          <StatCard
            label="투찰 수 중앙값"
            value={stats.medianBids != null ? `${stats.medianBids.toFixed(0)}곳` : "-"}
            hint={stats.soloPct != null ? `단독 ${stats.soloPct}%` : undefined}
          />
          <StatCard
            label="낙찰률 중앙값"
            value={stats.medianRate != null ? `${stats.medianRate.toFixed(1)}%` : "-"}
          />
          <StatCard label="기술점수 공개" value={fmtNum(stats.withTech)} hint="협상계약 개찰분" />
        </>
      }
    >
      <AsyncView state={state}>
        {() => (
          <Card>
            <div style={{ padding: 16, display: "grid", gap: 12 }}>
              <ListControl search="사업명·기관·낙찰자" searchValue={search} onSearchChange={setSearch} />
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={includeExcluded}
                    onChange={(e) => setIncludeExcluded(e.target.checked)}
                  />
                  <Text variant="muted">제외분 포함 (GPU·경비 등)</Text>
                </label>
                <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={negotiatedOnly}
                    onChange={(e) => setNegotiatedOnly(e.target.checked)}
                  />
                  <Text variant="muted">기술·가격점수 있는 건만</Text>
                </label>
                <Text variant="muted">정렬:</Text>
                {(
                  [
                    ["open", "개찰일"],
                    ["bids", "투찰 수"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setSortKey(id)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      border:
                        sortKey === id
                          ? "1px solid var(--color-action-primary-default, #7540ee)"
                          : "1px solid #ddd",
                      background: sortKey === id ? "rgba(117,64,238,0.08)" : "transparent",
                      cursor: "pointer",
                    }}
                  >
                    {label}
                  </button>
                ))}
                <Button
                  variant="secondary"
                  onClick={() =>
                    downloadCsv(
                      "pricing.csv",
                      ["개찰일", "기관", "사업명", "투찰수", "기술점", "가격점", "낙찰률", "예산억", "낙찰자"],
                      rows.map((n) => [
                        n.open_date ?? n.notice_date,
                        n.org,
                        n.title,
                        n.bid_count,
                        n.winner_tech,
                        n.winner_price_score,
                        n.win_rate_pct ?? n.award_to_budget_pct,
                        n.budget_eok,
                        n.winner || n.first_rank,
                      ]),
                    )
                  }
                >
                  CSV
                </Button>
              </div>
              <Text variant="muted">
                {paged.shown}/{paged.total}건 표시
                {!includeExcluded ? " · 제외분 숨김" : ""}
                {negotiatedOnly ? " · 점수 공개분만" : ""}
              </Text>
              {rows.length === 0 ? (
                <EmptyState title="조건에 맞는 투찰 데이터가 없습니다" />
              ) : (
                <>
                  <DataTable columns={columns} rows={paged.page} />
                  {paged.hasMore ? (
                    <Button variant="secondary" onClick={paged.more}>
                      더 보기
                    </Button>
                  ) : null}
                </>
              )}
            </div>
          </Card>
        )}
      </AsyncView>
    </DashboardPageLayout>
  );
}
