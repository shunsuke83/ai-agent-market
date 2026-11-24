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
  type Bidder,
  type BidderHistoryItem,
  type BidderNotice,
  type BiddersPayload,
} from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { fmtEok, fmtNum } from "../lib/format";

const LIST_LIMIT = 50;

function digits(s: string): string {
  return s.replace(/\D/g, "");
}

function fmtBizno(bz: string): string {
  return bz.length === 10 ? `${bz.slice(0, 3)}-${bz.slice(3, 5)}-${bz.slice(5)}` : bz;
}

function normName(s: string): string {
  return String(s || "")
    .replace(/\(주\)|㈜|주식회사|\(유\)|유한회사|\(재\)|재단법인|\(사\)|사단법인/g, "")
    .replace(/\s+/g, "")
    .toLowerCase();
}

function firmLabel(f: Bidder): string {
  return String(f.name ?? f.firm ?? f.bidder ?? f.bizno ?? "-");
}

type HistRow = BidderHistoryItem & {
  notice: BidderNotice | null;
  result: string;
  resultBizno?: string;
};

function buildHistRows(
  firm: Bidder,
  notices: BidderNotice[],
  nameByBizno: Map<string, string>,
): HistRow[] {
  const hist = [...(firm.history ?? [])].sort((a, b) => {
    const da = notices[a.notice_idx]?.date ?? "";
    const db = notices[b.notice_idx]?.date ?? "";
    return db.localeCompare(da);
  });
  return hist.map((h) => {
    const notice = notices[h.notice_idx] ?? null;
    const winner = notice?.winner_bizno ?? "";
    let result = notice?.status ?? "";
    let resultBizno: string | undefined;
    if (winner === firm.bizno) {
      result = "낙찰";
    } else if (winner) {
      result = `${nameByBizno.get(winner) ?? fmtBizno(winner)} 낙찰`;
      resultBizno = winner;
    } else if (notice?.status === "낙찰") {
      result = "다른 업체 낙찰";
    } else if (h.rank === 1) {
      result = "1순위 (확정 전)";
    } else if (notice?.status === "1순위") {
      result = "다른 업체 1순위";
    }
    return { ...h, notice, result, resultBizno };
  });
}

