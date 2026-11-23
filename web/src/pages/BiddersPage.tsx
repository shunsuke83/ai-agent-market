import { DataTable, type DataTableColumn } from "@genonai/admin-design-system";
import DatasetListPage from "../components/DatasetListPage";
import { dataClient, type Bidder } from "../data/client";

const COLUMNS: DataTableColumn<Bidder>[] = [
  { key: "name", header: "업체명", render: (r) => String(r.name ?? r.firm ?? r.bidder ?? "-") },
  { key: "wins", header: "낙찰", align: "right", render: (r) => String(r.wins ?? r.win_count ?? "-") },
  { key: "bids", header: "투찰", align: "right", render: (r) => String(r.bids ?? r.bid_count ?? "-") },
  { key: "rate", header: "평균 낙찰률", align: "right", render: (r) => (r.avg_win_rate != null ? `${r.avg_win_rate}%` : "-") },
];

export default function BiddersPage() {
  return (
    <DatasetListPage<Bidder>
      title="입찰이력 검색"
      description="업체별 투찰·낙찰 이력"
      load={() => dataClient.getBidders()}
      searchText={(r) => `${r.name ?? ""} ${r.firm ?? ""} ${r.bidder ?? ""}`}
      render={(rows) => <DataTable columns={COLUMNS} rows={rows} empty="조건에 맞는 업체가 없습니다." />}
    />
  );
}
