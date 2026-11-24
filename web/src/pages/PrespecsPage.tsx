import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
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
import { dataClient, type Prespec } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { usePaged } from "../hooks/usePaged";
import { downloadCsv } from "../lib/csv";
import { ddayLabel } from "../lib/dday";
import { fmtDateTime, fmtEok, fmtNum } from "../lib/format";

const BAND_MIN = 8;
const BAND_MAX = 30;

type PrespecStatus = "의견 접수 중" | "본공고 게시" | "의견 마감";

function nowKst(): string {
  const d = new Date(Date.now() + 9 * 3600 * 1000);
  return d.toISOString().slice(0, 16).replace("T", " ");
}

function statusOf(p: Prespec, now: string): PrespecStatus {
  if (p.bid_nos && p.bid_nos.length > 0) return "본공고 게시";
  if (p.opinion_close_at && p.opinion_close_at >= now) return "의견 접수 중";
  return "의견 마감";
}

function statusTone(s: PrespecStatus): "success" | "warning" | "neutral" {
  if (s === "의견 접수 중") return "success";
  if (s === "본공고 게시") return "warning";
  return "neutral";
}

function g2bBidUrl(bidNo: string): string {
  const no = bidNo.split("-")[0];
  return `https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=${encodeURIComponent(no)}&bidPbancOrd=000`;
}

type Row = Prespec & { status: PrespecStatus };