function BidderDetail({
  firm,
  notices,
  nameByBizno,
  onBack,
  onSelectFirm,
}: {
  firm: Bidder;
  notices: BidderNotice[];
  nameByBizno: Map<string, string>;
  onBack: () => void;
  onSelectFirm: (bizno: string) => void;
}) {
  const rows = useMemo(
    () => buildHistRows(firm, notices, nameByBizno),
    [firm, notices, nameByBizno],
  );

  const columns: DataTableColumn<HistRow>[] = [
    { key: "date", header: "개찰일", render: (r) => r.notice?.date ?? "-" },
    {
      key: "org",
      header: "수요기관",
      render: (r) =>
        r.notice?.org ? (
          <Link to={`/agencies?q=${encodeURIComponent(r.notice.org)}`}>{r.notice.org}</Link>
        ) : (
          "-"
        ),
    },
    {
      key: "title",
      header: "사업명",
      render: (r) =>
        r.notice?.id ? (
          <Link to={`/bids/${r.notice.id}`}>{r.notice.title ?? r.notice.id}</Link>
        ) : (
          (r.notice?.title ?? "-")
        ),
    },
    {
      key: "budget",
      header: "예산(억)",
      align: "right",
      render: (r) => fmtEok(r.notice?.budget_eok),
    },
    {
      key: "rank",
      header: "순위",
      align: "right",
      render: (r) => {
        if (r.rank == null) return "-";
        const n = r.notice?.bidder_count;
        return n ? `${r.rank}/${n}` : String(r.rank);
      },
    },
    {
      key: "rate",
      header: "투찰률·가격점수",
      align: "right",
      render: (r) => {
        if (r.rate_pct != null) return `${r.rate_pct.toFixed(2)}%`;
        if (r.price_score != null) return `${r.price_score.toFixed(2)}점`;
        return "-";
      },
    },
    {
      key: "amount",
      header: "투찰금액",
      align: "right",
      render: (r) => fmtEok(r.amount_eok),
    },
    {
      key: "result",
      header: "결과",
      render: (r) =>
        r.resultBizno ? (
          <Button variant="ghost" onClick={() => onSelectFirm(r.resultBizno!)}>
            {r.result}
          </Button>
        ) : (
          r.result || "-"
        ),
    },
  ];

  const changes = (firm.changes ?? [])
    .map((c) => `${c.date ?? ""} ${c.text ?? ""}${c.confirmed ? "" : "(확인일)"}`.trim())
    .filter(Boolean);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Button variant="secondary" onClick={onBack}>
          목록으로
        </Button>
        <Text as="h2" variant="heading">
          {firmLabel(firm)}
        </Text>
      </div>
      <Text variant="muted">
        사업자번호 {fmtBizno(firm.bizno)}
        {firm.region ? ` · ${firm.region}` : ""}
      </Text>
      {changes.length > 0 ? (
        <Text variant="muted">나라장터 등록정보 변경: {changes.join(" / ")}</Text>
      ) : null}
      <div
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
        }}
      >
        <StatCard label="투찰" value={fmtNum(firm.bids ?? firm.bid_count)} />
        <StatCard label="낙찰 확정" value={fmtNum(firm.wins ?? firm.win_count)} />
        <StatCard label="1순위 (확정 전)" value={fmtNum(firm.firsts)} />
        <StatCard
          label="투찰률 중앙값"
          value={firm.median_bid_rate != null ? `${firm.median_bid_rate}%` : "-"}
          hint={firm.bid_rate_n ? `${firm.bid_rate_n}건` : undefined}
        />
        <StatCard
          label="예산 대비 투찰 중앙값"
          value={firm.median_budget_share != null ? `${firm.median_budget_share}%` : "-"}
          hint={firm.budget_share_n ? `${firm.budget_share_n}건` : undefined}
        />
        <StatCard
          label="평균 낙찰률"
          value={firm.avg_win_rate != null ? `${firm.avg_win_rate}%` : "-"}
        />
      </div>
      {(firm.rivals ?? []).length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <Text variant="muted">자주 맞붙은 업체(개찰 순위 기준):</Text>
          {(firm.rivals ?? []).map((r) => (
            <Text key={r.bizno} variant="muted">
              <Button variant="ghost" onClick={() => onSelectFirm(r.bizno)}>
                {r.name}
              </Button>{" "}
              {r.faced}회(앞섬 {r.ahead}·뒤짐 {r.behind})
            </Text>
          ))}
        </div>
      ) : null}
      <Card>
        <div style={{ padding: 16 }}>
          <DataTable columns={columns} rows={rows} empty="이 업체의 투찰 이력이 없습니다." />
        </div>
      </Card>
      <Text variant="muted">
        순위 옆 숫자는 그 공고의 투찰 업체 수입니다. &apos;%&apos;는 예정가격 대비 투찰률이고,
        &apos;점&apos;은 협상계약의 가격평가 점수입니다. 투찰률 중앙값에는 투찰률만 쓰고, 예산 대비는
        투찰금액÷예산입니다.
      </Text>
    </div>
  );
}

