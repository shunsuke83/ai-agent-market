import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Button,
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
  type AgenciesPayload,
  type Agency,
  type AgencyNotice,
} from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { fmtEok, fmtNum } from "../lib/format";

const LIST_LIMIT = 50;

const GROUPS: Record<string, string[]> = {
  발전5사: ["한국남동발전", "한국중부발전", "한국서부발전", "한국남부발전", "한국동서발전"],
  한국발전: ["한국남동발전", "한국중부발전", "한국서부발전", "한국남부발전", "한국동서발전"],
  금융공공기관: [
    "한국은행",
    "한국투자공사",
    "산업은행",
    "수출입은행",
    "예금보험",
    "자산관리공사",
    "주택금융",
    "신용보증기금",
    "기술보증기금",
    "무역보험",
    "한국거래소",
  ],
};

const ALIASES: Record<string, string> = {
  남동발전: "한국남동발전",
  중부발전: "한국중부발전",
  서부발전: "한국서부발전",
  남부발전: "한국남부발전",
  동서발전: "한국동서발전",
  한은: "한국은행",
  kic: "한국투자공사",
};

function norm(s: string): string {
  return s.replace(/\s+/g, "").toLowerCase();
}

function AgencyDetail({
  agency,
  notices,
  onBack,
}: {
  agency: Agency;
  notices: AgencyNotice[];
  onBack: () => void;
}) {
  const rows = notices
    .filter((n) => n.org === agency.name)
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));

  const columns: DataTableColumn<AgencyNotice>[] = [
    { key: "date", header: "공고일", render: (r) => r.date ?? "-" },
    {
      key: "title",
      header: "사업명",
      render: (r) => (
        <span>
          {r.id ? <Link to={`/bids/${r.id}`}>{r.title ?? r.id}</Link> : (r.title ?? "-")}
          {r.gen_agent ? (
            <Text as="span" variant="muted">
              {" "}
              · 생성형·Agent
            </Text>
          ) : null}
        </span>
      ),
    },
    { key: "budget", header: "예산(억)", align: "right", render: (r) => fmtEok(r.budget_eok) },
    { key: "status", header: "상태", render: (r) => r.status ?? "-" },
    {
      key: "winner",
      header: "낙찰 업체",
      render: (r) => {
        if (!r.winner) return "-";
        const label =
          r.status === "낙찰" ? r.winner : `${r.winner} (1순위)`;
        return r.winner_bizno ? (
          <Link to={`/bidders?q=${encodeURIComponent(r.winner)}`}>{label}</Link>
        ) : (
          label
        );
      },
    },
    {
      key: "award",
      header: "낙찰금액",
      align: "right",
      render: (r) => fmtEok(r.award_amount_eok),
    },
    {
      key: "bids",
      header: "응찰",
      align: "right",
      render: (r) => fmtNum(r.bid_count ?? undefined),
    },
  ];

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Button variant="secondary" onClick={onBack}>
          목록으로
        </Button>
        <Text as="h2" variant="heading">
          {agency.name}
        </Text>
      </div>
      <div
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
        }}
      >
        <StatCard
          label="AI 사업 공고"
          value={fmtNum(agency.notices)}
          hint={`생성형·Agent ${fmtNum(agency.gen_agent_notices)}건`}
        />
        <StatCard label="예산 합계" value={fmtEok(agency.budget_eok)} />
        <StatCard label="낙찰 확정" value={fmtNum(agency.wins)} />
        <StatCard
          label="낙찰금액 합계"
          value={agency.award_known ? fmtEok(agency.award_amount_eok) : "-"}
          hint={agency.award_known ? `공개 ${agency.award_known}건` : undefined}
        />
        <StatCard
          label="평균 응찰"
          value={agency.avg_bid_count != null ? `${agency.avg_bid_count}곳` : "-"}
        />
      </div>
      {(agency.top_winners ?? []).length > 0 ? (
        <Text variant="muted">
          이 기관 사업을 낙찰받은 업체:{" "}
          {(agency.top_winners ?? [])
            .map((w) => {
              const amt = w.award_amount_eok ? `(${fmtEok(w.award_amount_eok)})` : "";
              return `${w.name} ${w.wins}건${amt}`;
            })
            .join(", ")}
        </Text>
      ) : null}
      <Card>
        <div style={{ padding: 16 }}>
          <DataTable columns={columns} rows={rows} empty="이 기관의 공고가 없습니다." />
        </div>
      </Card>
      <Text variant="muted">
        이 사이트가 수집하는 AI 사업 공고만 담았습니다. 기관의 전체 발주 이력이 아닙니다. 수요기관명은
        나라장터 표기 그대로라 같은 기관이 다른 이름으로 나뉠 수 있습니다.
      </Text>
    </div>
  );
}

