export function fmtEok(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return "-";
  return `${Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}억`;
}

export function fmtDateTime(v: string | null | undefined): string {
  return v ? v.slice(0, 16) : "-";
}

export function fmtNum(v: number | null | undefined): string {
  return v == null ? "-" : v.toLocaleString("ko-KR");
}
