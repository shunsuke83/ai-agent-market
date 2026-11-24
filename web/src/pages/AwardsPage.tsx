import { Link } from "react-router-dom";
import { Button, DataTable, EmptyState, ListControl, ListPageLayout } from "@genonai/admin-design-system";
import { useMemo, useState } from "react";
import AsyncView from "../components/AsyncView";
import FitBadge from "../components/FitBadge";
import { dataClient, type NoticeListItem } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { usePaged } from "../hooks/usePaged";
import { downloadCsv } from "../lib/csv";
import { ddayLabel } from "../lib/dday";
import { fmtEok, fmtWinRate } from "../lib/format";

type SortKey = "open" | "award";

export default function AwardsPage() {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("open");
  const q = useDebounced(search);
  const state = useAsync(
    () => dataClient.listNotices({ openOnly: false, includeExcluded: true, limit: 5000 }),
    [],
  );

  const rows = useMemo(() => {
    if (state.status !== "ready") return [] as NoticeListItem[];
    const needle = q.trim().toLowerCase();
    return state.data.items
      .filter((n) => n.winner || n.first_rank)
      .filter((n) => {
        if (!needle) return true;
        const hay = `${n.title ?? ""} ${n.org ?? ""} ${n.winner ?? ""} ${n.bid_no}`.toLowerCase();
        return hay.includes(needle);
      })
      .sort((a, b) => {
        if (sortKey === "award") {
          return (b.award_amount_eok ?? b.budget_eok ?? 0) - (a.award_amount_eok ?? a.budget_eok ?? 0);
        }
        const byDate = (b.open_date ?? "").localeCompare(a.open_date ?? "");
        if (byDate) return byDate;
        return (b.award_amount_eok ?? b.budget_eok ?? 0) - (a.award_amount_eok ?? a.budget_eok ?? 0);
      });
  }, [state, q, sortKey]);

  const paged = usePaged(rows, 50, `${q}|${sortKey}`);

  return (
    <ListPageLayout
      title="수주 현황"
      description="낙찰·1순위가 있는 AI 공고 (분류 제외분 포함)"
      toolbar={
        <ListControl
          search="사업명·기관·낙찰자"
          searchValue={search}
          onSearchChange={setSearch}
          filters={
            <>
              <Button variant={sortKey === "open" ? "primary" : "secondary"} onClick={() => setSortKey("open")}>
                개찰일순
              </Button>
              <Button variant={sortKey === "award" ? "primary" : "secondary"} onClick={() => setSortKey("award")}>
                낙찰액순
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  downloadCsv(
                    "awards.csv",
                    ["개찰일", "기관", "사업명", "낙찰자", "낙찰억", "예산억", "낙찰률"],
                    rows.map((n) => [
                      n.open_date,
                      n.org,
                      n.title,
                      n.winner || n.first_rank,
                      n.award_amount_eok,
                      n.budget_eok,
                      n.win_rate_pct ?? n.award_to_budget_pct,
                    ]),
                  )
                }
              >
                CSV
              </Button>
            </>
          }
        />
      }
    >
      <AsyncView state={state}>
        {() =>
          rows.length === 0 ? (
            <EmptyState title="낙찰 결과가 없습니다" />
          ) : (
            <>
              <div style={{ padding: "8px 16px", fontSize: 12, color: "var(--color-text-secondary)" }}>
                {paged.shown.toLocaleString()} / {paged.total.toLocaleString()}건
              </div>
              <DataTable
                columns={[
                  { key: "fit", header: "적합도", render: (r) => <FitBadge verdict={r.fit_verdict} score={r.fit_score} /> },
                  {
                    key: "open",
                    header: "개찰일",
                    render: (r) => (
                      <span>
                        {r.open_date ?? "-"}
                        {ddayLabel(r.close_at) ? ` · ${ddayLabel(r.close_at)}` : ""}
                      </span>
                    ),
                  },
                  { key: "org", header: "수요기관", render: (r) => r.org ?? "-" },
                  {
                    key: "title",
                    header: "사업명",
                    render: (r) => <Link to={`/bids/${r.id}`}>{r.title ?? r.bid_no}</Link>,
                  },
                  {
                    key: "winner",
                    header: "낙찰자",
                    render: (r) =>
                      r.winner ? r.winner : r.first_rank ? `${r.first_rank} (1순위)` : "-",
                  },
                  {
                    key: "award",
                    header: "낙찰(억)",
                    align: "right",
                    render: (r) => fmtEok(r.award_amount_eok),
                  },
                  { key: "budget", header: "예산(억)", align: "right", render: (r) => fmtEok(r.budget_eok) },
                  {
                    key: "rate",
                    header: "낙찰률",
                    align: "right",
                    render: (r) => fmtWinRate(r.win_rate_pct, r.award_to_budget_pct),
                  },
                ]}
                rows={paged.page}
              />
              {paged.hasMore ? (
                <div style={{ padding: 16 }}>
                  <Button variant="secondary" onClick={paged.more}>
                    더 보기
                  </Button>
                </div>
              ) : null}
            </>
          )
        }
      </AsyncView>
    </ListPageLayout>
  );
}
