import { Link } from "react-router-dom";
import { Card, DashboardPageLayout, StatCard, Text } from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import NoticeTable from "../components/NoticeTable";
import { IS_INTERNAL, SITE_TITLE } from "../config";
import { dataClient, type NoticeListItem, type SpaSummary } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { nowKstStamp } from "../lib/dday";
import { fmtNum } from "../lib/format";

type HomeData = { summary: SpaSummary; stamp: string | null };

async function loadHome(): Promise<HomeData> {
  const [meta, summary, list] = await Promise.all([
    dataClient.getMeta(),
    dataClient.getSummary(),
    dataClient.listNotices({ openOnly: true, limit: 3000 }),
  ]);
  const items = list.items;
  const now = nowKstStamp();
  const byClose = [...items]
    .filter((n) => n.close_at && n.close_at >= now)
    .sort((a, b) => (a.close_at ?? "").localeCompare(b.close_at ?? ""));
  const derived: SpaSummary = {
    ...summary,
    open_notices: summary?.open_notices ?? list.total,
    go_count: summary?.go_count ?? items.filter((n) => n.fit_verdict === "GO").length,
    review_count: summary?.review_count ?? items.filter((n) => n.fit_verdict === "REVIEW").length,
    closing_soon: byClose.length,
    new:
      summary?.new?.length && !IS_INTERNAL
        ? summary.new
        : [...items].sort((a, b) => (b.notice_date ?? "").localeCompare(a.notice_date ?? "")).slice(0, 8),
    fit:
      summary?.fit?.length && !IS_INTERNAL
        ? summary.fit
        : items.filter((n) => n.fit_verdict === "GO").slice(0, 8),
    // Always recompute closing against the client clock (Z-05).
    closing: byClose.slice(0, 8),
  };
  return { summary: derived, stamp: summary?.generated_at ?? meta.stamp };
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
      <NoticeTable rows={rows} showDday />
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
            <Section title="참여 적합 공고" rows={s.fit ?? []} more="/band?fit=GO" />
            <Section title="마감 임박" rows={s.closing ?? []} more="/band?closing=1" />
          </>
        )}
      </AsyncView>
    </DashboardPageLayout>
  );
}
