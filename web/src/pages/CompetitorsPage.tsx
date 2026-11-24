import { useMemo, useState } from "react";
import {
  Alert,
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
import { dataClient, type CompetitorFirm, type CompetitorsPayload } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { fmtEok, fmtNum } from "../lib/format";

const FIRM_COLUMNS: DataTableColumn<CompetitorFirm>[] = [
  {
    key: "name",
    header: "업체",
    render: (r) => (
      <span>
        {r.name}
        {r.group === "outside" ? (
          <Text as="span" variant="muted" className="ds-text--caption">
            {" "}
            · 목록 밖
          </Text>
        ) : null}
      </span>
    ),
  },
  { key: "type", header: "유형", render: (r) => r.type || "-" },
  { key: "bids", header: "투찰", align: "right", render: (r) => fmtNum(r.bids) },
  { key: "wins", header: "낙찰", align: "right", render: (r) => fmtNum(r.wins) },
  {
    key: "amount",
    header: "낙찰금액",
    align: "right",
    render: (r) => fmtEok(r.award_amount_eok),
  },
  {
    key: "gen",
    header: "생성형·Agent 투찰",
    align: "right",
    render: (r) => fmtNum(r.gen_agent_bids),
  },
  {
    key: "rate",
    header: "투찰가÷예산",
    align: "right",
    render: (r) =>
      r.bid_to_budget_median_pct != null ? `${r.bid_to_budget_median_pct}%` : "-",
  },
  {
    key: "largest",
    header: "가장 큰 수주",
    render: (r) => {
      const w = r.largest_win;
      if (!w) return "-";
      const amt = w.award_amount_eok != null ? fmtEok(w.award_amount_eok) : "";
      return `${w.org ?? ""} ${amt}`.trim() || (w.title ?? "-");
    },
  },
  {
    key: "employees",
    header: "직원",
    align: "right",
    render: (r) => fmtNum(r.employees ?? undefined),
  },
];

function AnalysisBlock({ data }: { data: CompetitorsPayload }) {
  const analysis = data.analysis;
  if (!analysis) return null;
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card>
        <div style={{ padding: 16, display: "grid", gap: 12 }}>
          <Text as="h2" variant="heading">
            {analysis.title ?? "분석 요약"}
          </Text>
          {analysis.as_of || analysis.author ? (
            <Text variant="muted">
              {[analysis.as_of, analysis.author ? `@ ${analysis.author}` : null]
                .filter(Boolean)
                .join(" · ")}
            </Text>
          ) : null}
          {analysis.lede ? <Text variant="body">{analysis.lede}</Text> : null}
          {analysis.bullets && analysis.bullets.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }}>
              {analysis.bullets.map((b) => (
                <li key={b}>
                  <Text variant="body">{b}</Text>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </Card>

      {(data.type_rollups ?? []).length > 0 ? (
        <Card>
          <div style={{ padding: 16, display: "grid", gap: 12 }}>
            <Text as="h2" variant="heading">
              유형별 실적
            </Text>
            <DataTable
              columns={[
                { key: "type", header: "유형", render: (r) => r.type },
                { key: "firms", header: "기업 수", align: "right", render: (r) => fmtNum(r.firms) },
                { key: "bids", header: "투찰", align: "right", render: (r) => fmtNum(r.bids) },
                { key: "wins", header: "낙찰", align: "right", render: (r) => fmtNum(r.wins) },
                {
                  key: "amt",
                  header: "낙찰금액",
                  align: "right",
                  render: (r) => fmtEok(r.award_amount_eok),
                },
              ]}
              rows={data.type_rollups ?? []}
            />
          </div>
        </Card>
      ) : null}

      {(analysis.sections ?? []).map((sec) => (
        <Card key={sec.id ?? sec.title}>
          <div style={{ padding: 16, display: "grid", gap: 10 }}>
            <Text as="h2" variant="heading">
              {sec.title}
            </Text>
            {(sec.paragraphs ?? []).map((p) => (
              <Text key={p.slice(0, 40)} variant="body">
                {p}
              </Text>
            ))}
          </div>
        </Card>
      ))}

      {(data.head_to_head ?? []).length > 0 ? (
        <Card>
          <div style={{ padding: 16, display: "grid", gap: 12 }}>
            <Text as="h2" variant="heading">
              맞대결 (상장·전문기업)
            </Text>
            <DataTable
              columns={[
                {
                  key: "pair",
                  header: "맞대결",
                  render: (r) => `${r.a} 대 ${r.b}`,
                },
                { key: "meetings", header: "만난 횟수", align: "right", render: (r) => fmtNum(r.meetings) },
                {
                  key: "ahead",
                  header: "순위 비교",
                  render: (r) =>
                    r.a_ahead === r.b_ahead
                      ? `${r.a_ahead}번씩`
                      : r.a_ahead > r.b_ahead
                        ? `${r.a}이 ${r.a_ahead}번 앞섬`
                        : `${r.b}이 ${r.b_ahead}번 앞섬`,
                },
              ]}
              rows={data.head_to_head ?? []}
            />
            {(analysis.head_to_head_notes ?? []).length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 4 }}>
                {(analysis.head_to_head_notes ?? []).map((n) => (
                  <li key={`${n.pair?.join("-")}-${n.note}`}>
                    <Text variant="muted">
                      {(n.pair ?? []).join(" · ")}
                      {n.pair?.length ? " — " : ""}
                      {n.note}
                    </Text>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </Card>
      ) : null}

      {(analysis.limitations ?? []).length > 0 ? (
        <Alert tone="info" title="데이터의 한계">
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {(analysis.limitations ?? []).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Alert>
      ) : null}
    </div>
  );
}

export default function CompetitorsPage() {
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const state = useAsync(() => dataClient.getCompetitors(), []);

  const rows = useMemo(() => {
    if (state.status !== "ready" || !state.data?.firms) return [] as CompetitorFirm[];
    const needle = q.trim().toLowerCase();
    const items = state.data.firms;
    if (!needle) return items;
    return items.filter((r) => {
      const hay = `${r.name ?? ""} ${r.type ?? ""} ${r.region ?? ""} ${r.bizno ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [state, q]);

  const summary = state.status === "ready" ? state.data?.summary : null;
  const stamp = state.status === "ready" ? state.data?.generated_at : null;

  return (
    <DashboardPageLayout
      title="국내 전문기업"
      description="전문기업·목록 밖 경쟁사의 투찰·낙찰 실적과 분석 요약"
      stamp={stamp ? `업데이트 ${stamp}` : undefined}
      stats={
        summary ? (
          <>
            <StatCard label="분석 기업" value={fmtNum(summary.firms)} hint={`전문 ${summary.listed ?? "-"} · 목록 밖 ${summary.outside ?? "-"}`} />
            <StatCard label="투찰" value={fmtNum(summary.bids)} />
            <StatCard label="낙찰" value={fmtNum(summary.wins)} />
            <StatCard label="낙찰금액" value={fmtEok(summary.award_amount_eok)} />
          </>
        ) : null
      }
    >
      <AsyncView state={state}>
        {(data) =>
          !data ? (
            <EmptyState title="경쟁사 분석 데이터가 없습니다" description="export-spa 후 data/spa/competitors.json이 필요합니다." />
          ) : (
            <div style={{ display: "grid", gap: 20 }}>
              <AnalysisBlock data={data} />
              <Card>
                <div style={{ padding: 16, display: "grid", gap: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                    <Text as="h2" variant="heading">
                      한눈에 보기
                    </Text>
                    <ListControl search="업체·유형·지역" searchValue={search} onSearchChange={setSearch} />
                  </div>
                  <Text variant="muted">
                    낙찰 건수 순. 투찰·낙찰은 수집한 나라장터 개찰·낙찰 결과 기준이며, 개찰 1순위만 있는 건은 낙찰에 넣지 않습니다.
                  </Text>
                  {rows.length === 0 ? (
                    <EmptyState title="조건에 맞는 기업이 없습니다" />
                  ) : (
                    <DataTable columns={FIRM_COLUMNS} rows={rows} />
                  )}
                </div>
              </Card>
            </div>
          )
        }
      </AsyncView>
    </DashboardPageLayout>
  );
}
