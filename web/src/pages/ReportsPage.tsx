import {
  Card,
  DataTable,
  EmptyState,
  ListPageLayout,
  MetricCard,
  Text,
  type DataTableColumn,
} from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import { dataClient } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { fmtEok, fmtNum } from "../lib/format";

type ReportRow = {
  year?: number;
  week?: number;
  month?: number;
  file?: string;
  slug?: string;
  core_count?: number;
  budget_sum?: number;
  awards_count?: number;
  other_count?: number;
  start?: string;
  end?: string;
};

function asRows(v: unknown): ReportRow[] {
  return Array.isArray(v) ? (v as ReportRow[]) : [];
}

function reportHref(file: string | undefined): string | null {
  if (!file) return null;
  const name = file.replace(/^\/+/, "").replace(/^reports\//, "");
  return `/reports/${encodeURIComponent(name)}`;
}

const weeklyCols: DataTableColumn<ReportRow>[] = [
  {
    key: "period",
    header: "기간",
    render: (r) =>
      r.start && r.end ? `${r.start} ~ ${r.end}` : r.week != null ? `${r.year}-W${r.week}` : "-",
  },
  {
    key: "file",
    header: "리포트",
    render: (r) => {
      const href = reportHref(r.file);
      const label = r.slug || r.file || "-";
      return href ? (
        <a href={href} target="_blank" rel="noreferrer">
          {label}
        </a>
      ) : (
        label
      );
    },
  },
  { key: "core", header: "핵심 공고", align: "right", render: (r) => fmtNum(r.core_count) },
  { key: "budget", header: "예산 합(억)", align: "right", render: (r) => fmtEok(r.budget_sum) },
  { key: "awards", header: "낙찰", align: "right", render: (r) => fmtNum(r.awards_count) },
];

const monthlyCols: DataTableColumn<ReportRow>[] = [
  {
    key: "period",
    header: "월",
    render: (r) => (r.year != null && r.month != null ? `${r.year}-${String(r.month).padStart(2, "0")}` : "-"),
  },
  {
    key: "file",
    header: "리포트",
    render: (r) => {
      const href = reportHref(r.file);
      const label = r.slug || r.file || "-";
      return href ? (
        <a href={href} target="_blank" rel="noreferrer">
          {label}
        </a>
      ) : (
        label
      );
    },
  },
  { key: "core", header: "핵심 공고", align: "right", render: (r) => fmtNum(r.core_count) },
  { key: "budget", header: "예산 합(억)", align: "right", render: (r) => fmtEok(r.budget_sum) },
  { key: "awards", header: "낙찰", align: "right", render: (r) => fmtNum(r.awards_count) },
];

export default function ReportsPage() {
  const state = useAsync(() => dataClient.getReports(), []);
  return (
    <ListPageLayout title="리포트 목록" description="주간·월간 분석 리포트">
      <AsyncView state={state}>
        {(data) => {
          if (!data) {
            return (
              <EmptyState
                title="리포트 데이터가 없습니다"
                description="이 모드에서는 제공되지 않거나 아직 배포되지 않았습니다."
              />
            );
          }
          const weekly = asRows(data.weekly);
          const monthly = asRows(data.monthly);
          return (
            <div style={{ padding: 16, display: "grid", gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
                <MetricCard label="주간 리포트" value={weekly.length} />
                <MetricCard label="월간 리포트" value={monthly.length} />
              </div>
              <Card flush>
                <div style={{ padding: 16 }}>
                  <Text as="h2" variant="heading">
                    주간
                  </Text>
                </div>
                <DataTable columns={weeklyCols} rows={weekly} empty={<EmptyState title="주간 리포트가 없습니다." />} />
              </Card>
              <Card flush>
                <div style={{ padding: 16 }}>
                  <Text as="h2" variant="heading">
                    월간
                  </Text>
                </div>
                <DataTable columns={monthlyCols} rows={monthly} empty={<EmptyState title="월간 리포트가 없습니다." />} />
              </Card>
            </div>
          );
        }}
      </AsyncView>
    </ListPageLayout>
  );
}
