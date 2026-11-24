import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, ListControl, ListPageLayout } from "@genonai/admin-design-system";
import AsyncView from "../components/AsyncView";
import NoticeTable from "../components/NoticeTable";
import { fitLabel } from "../components/FitBadge";
import { dataClient, type FitVerdict, type NoticeListItem } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";
import { usePaged } from "../hooks/usePaged";
import { downloadCsv } from "../lib/csv";
import { nowKstStamp } from "../lib/dday";

const BAND_MIN = 8;
const BAND_MAX = 30;

function inBand(n: NoticeListItem): boolean {
  return n.budget_eok != null && n.budget_eok >= BAND_MIN && n.budget_eok <= BAND_MAX;
}

type SortKey = "close" | "budget" | "notice";

export default function BandPage() {
  const [params, setParams] = useSearchParams();
  const fitParam = (params.get("fit") || "") as FitVerdict | "";
  const closingOnly = params.get("closing") === "1";

  const [search, setSearch] = useState("");
  const [fit, setFit] = useState<FitVerdict | "">(
    fitParam === "GO" || fitParam === "REVIEW" || fitParam === "NO-GO" ? fitParam : "",
  );
  const [bandOnly, setBandOnly] = useState(!closingOnly && !fitParam);
  const [sortKey, setSortKey] = useState<SortKey>(closingOnly ? "close" : "notice");
  const q = useDebounced(search);

  useEffect(() => {
    if (fitParam === "GO" || fitParam === "REVIEW" || fitParam === "NO-GO") setFit(fitParam);
  }, [fitParam]);

  const state = useAsync(
    async () => dataClient.listNotices({ q, fit, openOnly: true, limit: 2000 }),
    [q, fit],
  );

  const fits: (FitVerdict | "")[] = ["", "GO", "REVIEW", "NO-GO"];
  const now = nowKstStamp();

  const filtered = useMemo(() => {
    if (state.status !== "ready") return [] as NoticeListItem[];
    let rows = state.data.items;
    if (bandOnly) rows = rows.filter(inBand);
    if (closingOnly) rows = rows.filter((n) => n.close_at && n.close_at >= now);
    rows = [...rows].sort((a, b) => {
      if (sortKey === "budget") return (b.budget_eok ?? 0) - (a.budget_eok ?? 0);
      if (sortKey === "close") return (a.close_at ?? "").localeCompare(b.close_at ?? "");
      return (b.notice_date ?? "").localeCompare(a.notice_date ?? "");
    });
    return rows;
  }, [state, bandOnly, closingOnly, sortKey, now]);

  const paged = usePaged(filtered, 50, `${q}|${fit}|${bandOnly}|${closingOnly}|${sortKey}`);

  const setFitAndUrl = (f: FitVerdict | "") => {
    setFit(f);
    const next = new URLSearchParams(params);
    if (f) next.set("fit", f);
    else next.delete("fit");
    setParams(next, { replace: true });
  };

  const toggleClosing = () => {
    const next = new URLSearchParams(params);
    if (closingOnly) next.delete("closing");
    else next.set("closing", "1");
    setParams(next, { replace: true });
    setSortKey("close");
  };

  const exportCsv = () => {
    downloadCsv(
      "band.csv",
      ["적합도", "마감", "발주기관", "공고명", "예산억", "공고번호"],
      filtered.map((n) => [n.fit_verdict, n.close_at, n.org, n.title, n.budget_eok, n.bid_no]),
    );
  };

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
                <Button key={f || "all"} variant={fit === f ? "primary" : "secondary"} onClick={() => setFitAndUrl(f)}>
                  {f ? fitLabel(f) : "전체"}
                </Button>
              ))}
              <Button variant={bandOnly ? "primary" : "secondary"} onClick={() => setBandOnly((v) => !v)}>
                {BAND_MIN}~{BAND_MAX}억만
              </Button>
              <Button variant={closingOnly ? "primary" : "secondary"} onClick={toggleClosing}>
                마감 임박
              </Button>
              <Button
                variant={sortKey === "close" ? "primary" : "secondary"}
                onClick={() => setSortKey("close")}
              >
                마감순
              </Button>
              <Button
                variant={sortKey === "budget" ? "primary" : "secondary"}
                onClick={() => setSortKey("budget")}
              >
                예산순
              </Button>
              <Button variant="secondary" onClick={exportCsv}>
                CSV
              </Button>
            </>
          }
        />
      }
    >
      <AsyncView state={state}>
        {() => (
          <>
            <div style={{ padding: "8px 16px", fontSize: 12, color: "var(--color-text-secondary)" }}>
              {paged.shown.toLocaleString()} / {paged.total.toLocaleString()}건
            </div>
            <NoticeTable rows={paged.page} showDday />
            {paged.hasMore ? (
              <div style={{ padding: 16 }}>
                <Button variant="secondary" onClick={paged.more}>
                  더 보기
                </Button>
              </div>
            ) : null}
          </>
        )}
      </AsyncView>
    </ListPageLayout>
  );
}