export default function AgenciesPage() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [selected, setSelected] = useState<string | null>(null);
  const [skipAuto, setSkipAuto] = useState(false);
  const q = useDebounced(search);
  const state = useAsync(() => dataClient.getAgencies(), []);

  const payload: AgenciesPayload | null = state.status === "ready" ? state.data : null;
  const agencies = payload?.agencies ?? [];
  const notices = payload?.notices ?? [];
  const summary = payload?.summary;
  const stamp = payload?.generated_at;

  const selectedAgency = useMemo(
    () => (selected ? agencies.find((a) => a.name === selected) ?? null : null),
    [agencies, selected],
  );

  const matches = useMemo(() => {
    let query = q.trim();
    const nq = norm(query);
    if (!nq) {
      return agencies.slice(0, LIST_LIMIT);
    }
    if (ALIASES[nq]) {
      query = ALIASES[nq];
    }
    const nq2 = norm(query);
    const group = GROUPS[nq2] || GROUPS[nq2.replace(/\s+/g, "")];
    if (group) {
      const keys = group.map(norm);
      return agencies
        .filter((a) => keys.some((k) => norm(a.name).includes(k)))
        .sort((a, b) => Number(b.notices ?? 0) - Number(a.notices ?? 0));
    }
    if (nq2.length < 2) return [];
    return agencies
      .filter((a) => norm(a.name).includes(nq2))
      .sort((a, b) => {
        const exact = Number(norm(b.name) === nq2) - Number(norm(a.name) === nq2);
        if (exact) return exact;
        return Number(b.notices ?? 0) - Number(a.notices ?? 0);
      });
  }, [agencies, q]);

  useEffect(() => {
    setSkipAuto(false);
  }, [q]);

  // One unique hit → open detail (same as legacy agency-search.js).
  useEffect(() => {
    if (skipAuto || selected || matches.length !== 1) return;
    if (q.trim().length < 2 && !ALIASES[norm(q.trim())]) return;
    setSelected(matches[0].name);
  }, [matches, q, selected, skipAuto]);

  const listColumns: DataTableColumn<Agency>[] = [
    {
      key: "name",
      header: "수요기관",
      render: (r) => (
        <Button
          variant="ghost"
          onClick={() => {
            setSelected(r.name);
            setSearch(r.name);
          }}
        >
          {r.name}
        </Button>
      ),
    },
    { key: "notices", header: "공고", align: "right", render: (r) => fmtNum(r.notices) },
    { key: "wins", header: "낙찰", align: "right", render: (r) => fmtNum(r.wins) },
    {
      key: "budget",
      header: "예산 합계",
      align: "right",
      render: (r) => fmtEok(r.budget_eok),
    },
    {
      key: "award",
      header: "낙찰금액",
      align: "right",
      render: (r) => (r.award_known ? fmtEok(r.award_amount_eok) : "-"),
    },
    {
      key: "gen",
      header: "생성형·Agent",
      align: "right",
      render: (r) => fmtNum(r.gen_agent_notices),
    },
    { key: "latest", header: "최근 공고일", render: (r) => r.latest_date ?? "-" },
  ];

  return (
    <DashboardPageLayout
      title="발주기관 검색"
      description="수요기관 이름으로 AI 사업 공고와 낙찰 업체를 찾습니다. 어느 기관이 얼마 규모로 자주 발주하는지, 누가 그 기관 사업을 가져가는지 볼 수 있습니다."
      stamp={stamp ? `업데이트 ${stamp}` : undefined}
      stats={
        summary ? (
          <>
            <StatCard label="수요기관" value={fmtNum(summary.orgs)} />
            <StatCard label="AI 사업 공고" value={fmtNum(summary.notices)} />
            <StatCard label="낙찰 확정" value={fmtNum(summary.wins)} />
          </>
        ) : null
      }
    >
      <AsyncView state={state}>
        {(data) =>
          !data ? (
            <EmptyState title="발주기관 데이터가 없습니다" />
          ) : selectedAgency ? (
            <AgencyDetail
              agency={selectedAgency}
              notices={notices}
              onBack={() => {
                setSkipAuto(true);
                setSelected(null);
              }}
            />
          ) : (
            <Card>
              <div style={{ padding: 16, display: "grid", gap: 12 }}>
                <ListControl
                  search="기관명 (예: 한국전력, 교육청, 발전5사)"
                  searchValue={search}
                  onSearchChange={(v) => {
                    setSearch(v);
                    setSelected(null);
                  }}
                />
                <Text variant="muted">
                  묶음 검색: 발전5사 · 금융공공기관. 기관명을 누르면 공고·낙찰 업체 상세가 열립니다.
                </Text>
                {q.trim() && norm(q).length < 2 && !GROUPS[norm(q)] && !ALIASES[norm(q)] ? (
                  <EmptyState title="기관명을 2글자 이상 입력하세요" />
                ) : matches.length === 0 ? (
                  <EmptyState title="조건에 맞는 기관이 없습니다" />
                ) : (
                  <>
                    {q.trim() ? (
                      <Text variant="muted">
                        &quot;{q.trim()}&quot;에 맞는 기관 {matches.length}곳
                        {matches.length > LIST_LIMIT
                          ? ` · 공고가 많은 순으로 ${LIST_LIMIT}곳만 표시`
                          : ""}
                      </Text>
                    ) : (
                      <Text variant="muted">공고가 많은 기관 상위 {LIST_LIMIT}곳</Text>
                    )}
                    <DataTable columns={listColumns} rows={matches.slice(0, LIST_LIMIT)} />
                  </>
                )}
              </div>
            </Card>
          )
        }
      </AsyncView>
    </DashboardPageLayout>
  );
}
