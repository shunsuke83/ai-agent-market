import { Link } from "react-router-dom";
import { Badge, DataTable, EmptyState, type DataTableColumn } from "@genonai/admin-design-system";
import type { NoticeListItem } from "../data/types";
import { ddayLabel } from "../lib/dday";
import { fmtDateTime, fmtEok } from "../lib/format";
import FitBadge from "./FitBadge";

export default function NoticeTable({
  rows,
  empty = "조건에 맞는 공고가 없습니다.",
  showDday = false,
}: {
  rows: NoticeListItem[];
  empty?: string;
  showDday?: boolean;
}) {
  const columns: DataTableColumn<NoticeListItem>[] = [
    { key: "fit", header: "적합도", render: (n) => <FitBadge verdict={n.fit_verdict} score={n.fit_score} /> },
    {
      key: "close_at",
      header: "마감",
      render: (n) => (
        <span>
          {fmtDateTime(n.close_at)}
          {showDday && ddayLabel(n.close_at) ? (
            <>
              {" "}
              <Badge tone="warning">{ddayLabel(n.close_at)}</Badge>
            </>
          ) : null}
        </span>
      ),
    },
    { key: "org", header: "발주기관", render: (n) => n.org ?? "-" },
    {
      key: "title",
      header: "공고명",
      render: (n) => (
        <span>
          <Link to={`/bids/${encodeURIComponent(n.id)}`}>{n.title ?? n.bid_no}</Link>
          {n.hw_included ? (
            <>
              {" "}
              <Badge tone="warning">HW</Badge>
            </>
          ) : null}
        </span>
      ),
    },
    { key: "budget_eok", header: "예산", align: "right", render: (n) => fmtEok(n.budget_eok) },
  ];

  return <DataTable columns={columns} rows={rows} empty={<EmptyState title={empty} />} />;
}
