import { DataTable, type DataTableColumn } from "@genonai/admin-design-system";
import DatasetListPage from "../components/DatasetListPage";
import { dataClient, type Firm } from "../data/client";

const COLUMNS: DataTableColumn<Firm>[] = [
  { key: "corp_name", header: "기업명", render: (r) => String(r.corp_name ?? r.name ?? "-") },
  { key: "region", header: "지역", render: (r) => String(r.region ?? "-") },
  { key: "biz_div", header: "업종", render: (r) => String(r.biz_div ?? "-") },
  { key: "employees", header: "직원", align: "right", render: (r) => String(r.employees ?? "-") },
  {
    key: "homepage",
    header: "홈페이지",
    render: (r) =>
      r.homepage ? (
        <a href={String(r.homepage)} target="_blank" rel="noreferrer">
          링크
        </a>
      ) : (
        "-"
      ),
  },
];

export default function CompetitorsPage() {
  return (
    <DatasetListPage<Firm>
      title="국내 전문기업"
      description="조달업체 기본정보가 있는 AI 관련 기업"
      load={() => dataClient.getFirms()}
      searchText={(r) => `${r.corp_name ?? ""} ${r.name ?? ""} ${r.region ?? ""} ${r.bizno ?? ""}`}
      render={(rows) => <DataTable columns={COLUMNS} rows={rows} empty="조건에 맞는 기업이 없습니다." />}
    />
  );
}
