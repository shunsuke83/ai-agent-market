import { Link } from "react-router-dom";
import { DataTable, EmptyState, ListControl, ListPageLayout } from "@genonai/admin-design-system";
import { useMemo, useState } from "react";
import AsyncView from "../components/AsyncView";
import FitBadge from "../components/FitBadge";
import { dataClient, type NoticeListItem } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { fmtEok } from "../lib/format";

export default function AwardsPage() {
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
      .filter((n) => n.winner || n.first_rank)
      .filter((n) => {
        if (!needle) return true;
        const hay = `${n.title ?? ""} ${n.org ?? ""} ${n.winner ?? ""} ${n.bid_no}`.toLowerCase();
        return hay.includes(needle);
      })
      .sort((a, b) => (b.open_date ?? "").localeCompare(a.open_date ?? ""));
  }, [state, q]);

  return (
    <ListPageLayout
      title="수주 현황"
      description="낙찰자·개찰일이 있는 AI 공고"
      toolbar={<ListControl search="사업명·기관·낙찰자" searchValue={search} onSearchChange={setSearch} />}
    >
      <AsyncView state={state}>
        {() =>
          rows.length === 0 ? (
            <EmptyState title="낙찰 결과가 없습니다" />
          ) : (
            <DataTable
              columns={[
                { key: "fit", header: "적합도", render: (r) => <FitBadge verdict={r.fit_verdict} score={r.fit_score} /> },
                { key: "open", header: "개찰일", render: (r) => r.open_date ?? "-" },
                { key: "org", header: "수요기관", render: (r) => r.org ?? "-" },
                {
                  key: "title",
                  header: "사업명",
                  render: (r) => <Link to={`/bids/${r.id}`}>{r.title ?? r.bid_no}</Link>,
                },
                { key: "winner", header: "낙찰자", render: (r) => r.winner ?? r.first_rank ?? "-" },
                { key: "budget", header: "예산(억)", align: "right", render: (r) => fmtEok(r.budget_eok) },
              ]}
              rows={rows}
            />
          )
        }
      </AsyncView>
    </ListPageLayout>
  );
}
