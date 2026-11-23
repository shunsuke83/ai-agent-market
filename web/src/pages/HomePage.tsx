import { Link } from "react-router-dom";
import { Card, DashboardPageLayout, StatCard, Text } from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import NoticeTable from "../components/NoticeTable";
import { IS_INTERNAL, SITE_TITLE } from "../config";
import { dataClient, type NoticeListItem, type SpaSummary } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { fmtNum } from "../lib/format";

type HomeData = { summary: SpaSummary; stamp: string | null };

async function loadHome(): Promise<HomeData> {
  const [meta, summary] = await Promise.all([dataClient.getMeta(), dataClient.getSummary()]);
  if (summary && (summary.new || summary.fit || summary.closing)) {
    return { summary, stamp: summary.generated_at ?? meta.stamp };
  }
  // No precomputed summary: derive from the notice list.
  const { total, items } = await dataClient.listNotices({ openOnly: true, limit: 300 });
  const byClose = [...items]
    .filter((n) => n.close_at)
    .sort((a, b) => (a.close_at ?? "").localeCompare(b.close_at ?? ""));
  const derived: SpaSummary = {
    ...summary,
    open_notices: summary?.open_notices ?? total,
    go_count: summary?.go_count ?? items.filter((n) => n.fit_verdict === "GO").length,
    review_count: summary?.review_count ?? items.filter((n) => n.fit_verdict === "REVIEW").length,
    new: [...items].sort((a, b) => (b.notice_date ?? "").localeCompare(a.notice_date ?? "")).slice(0, 8),
    fit: items.filter((n) => n.fit_verdict === "GO").slice(0, 8),
    closing: byClose.slice(0, 8),
  };
  return { summary: derived, stamp: meta.stamp };
}

function Section({ title, rows, more }: { title: string; rows: NoticeListItem[]; more?: string }) {
  return (
    <Card flush>
      <div style={{ padding: "16px 16px 8px", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <Text as="h2" variant="heading">
          {title}
        </Text>
        {more ? <Link to={more}>더 보기</Link> : null}
      </div>
      <NoticeTable rows={rows} />
    </Card>
  );
}

export default function HomePage() {
  const state = useAsync(loadHome, []);
  const summary = state.status === "ready" ? state.data.summary : null;
  const stamp = state.status === "ready" ? state.data.stamp : null;

  return (
    <DashboardPageLayout
      title={SITE_TITLE}
      description={IS_INTERNAL ? "내부 D1 기준 진행 중 공고 현황" : "공개 데이터 기준 AI 사업 입찰 현황"}
      stamp={stamp ? `업데이트 ${stamp}` : undefined}
      stats={
        summary ? (
          <>
            <StatCard label="진행 중 공고" value={fmtNum(summary.open_notices)} />
            <StatCard label="참여(GO)" value={fmtNum(summary.go_count)} hint="적합도 기준" />
            <StatCard label="검토(REVIEW)" value={fmtNum(summary.review_count)} />
            <StatCard label="마감 임박" value={fmtNum(summary.closing_soon ?? summary.closing?.length)} />
          </>
        ) : null
      }
    >
      <AsyncView state={state}>
        {({ summary: s }) => (
          <>
            <Section title="신규 공고" rows={s.new ?? []} more="/band" />
            <Section title="참여 적합 공고" rows={s.fit ?? []} more="/band" />
            <Section title="마감 임박" rows={s.closing ?? []} more="/band" />
          </>
        )}
      </AsyncView>
    </DashboardPageLayout>
  );
}
