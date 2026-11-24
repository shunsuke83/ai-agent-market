import { useEffect, useMemo, useState } from "react";

const DEFAULT_PAGE = 50;

/** Client-side "load more" paging over an already-filtered list. */
export function usePaged<T>(rows: T[], pageSize = DEFAULT_PAGE, resetKey?: string | number) {
  const [visible, setVisible] = useState(pageSize);

  useEffect(() => {
    setVisible(pageSize);
  }, [pageSize, resetKey, rows.length]);

  const page = useMemo(() => rows.slice(0, visible), [rows, visible]);
  const hasMore = visible < rows.length;
  return {
    page,
    hasMore,
    shown: page.length,
    total: rows.length,
    more: () => setVisible((n) => n + pageSize),
    reset: () => setVisible(pageSize),
  };
}