function HeadToHead({
  firms,
  notices,
  onSelectFirm,
}: {
  firms: Bidder[];
  notices: BidderNotice[];
  onSelectFirm: (bizno: string) => void;
}) {
  const [aQ, setAQ] = useState("");
  const [bQ, setBQ] = useState("");
  const [result, setResult] = useState<{
    a: Bidder;
    b: Bidder;
    rows: { date: string; org: string; title: string; id?: string | null; rankA?: number | null; rankB?: number | null }[];
    ahead: number;
    behind: number;
  } | null>(null);
  const [error, setError] = useState("");

  const findFirm = (q: string): Bidder | null => {
    const d = digits(q);
    if (d.length === 10) {
      const hit = firms.find((f) => f.bizno === d);
      if (hit) return hit;
    }
    const nq = normName(q);
    if (!nq) return null;
    const hits = firms
      .filter((f) => normName(firmLabel(f)).includes(nq))
      .sort((x, y) => Number(y.bids ?? 0) - Number(x.bids ?? 0));
    return hits[0] ?? null;
  };

  const run = () => {
    const a = findFirm(aQ.trim());
    const b = findFirm(bQ.trim());
    if (!a || !b || a.bizno === b.bizno) {
      setResult(null);
      setError("맞대결할 업체 둘을 업체명 또는 사업자번호로 입력하세요.");
      return;
    }
    setError("");
    const setB = new Map((b.history ?? []).map((h) => [h.notice_idx, h]));
    let ahead = 0;
    let behind = 0;
    const rows: {
      date: string;
      org: string;
      title: string;
      id?: string | null;
      rankA?: number | null;
      rankB?: number | null;
    }[] = [];
    for (const ha of a.history ?? []) {
      const hb = setB.get(ha.notice_idx);
      if (!hb) continue;
      const n = notices[ha.notice_idx];
      if (ha.rank != null && hb.rank != null) {
        if (ha.rank < hb.rank) ahead += 1;
        else if (ha.rank > hb.rank) behind += 1;
      }
      rows.push({
        date: n?.date ?? "-",
        org: n?.org ?? "-",
        title: n?.title ?? "-",
        id: n?.id,
        rankA: ha.rank,
        rankB: hb.rank,
      });
    }
    rows.sort((x, y) => y.date.localeCompare(x.date));
    setResult({ a, b, rows, ahead, behind });
  };

  const h2hColumns: DataTableColumn<(typeof result extends null ? never : NonNullable<typeof result>["rows"][number])>[] = [
    { key: "date", header: "개찰일", render: (r) => r.date },
    { key: "org", header: "수요기관", render: (r) => r.org },
    {
      key: "title",
      header: "사업명",
      render: (r) => (r.id ? <Link to={`/bids/${r.id}`}>{r.title}</Link> : r.title),
    },
    {
      key: "a",
      header: result ? firmLabel(result.a) : "A",
      align: "right",
      render: (r) => (r.rankA == null ? "-" : String(r.rankA)),
    },
    {
      key: "b",
      header: result ? firmLabel(result.b) : "B",
      align: "right",
      render: (r) => (r.rankB == null ? "-" : String(r.rankB)),
    },
  ];

  return (
    <Card>
      <div style={{ padding: 16, display: "grid", gap: 12 }}>
        <Text as="h3" variant="heading">
          맞대결
        </Text>
        <Text variant="muted">두 업체가 같이 투찰한 공고의 개찰 순위를 비교합니다.</Text>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <ListControl search="업체 A" searchValue={aQ} onSearchChange={setAQ} />
          <ListControl search="업체 B" searchValue={bQ} onSearchChange={setBQ} />
          <Button onClick={run}>비교</Button>
        </div>
        {error ? <EmptyState title={error} /> : null}
        {result ? (
          <>
            <Text variant="muted">
              <Button variant="ghost" onClick={() => onSelectFirm(result.a.bizno)}>
                {firmLabel(result.a)}
              </Button>{" "}
              대{" "}
              <Button variant="ghost" onClick={() => onSelectFirm(result.b.bizno)}>
                {firmLabel(result.b)}
              </Button>
              {" · "}같이 투찰한 공고 {result.rows.length}건 · {firmLabel(result.a)} 앞섬{" "}
              {result.ahead} · 뒤짐 {result.behind}
            </Text>
            {result.rows.length === 0 ? (
              <EmptyState title="같이 투찰한 공고가 없습니다" />
            ) : (
              <DataTable columns={h2hColumns} rows={result.rows} />
            )}
          </>
        ) : null}
      </div>
    </Card>
  );
}

