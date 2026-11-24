import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Alert,
  Badge,
  Card,
  DataTable,
  DescriptionList,
  DetailPageLayout,
  EmptyState,
  Tag,
  Text,
  type AlertTone,
  type DataTableColumn,
} from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import FitBadge, { fitLabel } from "../components/FitBadge";
import { dataClient, type FitVerdict, type NoticeBidder, type NoticeDetail } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { fmtDateTime, fmtEok, fmtNum, fmtWinRate, g2bUrl } from "../lib/format";

const FIT_ALERT: Record<FitVerdict, AlertTone> = { GO: "success", REVIEW: "warning", "NO-GO": "danger" };
const RATE_MIN = 50;
const RATE_MAX = 110;

function rateOrScore(rate: number | null | undefined): { rate: number | null; score: number | null } {
  if (rate == null || !Number.isFinite(rate)) return { rate: null, score: null };
  if (rate >= RATE_MIN && rate <= RATE_MAX) return { rate, score: null };
  if (rate >= 0 && rate < RATE_MIN) return { rate: null, score: rate };
  return { rate: null, score: null };
}

function BidderTable({ notice }: { notice: NoticeDetail }) {
  const bidders = (notice.bidders ?? notice.payload?.bidders ?? []).filter(
    (b): b is NoticeBidder => !!b && typeof b === "object",
  );
  if (!bidders.length) return null;

  const split = bidders.map((b) => rateOrScore(b.rate_pct ?? null));
  const hasRate = split.some((s) => s.rate != null);
  const hasScore = split.some((s) => s.score != null);
  const pricePts = notice.payload?.price_rate;

  const columns: DataTableColumn<NoticeBidder & { _i: number }>[] = [
    {
      key: "rank",
      header: "순위",
      align: "right",
      render: (r) => fmtNum(r.rank ?? undefined),
    },
    {
      key: "name",
      header: "업체",
      render: (r) =>
        r.name ? (
          <Link to={`/bidders?q=${encodeURIComponent(r.name)}`}>{r.name}</Link>
        ) : (
          "-"
        ),
    },
    {
      key: "amount",
      header: "투찰금액(억)",
      align: "right",
      render: (r) => fmtEok(r.amount_eok),
    },
  ];
  if (hasRate) {
    columns.push({
      key: "rate",
      header: "투찰률",
      align: "right",
      render: (r) => {
        const v = split[r._i]?.rate;
        return v != null ? `${v.toFixed(3)}%` : "-";
      },
    });
  }
  if (hasScore) {
    columns.push({
      key: "score",
      header: pricePts != null ? `가격점수 (${pricePts}점 만점)` : "가격점수",
      align: "right",
      render: (r) => {
        const v = split[r._i]?.score;
        return v != null ? v.toFixed(3) : "-";
      },
    });
  }

  const rows = bidders.map((b, i) => ({ ...b, _i: i }));
  const notes = ["나라장터 개찰결과 기준."];
  if (hasRate) notes.push("투찰률은 예정가격 대비입니다.");
  if (hasScore) {
    const tech = notice.payload?.tech_rate;
    const weights =
      tech != null && pricePts != null
        ? `기술평가 ${tech}점과 가격평가 ${pricePts}점을`
        : "기술평가 점수와 가격평가 점수를";
    notes.push(
      `협상에 의한 계약은 ${weights} 합친 종합점수로 순위를 정합니다. 이 사이트가 받는 개찰결과에는 가격점수만 있어 기술점수·종합점수는 표시하지 못합니다.`,
    );
  }

  return (
    <Card>
      <div style={{ padding: 16, display: "grid", gap: 12 }}>
        <Text as="h2" variant="heading">
          투찰 업체
        </Text>
        <DataTable columns={columns} rows={rows} empty="투찰 업체가 없습니다." />
        <Text variant="muted">{notes.join(" ")}</Text>
      </div>
    </Card>
  );
}

