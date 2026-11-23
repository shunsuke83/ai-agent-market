import { useMemo, useState } from "react";
import { EmptyState, ListControl, ListPageLayout } from "@genonai/admin-design-system";
import AsyncView from "./AsyncView";
import { IS_INTERNAL } from "../config";
import { useAsync } from "../hooks/useAsync";
import type { ReactNode } from "react";

/**
 * List page for a dataset loaded from the data client. `load` resolves to `null` when the
 * current mode does not provide the dataset.
 */
export default function DatasetListPage<Row extends object>({
  title,
  description,
  load,
  render,
  searchText,
}: {
  title: string;
  description?: string;
  load: () => Promise<Row[] | null>;
  render: (rows: Row[]) => ReactNode;
  searchText?: (row: Row) => string;
}) {
  const [q, setQ] = useState("");
  const state = useAsync(load, []);

  const filtered = useMemo(() => {
    if (state.status !== "ready" || !state.data) return [];
    const needle = q.trim().toLowerCase();
    if (!needle || !searchText) return state.data;
    return state.data.filter((r) => searchText(r).toLowerCase().includes(needle));
  }, [state, q, searchText]);

  return (
    <ListPageLayout
      title={title}
      description={description}
      toolbar={searchText ? <ListControl search="검색" searchValue={q} onSearchChange={setQ} /> : undefined}
    >
      <AsyncView state={state}>
        {(data) =>
          data === null ? (
            <EmptyState
              title="이 모드에서는 제공되지 않는 데이터입니다"
              description={IS_INTERNAL ? "내부 API에 해당 데이터가 없습니다." : "공개 데이터가 아직 배포되지 않았습니다."}
            />
          ) : (
            render(filtered)
          )
        }
      </AsyncView>
    </ListPageLayout>
  );
}
