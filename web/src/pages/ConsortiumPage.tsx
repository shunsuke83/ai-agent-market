import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
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
import {
  dataClient,
  type ConsortiumEdge,
  type ConsortiumFirmRollup,
  type ConsortiumJointContract,
  type ConsortiumPayload,
} from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { fmtEok, fmtNum } from "../lib/format";

function FirmLink({ name, bizno }: { name?: string | null; bizno?: string | null }) {
  const label = name || bizno || "-";
  const q = name || bizno || "";
  if (!q) return <>-</>;
  return <Link to={`/bidders?q=${encodeURIComponent(q)}`}>{label}</Link>;
}

export default function ConsortiumPage() {
  const state = useAsync(() => dataClient.getConsortium(), []);
  const [search, setSearch] = useState("");
  const [onlyLarge, setOnlyLarge] = useState(false);
  const [onlyListedMember, setOnlyListedMember] = useState(false);
  const q = useDebounced(search);

  const payload: ConsortiumPayload | null = state.status === "ready" ? state.data : null;
  const summary = payload?.summary;
  const xenon = payload?.xenon;

  const edges = useMemo(() => {
    let rows = payload?.edges ?? [];
    const needle = q.trim().toLowerCase();
    if (needle) {
      rows = rows.filter((e) =>
        `${e.lead_name ?? ""} ${e.member_name ?? ""}`.toLowerCase().includes(needle),
      );
    }
    if (onlyListedMember) rows = rows.filter((e) => e.member_listed);
    return rows;
  }, [payload, q, onlyListedMember]);

  const large = useMemo(() => {
    let rows = payload?.large_joint ?? [];
    if (onlyLarge) rows = rows.filter((r) => (r.amount_eok ?? 0) >= 30);
    const needle = q.trim().toLowerCase();
    if (needle) {
      rows = rows.filter((r) =>
        `${r.title ?? ""} ${r.org ?? ""}`.toLowerCase().includes(needle),
      );
    }
    return rows;
  }, [payload, q, onlyLarge]);

  const leaderCols: DataTableColumn<ConsortiumFirmRollup>[] = [
    {
      key: "name",
      header: "주계약",
      render: (r) => <FirmLink name={r.name} bizno={r.bizno} />,
    },
    {
      key: "listed",
      header: "43사",
      render: (r) => (r.listed ? "예" : "-"),
    },
    { key: "n", header: "계약", align: "right", render: (r) => fmtNum(r.contracts) },
    { key: "amt", header: "금액", align: "right", render: (r) => fmtEok(r.amount_eok) },
  ];

  const memberCols: DataTableColumn<ConsortiumFirmRollup>[] = [
    {
      key: "name",
      header: "도급",
      render: (r) => <FirmLink name={r.name} bizno={r.bizno} />,
    },
    {
      key: "listed",
      header: "43사",
      render: (r) => (r.listed ? "예" : "-"),
    },
    { key: "n", header: "계약", align: "right", render: (r) => fmtNum(r.contracts) },
    { key: "amt", header: "금액", align: "right", render: (r) => fmtEok(r.amount_eok) },
  ];

  const edgeCols: DataTableColumn<ConsortiumEdge>[] = [
    {
      key: "lead",
      header: "주계약",
      render: (r) => <FirmLink name={r.lead_name} bizno={r.lead_bizno} />,
    },
    {
      key: "mem",
      header: "도급",
      render: (r) => <FirmLink name={r.member_name} bizno={r.member_bizno} />,
    },
    { key: "n", header: "횟수", align: "right", render: (r) => fmtNum(r.count) },
    {
      key: "amt",
      header: "금액 합",
      align: "right",
      render: (r) => fmtEok(r.amount_eok_sum),
    },
  ];

  const jointCols: DataTableColumn<ConsortiumJointContract>[] = [
    { key: "date", header: "계약일", render: (r) => r.signed_date ?? "-" },
    { key: "org", header: "기관", render: (r) => r.org ?? "-" },
    {
      key: "title",
      header: "사업명",
      render: (r) =>
        r.url ? (
          <a href={r.url} target="_blank" rel="noreferrer">
            {r.title ?? r.contract_no}
          </a>
        ) : (
          (r.title ?? r.contract_no ?? "-")
        ),
    },
    {
      key: "amt",
      header: "금액",
      align: "right",
      render: (r) => fmtEok(r.amount_eok),
    },
    {
      key: "firms",
      header: "구성",
      render: (r) =>
        (r.firms ?? [])
          .map((f) => {
            const share = f.share != null ? ` ${f.share}%` : "";
            return `${f.name}${f.role === "주계약업체" ? "(주)" : ""}${share}`;
          })
          .join(" · ") || "-",
    },
  ];

  return (
    <DashboardPageLayout
      title="컨소시엄 지도"
      description="AI 계약의 주계약·도급 관계를 집계합니다. 대형 SI가 전문기업을 도급으로 데려간 패턴을 찾습니다."
      stamp={payload?.generated_at ? `업데이트 ${payload.generated_at}` : undefined}
      stats={
        summary ? (
          <>
            <StatCard label="AI 계약" value={fmtNum(summary.contracts)} />
            <StatCard label="공동수급" value={fmtNum(summary.multi_firm)} />
            <StatCard
              label="30억+ 공동"
              value={fmtNum(summary.large_joint)}
              hint={`${summary.large_joint_min_eok ?? 30}억 이상`}
            />
            <StatCard
              label="외부→43사 도급"
              value={fmtNum(summary.external_lead_to_listed)}
            />
          </>
        ) : null
      }
    >
      <AsyncView state={state}>
        {(data) =>
          !data ? (
            <EmptyState title="컨소시엄 데이터가 없습니다" />
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              {xenon ? (
                <Alert tone="info" title="제논 관점">
                  주계약 {xenon.lead}건 · 도급 {xenon.member}건
                  {xenon.contracts && xenon.contracts.length
                    ? ` · 최근 ${xenon.contracts
                        .slice(0, 3)
                        .map((c) => c.title ?? c.contract_no)
                        .join(" / ")}`
                    : ""}
                </Alert>
              ) : null}

              <Card>
                <div style={{ padding: 16, display: "grid", gap: 12 }}>
                  <ListControl
                    search="주계약·도급·사업명"
                    searchValue={search}
                    onSearchChange={setSearch}
                  />
                  <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                    <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <input
                        type="checkbox"
                        checked={onlyLarge}
                        onChange={(e) => setOnlyLarge(e.target.checked)}
                      />
                      <Text variant="muted">30억+ 공동만 (계약표)</Text>
                    </label>
                    <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <input
                        type="checkbox"
                        checked={onlyListedMember}
                        onChange={(e) => setOnlyListedMember(e.target.checked)}
                      />
                      <Text variant="muted">도급이 43사(목록)인 엣지만</Text>
                    </label>
                  </div>
                </div>
              </Card>

              <div
                style={{
                  display: "grid",
                  gap: 16,
                  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                }}
              >
                <Card>
                  <div style={{ padding: 16, display: "grid", gap: 12 }}>
                    <Text as="h2" variant="heading">
                      주계약 TOP
                    </Text>
                    <DataTable
                      columns={leaderCols}
                      rows={(data.leaders ?? []).slice(0, 15)}
                      empty="없음"
                    />
                  </div>
                </Card>
                <Card>
                  <div style={{ padding: 16, display: "grid", gap: 12 }}>
                    <Text as="h2" variant="heading">
                      도급 TOP
                    </Text>
                    <DataTable
                      columns={memberCols}
                      rows={(data.members ?? []).slice(0, 15)}
                      empty="없음"
                    />
                  </div>
                </Card>
              </div>

              <Card>
                <div style={{ padding: 16, display: "grid", gap: 12 }}>
                  <Text as="h2" variant="heading">
                    주계약 ↔ 도급
                  </Text>
                  <DataTable columns={edgeCols} rows={edges.slice(0, 40)} empty="엣지가 없습니다." />
                </div>
              </Card>

              <Card>
                <div style={{ padding: 16, display: "grid", gap: 12 }}>
                  <Text as="h2" variant="heading">
                    30억+ 공동도급 계약
                  </Text>
                  <DataTable columns={jointCols} rows={large} empty="해당 계약이 없습니다." />
                </div>
              </Card>
            </div>
          )
        }
      </AsyncView>
    </DashboardPageLayout>
  );
}
