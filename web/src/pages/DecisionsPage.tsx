import { Link } from "react-router-dom";
import {
  Alert,
  Card,
  DashboardPageLayout,
  DataTable,
  EmptyState,
  StatCard,
  Text,
  type DataTableColumn,
} from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import { dataClient, type DecisionRow, type DecisionsPayload } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { fmtEok, fmtNum } from "../lib/format";

const OUTCOME_LABEL: Record<string, string> = {
  won: "낙찰",
  lost: "탈락",
  first: "1순위",
  "n/a": "-",
};

export default function DecisionsPage() {
  const state = useAsync(() => dataClient.getDecisions(), []);

  return (
    <DashboardPageLayout
      title="적합도 사후검증"
      description="제논 투찰·결정 시드로 예산·상장3강 동반 입찰의 낙찰 여부를 점검합니다. 당시 적합도 점수는 비공개라 null입니다."
      stamp={
        state.status === "ready" && state.data?.as_of
          ? `시드 ${state.data.as_of}`
          : undefined
      }
    >
      <AsyncView state={state}>
        {(data: DecisionsPayload | null) => {
          if (!data) return <EmptyState title="결정 시드가 없습니다" />;
          const rows = data.decisions ?? [];
          const hard = rows.filter((r) => (r.budget_eok ?? 0) > 20 || r.listed3_present);
          const hardWins = hard.filter((r) => r.outcome === "won").length;
          const wins = rows.filter((r) => r.outcome === "won").length;

          const cols: DataTableColumn<DecisionRow>[] = [
            {
              key: "id",
              header: "공고",
              render: (r) => (
                <Link to={`/bids/${r.notice_id}`}>{r.notice_id}</Link>
              ),
            },
            {
              key: "budget",
              header: "예산",
              align: "right",
              render: (r) => fmtEok(r.budget_eok),
            },
            {
              key: "l3",
              header: "상장3강",
              render: (r) => (r.listed3_present ? "동반" : "-"),
            },
            {
              key: "action",
              header: "결정",
              render: (r) => r.action ?? "-",
            },
            {
              key: "out",
              header: "결과",
              render: (r) => OUTCOME_LABEL[r.outcome ?? ""] ?? r.outcome ?? "-",
            },
            {
              key: "fit",
              header: "당시 점수",
              align: "right",
              render: (r) =>
                r.fit_score_at_decision != null ? String(r.fit_score_at_decision) : "—",
            },
            { key: "notes", header: "메모", render: (r) => r.notes ?? "-" },
          ];

          return (
            <div style={{ display: "grid", gap: 16 }}>
              <div
                style={{
                  display: "grid",
                  gap: 12,
                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                }}
              >
                <StatCard label="시드 건수" value={fmtNum(rows.length)} />
                <StatCard label="낙찰" value={fmtNum(wins)} />
                <StatCard
                  label="고위험(>20억·3강)"
                  value={fmtNum(hard.length)}
                  hint={`낙찰 ${hardWins}건`}
                />
              </div>
              <Alert tone={hardWins === 0 ? "warning" : "info"} title="가설 점검">
                예산 20억 초과이거나 상장 3강이 함께 들어온 {hard.length}건 중 낙찰은{" "}
                {hardWins}건입니다. 경쟁 강도·예산 규모를 적합도 점수에 반영할 근거로 씁니다.
              </Alert>
              {data.notes ? <Text variant="muted">{data.notes}</Text> : null}
              <Card>
                <div style={{ padding: 16, maxWidth: "100%", overflowX: "auto" }}>
                  <DataTable columns={cols} rows={rows} empty="행이 없습니다." />
                </div>
              </Card>
            </div>
          );
        }}
      </AsyncView>
    </DashboardPageLayout>
  );
}
