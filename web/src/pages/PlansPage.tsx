import { DataTable, type DataTableColumn } from "@genonai/admin-design-system";
import DatasetListPage from "../components/DatasetListPage";
import { dataClient, type OrderPlan } from "../data/client";
import { fmtEok } from "../lib/format";

const COLUMNS: DataTableColumn<OrderPlan>[] = [
  { key: "order_ym", header: "예정월", render: (r) => String(r.order_ym ?? "-") },
  { key: "org", header: "발주기관", render: (r) => String(r.org ?? "-") },
  {
    key: "title",
    header: "사업명",
    render: (r) =>
      r.url ? (
        <a href={String(r.url)} target="_blank" rel="noreferrer">
          {String(r.title ?? r.plan_no ?? "-")}
        </a>
      ) : (
        String(r.title ?? r.plan_no ?? "-")
      ),
  },
  { key: "scope", header: "범위", render: (r) => String(r.scope ?? "-") },
  { key: "amount", header: "금액(억)", align: "right", render: (r) => fmtEok(r.amount_eok as number | null) },
];

export default function PlansPage() {
  return (
    <DatasetListPage<OrderPlan>
      title="발주 예정"
      description="발주계획 공개 목록"
      load={() => dataClient.getOrderPlans()}
      searchText={(r) => `${r.title ?? ""} ${r.org ?? ""} ${r.plan_no ?? ""}`}
      render={(rows) => <DataTable columns={COLUMNS} rows={rows} empty="조건에 맞는 발주계획이 없습니다." />}
    />
  );
}
