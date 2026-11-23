import { DataTable, EmptyState, type DataTableColumn } from "@genonai/admin-design-system";

type Rec = Record<string, unknown>;

function cell(v: unknown): string {
  if (v == null) return "-";
  if (Array.isArray(v)) return v.map(String).join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Generic table for datasets whose schema is not modelled yet: shows the first scalar keys. */
export default function RecordTable({
  rows,
  maxColumns = 6,
  empty = "데이터가 없습니다.",
}: {
  rows: Rec[];
  maxColumns?: number;
  empty?: string;
}) {
  const first = rows[0] ?? {};
  const keys = Object.keys(first)
    .filter((k) => typeof first[k] !== "object" || first[k] === null || Array.isArray(first[k]))
    .slice(0, maxColumns);
  const columns: DataTableColumn<Rec>[] = keys.map((k) => ({
    key: k,
    header: k,
    render: (r) => cell(r[k]),
  }));
  return <DataTable columns={columns} rows={rows} empty={<EmptyState title={empty} />} />;
}
