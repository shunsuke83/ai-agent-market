import { useState } from "react";
import { EmptyState, ListControl, ListPageLayout } from "@genonai/admin-design-system";
import AsyncView from "./AsyncView";
import NoticeTable from "./NoticeTable";
import { dataClient } from "../data/client";
import { useAsync } from "../hooks/useAsync";
import { useDebounced } from "../hooks/useDebounced";

/** Free-text search across notices (used by bidder / agency search pages). */
export default function SearchNoticesPage({
  title,
  description,
  placeholder,
}: {
  title: string;
  description?: string;
  placeholder: string;
}) {
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const state = useAsync(
    () => (q.trim() ? dataClient.listNotices({ q, openOnly: false, limit: 200 }) : Promise.resolve(null)),
    [q],
  );

  return (
    <ListPageLayout
      title={title}
      description={description}
      toolbar={<ListControl search={placeholder} searchValue={search} onSearchChange={setSearch} />}
    >
      <AsyncView state={state}>
        {(res) =>
          res === null ? (
            <EmptyState title="검색어를 입력하세요" description={placeholder} />
          ) : (
            <>
              <div style={{ padding: "8px 16px", fontSize: 12, color: "var(--color-text-secondary)" }}>
                총 {res.total.toLocaleString()}건
              </div>
              <NoticeTable rows={res.items} />
            </>
          )
        }
      </AsyncView>
    </ListPageLayout>
  );
}
