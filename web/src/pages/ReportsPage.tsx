import { Card, EmptyState, ListPageLayout, MetricCard, Text } from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import RecordTable from "../components/RecordTable";
import { dataClient } from "../data/client";
import { useAsync } from "../hooks/useAsync";

function asRows(v: unknown): Record<string, unknown>[] {
  return Array.isArray(v) ? (v as Record<string, unknown>[]) : [];
}

export default function ReportsPage() {
  const state = useAsync(() => dataClient.getReports(), []);
  return (
    <ListPageLayout title="리포트 목록" description="주간·월간 분석 리포트">
      <AsyncView state={state}>
        {(data) => {
          if (!data) {
            return <EmptyState title="리포트 데이터가 없습니다" description="이 모드에서는 제공되지 않거나 아직 배포되지 않았습니다." />;
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
                <RecordTable rows={weekly} empty="주간 리포트가 없습니다." />
              </Card>
              <Card flush>
                <div style={{ padding: 16 }}>
                  <Text as="h2" variant="heading">
                    월간
                  </Text>
                </div>
                <RecordTable rows={monthly} empty="월간 리포트가 없습니다." />
              </Card>
            </div>
          );
        }}
      </AsyncView>
    </ListPageLayout>
  );
}
