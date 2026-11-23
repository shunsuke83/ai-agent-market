import { Link, useParams } from "react-router-dom";
import {
  Alert,
  Badge,
  Card,
  DescriptionList,
  DetailPageLayout,
  EmptyState,
  Tag,
  Text,
  type AlertTone,
} from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import FitBadge, { fitLabel } from "../components/FitBadge";
import { dataClient, type FitVerdict } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { fmtDateTime, fmtEok } from "../lib/format";

const FIT_ALERT: Record<FitVerdict, AlertTone> = { GO: "success", REVIEW: "warning", "NO-GO": "danger" };

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
              <Text as="h2" variant="heading">
                공고 정보
              </Text>
              <DescriptionList
                items={[
                  { label: "예산", value: fmtEok(n.budget_eok) },
                  { label: "공고일", value: n.notice_date ?? "-" },
                  { label: "입찰 마감", value: fmtDateTime(n.close_at) },
                  { label: "개찰", value: fmtDateTime(n.open_at ?? n.open_date) },
                  { label: "계약방법", value: n.contract_method ?? "-" },
                  { label: "공고종류", value: n.ntce_kind ?? "-" },
                  ...(n.winner
                    ? [
                        { label: "낙찰업체", value: n.winner },
                        { label: "낙찰금액", value: fmtEok(n.award_amount_eok) },
                        { label: "낙찰률", value: n.win_rate_pct != null ? `${n.win_rate_pct}%` : "-" },
                      ]
                    : []),
                  {
                    label: "나라장터",
                    value: n.g2b_url ? (
                      <a href={n.g2b_url} target="_blank" rel="noreferrer">
                        원문 보기
                      </a>
                    ) : (
                      "-"
                    ),
                  },
                ]}
              />
            </Card>
          </DetailPageLayout>
        )
      }
    </AsyncView>
  );
}
