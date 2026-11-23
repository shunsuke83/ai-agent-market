import type { ReactNode } from "react";
import { Alert, Spinner } from "@genonai/admin-design-system";
import type { AsyncState } from "../hooks/useAsync";

/** Renders spinner / error alert / content for a useAsync state. */
export default function AsyncView<T>({
  state,
  children,
}: {
  state: AsyncState<T>;
  children: (data: T) => ReactNode;
}) {
  if (state.status === "loading") return <Spinner />;
  if (state.status === "error") {
    return (
      <div style={{ padding: 16 }}>
        <Alert tone="danger" title="데이터를 불러오지 못했습니다">
          {state.error}
        </Alert>
      </div>
    );
  }
  return <>{children(state.data)}</>;
}
