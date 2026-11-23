import { useState } from "react";
import { Button, ListControl, ListPageLayout } from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import NoticeTable from "../components/NoticeTable";
import { dataClient, type FitVerdict, type NoticeListItem } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { fitLabel } from "../components/FitBadge";

const BAND_MIN = 8;
const BAND_MAX = 30;

function inBand(n: NoticeListItem): boolean {
  return n.budget_eok != null && n.budget_eok >= BAND_MIN && n.budget_eok <= BAND_MAX;
}

export default function BandPage() {
  const [search, setSearch] = useState("");
  const [fit, setFit] = useState<FitVerdict | "">("");
  const [bandOnly, setBandOnly] = useState(true);
  const q = useDebounced(search);

  const state = useAsync(
    async () => {
      const res = await dataClient.listNotices({ q, fit, openOnly: true, limit: 2000 });
      return res;
    },
    [q, fit],
  );

  const fits: (FitVerdict | "")[] = ["", "GO", "REVIEW", "NO-GO"];

  return (
    <ListPageLayout
      title="8~30억 분석"
      description={`예산 ${BAND_MIN}~${BAND_MAX}억 구간 진행 중 공고`}
      toolbar={
        <ListControl
          search="공고명·기관·공고번호"
          searchValue={search}
          onSearchChange={setSearch}
          filters={
            <>
              {fits.map((f) => (
                <Button key={f || "all"} variant={fit === f ? "primary" : "secondary"} onClick={() => setFit(f)}>
                  {f ? fitLabel(f) : "전체"}
                </Button>
              ))}
              <Button variant={bandOnly ? "primary" : "secondary"} onClick={() => setBandOnly((v) => !v)}>
                {BAND_MIN}~{BAND_MAX}억만
              </Button>
            </>
          }
        />
      }
    >
      <AsyncView state={state}>
        {({ items }) => {
          const rows = bandOnly ? items.filter(inBand) : items;
          return (
            <>
              <div style={{ padding: "8px 16px", fontSize: 12, color: "var(--color-text-secondary)" }}>
                총 {rows.length.toLocaleString()}건
              </div>
              <NoticeTable rows={rows} />
            </>
          );
        }}
      </AsyncView>
    </ListPageLayout>
  );
}