export default function BiddersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";
  const [search, setSearch] = useState(initialQ);
  const [selected, setSelected] = useState<string | null>(null);
  const [skipAuto, setSkipAuto] = useState(false);
  const q = useDebounced(search);
  const state = useAsync(() => dataClient.getBidders(), []);

  const payload: BiddersPayload | null = state.status === "ready" ? state.data : null;
  const firms = payload?.firms ?? payload?.bidders ?? [];
  const notices = payload?.notices ?? [];
  const summary = payload?.summary;
  const stamp = payload?.generated_at;

  const nameByBizno = useMemo(() => {
    const m = new Map<string, string>();
    for (const f of firms) m.set(f.bizno, firmLabel(f));
    return m;
  }, [firms]);

  const selectedFirm = useMemo(
    () => (selected ? firms.find((f) => f.bizno === selected) ?? null : null),
    [firms, selected],
  );

  const matches = useMemo(() => {
    const query = q.trim();
    if (!query) return firms.slice(0, LIST_LIMIT);
    const d = digits(query);
    const numeric = /^[\d\s-]+$/.test(query);
    if (numeric && d.length === 10) {
      const hit = firms.find((f) => f.bizno === d);
      return hit ? [hit] : [];
    }
    if (numeric && d.length >= 3) {
      return firms
        .filter((f) => f.bizno.startsWith(d))
        .sort((a, b) => Number(b.bids ?? 0) - Number(a.bids ?? 0));
    }
    if (numeric && d.length < 3) return [];
    const nq = normName(query);
    if (nq.length < 1) return [];
    return firms
      .filter((f) => normName(firmLabel(f)).includes(nq))
      .sort((a, b) => {
        const exact =
          Number(normName(firmLabel(b)) === nq) - Number(normName(firmLabel(a)) === nq);
        if (exact) return exact;
        return Number(b.bids ?? 0) - Number(a.bids ?? 0);
      });
  }, [firms, q]);

  useEffect(() => {
    setSkipAuto(false);
  }, [q]);

  useEffect(() => {
    const next = q.trim();
    const cur = searchParams.get("q") ?? "";
    if (next === cur) return;
    const sp = new URLSearchParams(searchParams);
    if (next) sp.set("q", next);
    else sp.delete("q");
    setSearchParams(sp, { replace: true });
  }, [q, searchParams, setSearchParams]);

  useEffect(() => {
    if (skipAuto || selected || matches.length !== 1) return;
    const query = q.trim();
    if (!query) return;
    const d = digits(query);
    const numeric = /^[\d\s-]+$/.test(query);
    if (numeric && d.length < 10 && d.length < 3) return;
    if (!numeric && normName(query).length < 1) return;
    setSelected(matches[0].bizno);
  }, [matches, q, selected, skipAuto]);

  const selectFirm = (bizno: string) => {
    const f = firms.find((x) => x.bizno === bizno);
    setSelected(bizno);
    setSearch(f ? firmLabel(f) : fmtBizno(bizno));
    setSkipAuto(false);
  };

  const listColumns: DataTableColumn<Bidder>[] = [
    {
      key: "name",
      header: "업체",
      render: (r) => (
        <Button
          variant="ghost"
          onClick={() => {
            setSelected(r.bizno);
            setSearch(firmLabel(r));
          }}
        >
          {firmLabel(r)}
        </Button>
      ),
    },
    {
      key: "bizno",
      header: "사업자번호",
      render: (r) => fmtBizno(r.bizno),
    },
    { key: "region", header: "지역·규모", render: (r) => r.region || "-" },
    {
      key: "bids",
      header: "투찰",
      align: "right",
      render: (r) => fmtNum(r.bids ?? r.bid_count),
    },
    {
      key: "wins",
      header: "낙찰",
      align: "right",
      render: (r) => fmtNum(r.wins ?? r.win_count),
    },
    {
      key: "rate",
      header: "평균 낙찰률",
      align: "right",
      render: (r) => (r.avg_win_rate != null ? `${r.avg_win_rate}%` : "-"),
    },
  ];

  return (
    <DashboardPageLayout
      title="입찰이력 검색"
      description="업체명·사업자번호로 AI 사업 투찰·낙찰 이력과 맞붙는 업체를 찾습니다."
      stamp={stamp ? `업데이트 ${stamp}` : undefined}
      stats={
        summary ? (
          <>
            <StatCard label="투찰 업체" value={fmtNum(summary.firms)} />
            <StatCard label="개찰 공고" value={fmtNum(summary.notices)} />
            <StatCard label="투찰" value={fmtNum(summary.bids)} />
            <StatCard label="낙찰 확정" value={fmtNum(summary.wins)} />
          </>
        ) : null
      }
    >
      <AsyncView state={state}>
        {(data) =>
          !data ? (
            <EmptyState title="입찰이력 데이터가 없습니다" />
          ) : selectedFirm ? (
            <BidderDetail
              firm={selectedFirm}
              notices={notices}
              nameByBizno={nameByBizno}
              onBack={() => {
                setSkipAuto(true);
                setSelected(null);
              }}
              onSelectFirm={selectFirm}
            />
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              <Card>
                <div style={{ padding: 16, display: "grid", gap: 12 }}>
                  <ListControl
                    search="사업자번호 또는 업체명"
                    searchValue={search}
                    onSearchChange={(v) => {
                      setSearch(v);
                      setSelected(null);
                    }}
                  />
                  <Text variant="muted">
                    업체명을 누르면 투찰 이력·맞붙는 업체·낙찰 결과가 열립니다. 발주기관에서 넘어온
                    검색어는 주소의 q로 유지됩니다.
                  </Text>
                  {(() => {
                    const query = q.trim();
                    const d = digits(query);
                    const numeric = /^[\d\s-]+$/.test(query);
                    if (numeric && query && d.length < 3) {
                      return <EmptyState title="사업자번호는 3자리 이상 입력하세요" />;
                    }
                    if (matches.length === 0) {
                      return (
                        <EmptyState
                          title={
                            query
                              ? `"${query}"에 맞는 업체가 없습니다`
                              : "조건에 맞는 업체가 없습니다"
                          }
                        />
                      );
                    }
                    return (
                      <>
                        {query ? (
                          <Text variant="muted">
                            &quot;{query}&quot;에 맞는 업체 {matches.length}곳
                            {matches.length > LIST_LIMIT
                              ? ` · 투찰이 많은 순으로 ${LIST_LIMIT}곳만 표시`
                              : ""}
                          </Text>
                        ) : (
                          <Text variant="muted">낙찰·투찰이 많은 업체 상위 {LIST_LIMIT}곳</Text>
                        )}
                        <DataTable columns={listColumns} rows={matches.slice(0, LIST_LIMIT)} />
                      </>
                    );
                  })()}
                </div>
              </Card>
              <HeadToHead firms={firms} notices={notices} onSelectFirm={selectFirm} />
            </div>
          )
        }
      </AsyncView>
    </DashboardPageLayout>
  );
}
