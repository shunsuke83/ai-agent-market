import { DataTable, type DataTableColumn } from "@genonai/admin-design-system";
import DatasetListPage from "../components/DatasetListPage";
import { dataClient, type OrderPlan } from "../data/client";
import { fmtEok } from "../lib/format";

const COLUMNS: DataTableColumn<OrderPlan>[] = [
  { key: "order_ym", header: "예정월", render: (r) => String(r.order_ym ?? "-") },
  { key: "org", header: "발주기관", render: (r) => String(r.org ?? r.top_org ?? "-") },
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
  { key: "nature", header: "성격", render: (r) => String(r.nature ?? "-") },
  {
    key: "contract",
    header: "계약방법",
    render: (r) => String(r.contract_method ?? "-"),
  },
  {
    key: "procurement",
    header: "조달방식",
    render: (r) => String(r.procurement ?? "-"),
  },
  {
    key: "amount",
    header: "금액(억)",
    align: "right",
    render: (r) => fmtEok(r.amount_eok as number | null),
  },
  {
    key: "bids",
    header: "연결 공고",
    render: (r) => {
      const nos = Array.isArray(r.bid_nos) ? r.bid_nos.map(String) : [];
      if (!nos.length) return "-";
      return nos.slice(0, 3).join(", ") + (nos.length > 3 ? ` 외 ${nos.length - 3}` : "");
    },
  },
  {
    key: "contact",
    header: "담당",
    render: (r) => {
      const dept = r.dept ? String(r.dept) : "";
      const tel = r.tel ? String(r.tel) : "";
      if (!dept && !tel) return "-";
      return [dept, tel].filter(Boolean).join(" · ");
    },
  },
];

export default function PlansPage() {
  return (
    <DatasetListPage<OrderPlan>
      title="발주 예정"
      description="발주계획 공개 목록 — 계약방법·조달방식·연결 공고·담당까지 표시합니다."
      load={() => dataClient.getOrderPlans()}
      searchText={(r) =>
        `${r.title ?? ""} ${r.org ?? ""} ${r.top_org ?? ""} ${r.plan_no ?? ""} ${r.contract_method ?? ""} ${r.procurement ?? ""}`
      }
      render={(rows) => <DataTable columns={COLUMNS} rows={rows} empty="조건에 맞는 발주계획이 없습니다." />}
    />
  );
}
