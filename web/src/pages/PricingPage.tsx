import { Link } from "react-router-dom";
import { DataTable, EmptyState, ListControl, ListPageLayout } from "@genonai/admin-design-system";
import { useMemo, useState } from "react";
import AsyncView from "../components/AsyncView";
import { dataClient, type NoticeListItem } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { fmtEok } from "../lib/format";

export default function PricingPage() {
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const state = useAsync(
    () => dataClient.listNotices({ openOnly: false, includeExcluded: false, limit: 2000 }),
    [],
  );

  const rows = useMemo(() => {
    if (state.status !== "ready") return [] as NoticeListItem[];
    const needle = q.trim().toLowerCase();
    return state.data.items
      .filter((n) => n.bid_count != null || n.win_rate_pct != null || n.winner)
      .filter((n) => {
        if (!needle) return true;
        const hay = `${n.title ?? ""} ${n.org ?? ""} ${n.winner ?? ""}`.toLowerCase();
        return hay.includes(needle);
      })
      .sort((a, b) => (b.bid_count ?? 0) - (a.bid_count ?? 0));
  }, [state, q]);

  return (
    <ListPageLayout
      title="투찰·경쟁"
      description="투찰 수·낙찰률이 있는 공고"
      toolbar={<ListControl search="사업명·기관" searchValue={search} onSearchChange={setSearch} />}
    >
      <AsyncView state={state}>
        {() =>
          rows.length === 0 ? (
            <EmptyState title="투찰 데이터가 없습니다" />
          ) : (
            <DataTable
              columns={[
                {
                  key: "title",
                  header: "사업명",
                  render: (r) => <Link to={`/bids/${r.id}`}>{r.title ?? r.bid_no}</Link>,
                },
                { key: "org", header: "수요기관", render: (r) => r.org ?? "-" },
                { key: "bids", header: "투찰 수", align: "right", render: (r) => r.bid_count ?? "-" },
                {
                  key: "rate",
                  header: "낙찰률",
                  align: "right",
                  render: (r) => (r.win_rate_pct != null ? `${r.win_rate_pct}%` : "-"),
                },
                { key: "budget", header: "예산(억)", align: "right", render: (r) => fmtEok(r.budget_eok) },
                { key: "winner", header: "낙찰자", render: (r) => r.winner ?? "-" },
              ]}
              rows={rows}
            />
          )
        }
      </AsyncView>
    </ListPageLayout>
  );
}
