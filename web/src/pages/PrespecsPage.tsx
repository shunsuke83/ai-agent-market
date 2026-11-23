import { DataTable, type DataTableColumn } from "@genonai/admin-design-system";
import DatasetListPage from "../components/DatasetListPage";
import { dataClient, type Prespec } from "../data/client";
import { fmtDateTime, fmtEok } from "../lib/format";

const COLUMNS: DataTableColumn<Prespec>[] = [
  { key: "registered_at", header: "등록", render: (r) => fmtDateTime(r.registered_at) },
  { key: "opinion_close_at", header: "의견 마감", render: (r) => fmtDateTime(r.opinion_close_at) },
  { key: "org", header: "발주기관", render: (r) => r.org ?? "-" },
  { key: "title", header: "사전규격명", render: (r) => r.title ?? r.prespec_no },
  { key: "asign_budget_eok", header: "배정예산", align: "right", render: (r) => fmtEok(r.asign_budget_eok) },
];

export default function PrespecsPage() {
  return (
    <DatasetListPage<Prespec>
      title="사전규격"
      description="AI 관련 사전규격 공개 목록"
      load={() => dataClient.getPrespecs()}
      searchText={(r) => `${r.title ?? ""} ${r.org ?? ""} ${r.prespec_no}`}
      render={(rows) => <DataTable columns={COLUMNS} rows={rows} empty="조건에 맞는 사전규격이 없습니다." />}
    />
  );
}