export default function PrespecsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | PrespecStatus>("all");
  const q = useDebounced(search);
  const state = useAsync(async () => {
    const [rows, meta] = await Promise.all([dataClient.getPrespecs(), dataClient.getMeta()]);
    return { rows: rows ?? [], stamp: meta.stamp };
  }, []);

  const now = useMemo(() => nowKst(), []);

  const enriched = useMemo(() => {
    if (state.status !== "ready") return [] as Row[];
    return state.data.rows.map((p) => ({ ...p, status: statusOf(p, now) }));
  }, [state, now]);

  const stats = useMemo(() => {
    const total = enriched.length;
    const open = enriched.filter((p) => p.status === "의견 접수 중").length;
    const bid = enriched.filter((p) => p.status === "본공고 게시").length;
    const band = enriched.filter((p) => {
      const b = p.asign_budget_eok;
      return b != null && b >= BAND_MIN && b <= BAND_MAX;
    }).length;
    const budgetSum = enriched.reduce((s, p) => s + (Number(p.asign_budget_eok) || 0), 0);
    const since = enriched
      .map((p) => p.registered_date || (p.registered_at ?? "").slice(0, 10))
      .filter(Boolean)
      .sort()[0];
    return { total, open, bid, band, budgetSum, since };
  }, [enriched]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return enriched
      .filter((p) => (statusFilter === "all" ? true : p.status === statusFilter))
      .filter((p) => {
        if (!needle) return true;
        const hay = `${p.title ?? ""} ${p.org ?? ""} ${p.prespec_no} ${p.scope ?? ""}`.toLowerCase();
        return hay.includes(needle);
      })
      .sort((a, b) => (b.registered_at ?? "").localeCompare(a.registered_at ?? ""));
  }, [enriched, q, statusFilter]);

  const paged = usePaged(rows, 50, `${q}|${statusFilter}`);

  const columns: DataTableColumn<Row>[] = [
    {
      key: "registered",
      header: "등록",
      render: (r) => r.registered_date || fmtDateTime(r.registered_at),
    },
    {
      key: "close",
      header: "의견 마감",
      render: (r) => (
        <span>
          {fmtDateTime(r.opinion_close_at)}
          {ddayLabel(r.opinion_close_at) ? (
            <>
              {" "}
              <Badge tone="warning">{ddayLabel(r.opinion_close_at)}</Badge>
            </>
          ) : null}
        </span>
      ),
    },
    {
      key: "status",
      header: "상태",
      render: (r) => <Badge tone={statusTone(r.status)}>{r.status}</Badge>,
    },
    { key: "org", header: "수요기관", render: (r) => r.org ?? "-" },
    {
      key: "title",
      header: "사전규격명",
      render: (r) => (
        <div style={{ display: "grid", gap: 4 }}>
          <span>{r.title ?? r.prespec_no}</span>
          <Text variant="muted">
            {r.prespec_no}
            {r.biz_div ? ` · ${r.biz_div}` : ""}
            {r.nature ? ` · ${r.nature}` : ""}
          </Text>
        </div>
      ),
    },
    { key: "scope", header: "범위", render: (r) => r.scope ?? "-" },
    {
      key: "budget",
      header: "배정예산",
      align: "right",
      render: (r) => fmtEok(r.asign_budget_eok),
    },
    {
      key: "files",
      header: "규격서",
      render: (r) => {
        const files = r.spec_files ?? [];
        if (!files.length) return "-";
        return (
          <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
            {files.map((url, i) => (
              <a key={`${url}-${i}`} href={url} target="_blank" rel="noreferrer">
                {i + 1}
              </a>
            ))}
          </span>
        );
      },
    },
    {
      key: "bids",
      header: "본공고",
      render: (r) => {
        const bids = r.bid_nos ?? [];
        if (!bids.length) return "-";
        return (
          <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
            {bids.map((b) => {
              const id = `${b.split("-")[0]}-000`;
              return (
                <span key={b} style={{ display: "inline-flex", gap: 4 }}>
                  <Link to={`/bids/${id}`}>{b.split("-")[0]}</Link>
                  <a href={g2bBidUrl(b)} target="_blank" rel="noreferrer" title="나라장터">
                    ↗
                  </a>
                </span>
              );
            })}
          </span>
        );
      },
    },
  ];

  const stamp = state.status === "ready" ? state.data.stamp : null;

  return (
    <DashboardPageLayout
      title="사전규격"
      description="본공고 전에 공개되는 AI 사업 사전규격(규격서 초안)입니다. 의견 접수 중이면 규격 의견을 낼 수 있습니다."
      stamp={stamp ? `업데이트 ${stamp}` : undefined}
      stats={
        <>
          <StatCard
            label="AI 사전규격"
            value={fmtNum(stats.total)}
            hint={stats.since ? `${stats.since} 이후` : undefined}
          />
          <StatCard label="의견 접수 중" value={fmtNum(stats.open)} />
          <StatCard label={`배정 ${BAND_MIN}~${BAND_MAX}억`} value={fmtNum(stats.band)} />
          <StatCard label="본공고 게시" value={fmtNum(stats.bid)} />
          <StatCard label="배정예산 합계" value={fmtEok(Math.round(stats.budgetSum))} />
        </>
      }
    >
      <AsyncView state={state}>
        {() => (
          <Card>
            <div style={{ padding: 16, display: "grid", gap: 12 }}>
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  flexWrap: "wrap",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {(
                    [
                      ["all", "전체"],
                      ["의견 접수 중", "의견 접수 중"],
                      ["본공고 게시", "본공고 게시"],
                      ["의견 마감", "의견 마감"],
                    ] as const
                  ).map(([id, label]) => (
                    <Button
                      key={id}
                      variant={statusFilter === id ? "primary" : "secondary"}
                      onClick={() => setStatusFilter(id)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      downloadCsv(
                        "prespecs.csv",
                        ["등록", "의견마감", "상태", "기관", "제목", "배정예산", "번호"],
                        rows.map((p) => [
                          p.registered_date || p.registered_at,
                          p.opinion_close_at,
                          p.status,
                          p.org,
                          p.title,
                          p.asign_budget_eok,
                          p.prespec_no,
                        ]),
                      )
                    }
                  >
                    CSV
                  </Button>
                  <ListControl search="사업명·기관·번호" searchValue={search} onSearchChange={setSearch} />
                </div>
              </div>
              <Text variant="muted">
                {paged.shown}/{paged.total}건
              </Text>
              {rows.length === 0 ? (
                <EmptyState title="조건에 맞는 사전규격이 없습니다" />
              ) : (
                <>
                  <DataTable columns={columns} rows={paged.page} />
                  {paged.hasMore ? (
                    <Button variant="secondary" onClick={paged.more}>
                      더 보기
                    </Button>
                  ) : null}
                </>
              )}
            </div>
          </Card>
        )}
      </AsyncView>
    </DashboardPageLayout>
  );
}