function infoItems(n: NoticeDetail) {
  const p = n.payload ?? {};
  const url = g2bUrl(n);
  const limits = (
    [
      ["industry_limit", "업종"],
      ["participation_limit", "참가 자격"],
      ["record_limit", "실적"],
    ] as const
  )
    .filter(([k]) => p[k])
    .map(([, label]) => label);

  const items: { label: string; value: ReactNode }[] = [
    { label: "공고번호", value: `${n.bid_no}-${n.bid_ord}` },
    {
      label: "수요기관",
      value: n.org ? <Link to={`/agencies?q=${encodeURIComponent(n.org)}`}>{n.org}</Link> : "-",
    },
    { label: "예산", value: fmtEok(n.budget_eok) },
  ];
  if (p.budget_kind) {
    items.push({ label: "예산 기준", value: String(p.budget_kind) });
  }
  if (p.asign_budget_eok != null) items.push({ label: "배정예산", value: fmtEok(p.asign_budget_eok as number) });
  if (p.presmpt_eok != null) items.push({ label: "추정가격", value: fmtEok(p.presmpt_eok as number) });
  if (p.base_amount_eok != null) items.push({ label: "기초금액", value: fmtEok(p.base_amount_eok as number) });

  items.push(
    { label: "공고일", value: n.notice_date ?? "-" },
    { label: "입찰 마감", value: fmtDateTime(n.close_at) },
    { label: "개찰", value: fmtDateTime(n.open_at ?? n.open_date) },
  );
  if (n.contract_method) items.push({ label: "계약방법", value: n.contract_method });
  if (n.ntce_kind) items.push({ label: "공고종류", value: n.ntce_kind });
  if (n.status) items.push({ label: "상태", value: n.status });

  if (n.winner) {
    items.push({
      label: "낙찰업체",
      value: <Link to={`/bidders?q=${encodeURIComponent(n.winner)}`}>{n.winner}</Link>,
    });
  } else if (n.first_rank) {
    items.push({
      label: "개찰 1순위",
      value: (
        <span>
          <Link to={`/bidders?q=${encodeURIComponent(n.first_rank)}`}>{n.first_rank}</Link>
          <Text as="span" variant="muted">
            {" "}
            (낙찰 확정 전)
          </Text>
        </span>
      ),
    });
  }
  if (n.winner || n.award_amount_eok != null) {
    items.push({ label: "낙찰금액", value: fmtEok(n.award_amount_eok) });
  }
  if (n.award_to_budget_pct != null) {
    items.push({
      label: "예산 대비 낙찰금액",
      value: `${Number(n.award_to_budget_pct).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`,
    });
  }
  if (n.winner || n.win_rate_pct != null || n.award_to_budget_pct != null) {
    items.push({
      label: "낙찰률",
      value: fmtWinRate(n.win_rate_pct, n.award_to_budget_pct),
    });
  }
  if (n.bid_count != null) {
    items.push({ label: "투찰 업체 수", value: fmtNum(n.bid_count) });
  }
  if (n.second) {
    items.push({
      label: "2순위",
      value: <Link to={`/bidders?q=${encodeURIComponent(n.second)}`}>{n.second}</Link>,
    });
  }
  if (p.award_method) items.push({ label: "낙찰 방법", value: String(p.award_method) });
  if (p.tech_rate != null && p.price_rate != null) {
    items.push({ label: "평가 비율", value: `기술 ${p.tech_rate} : 가격 ${p.price_rate}` });
  }
  if (p.joint_method) items.push({ label: "공동수급", value: String(p.joint_method).replace(/\(\s*\)/g, "").trim() });
  if (limits.length) {
    items.push({ label: "제한", value: `${limits.join(" · ")} 제한 — 공고서에서 조건 확인` });
  }
  const files = Array.isArray(p.notice_files) ? p.notice_files : [];
  if (files.length) {
    items.push({
      label: "공고 첨부",
      value: (
        <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 8 }}>
          {files.map((f, i) =>
            f?.url ? (
              <a key={`${f.url}-${i}`} href={f.url} target="_blank" rel="noreferrer">
                {f.name || `첨부 ${i + 1}`}
              </a>
            ) : null,
          )}
        </span>
      ),
    });
  }
  items.push({
    label: "나라장터",
    value: url ? (
      <a href={url} target="_blank" rel="noreferrer">
        원문 보기
      </a>
    ) : (
      "-"
    ),
  });
  return items;
}

export default function BidDetailPage() {
  const { id = "" } = useParams();
  const state = useAsync(() => dataClient.getNotice(id), [id]);

  return (
    <AsyncView state={state}>
      {(n) =>
        !n ? (
          <Card>
            <EmptyState title="공고를 찾을 수 없습니다" description={id} />
            <div style={{ textAlign: "center" }}>
              <Link to="/band">목록으로</Link>
            </div>
          </Card>
        ) : (
          <DetailPageLayout
            title={n.title ?? n.bid_no}
            description={`${n.org ?? "-"} · ${n.bid_no}-${n.bid_ord}`}
            badges={
              <>
                <FitBadge verdict={n.fit_verdict} score={n.fit_score} />
                {n.status ? <Badge>{n.status}</Badge> : null}
                {n.scope ? <Badge tone="brand">{n.scope}</Badge> : null}
                {n.nature ? <Badge>{n.nature}</Badge> : null}
                {n.soft_excluded ? <Badge tone="danger">{n.exclude_reason || "제외"}</Badge> : null}
                {(n.fields ?? []).map((f) => (
                  <Tag key={f}>{f}</Tag>
                ))}
              </>
            }
          >
            {n.fit_verdict ? (
              <Alert tone={FIT_ALERT[n.fit_verdict]} title={`적합도: ${fitLabel(n.fit_verdict)}`}>
                {n.fit_reasons && n.fit_reasons.length > 0 ? (
                  <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                    {n.fit_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                ) : (
                  "판정 사유가 없습니다."
                )}
              </Alert>
            ) : null}
            <Card>
              <div style={{ padding: 16, display: "grid", gap: 12 }}>
                <Text as="h2" variant="heading">
                  공고 정보
                </Text>
                <DescriptionList items={infoItems(n)} />
              </div>
            </Card>
            <BidderTable notice={n} />
          </DetailPageLayout>
        )
      }
    </AsyncView>
  );
}
