import { DataTable, type DataTableColumn } from "@genonai/admin-design-system";
import DatasetListPage from "../components/DatasetListPage";
import { dataClient, type Agency } from "../data/client";

const COLUMNS: DataTableColumn<Agency>[] = [
  { key: "name", header: "발주기관", render: (r) => String(r.name ?? r.org ?? "-") },
  { key: "notices", header: "공고 수", align: "right", render: (r) => String(r.notices ?? r.count ?? "-") },
  { key: "budget", header: "예산 합(억)", align: "right", render: (r) => String(r.budget_eok ?? r.total_budget_eok ?? "-") },
];

export default function AgenciesPage() {
  return (
    <DatasetListPage<Agency>
      title="발주기관 검색"
      description="기관별 AI 공고 집계"
      load={() => dataClient.getAgencies()}
      searchText={(r) => `${r.name ?? ""} ${r.org ?? ""}`}
      render={(rows) => <DataTable columns={COLUMNS} rows={rows} empty="조건에 맞는 기관이 없습니다." />}
    />
  );
}
