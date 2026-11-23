import { Badge, type BadgeTone } from "@genonai/admin-design-system";
import type { FitVerdict } from "../data/types";

const FIT_LABEL: Record<FitVerdict, string> = { GO: "참여", REVIEW: "검토", "NO-GO": "보류" };
const FIT_TONE: Record<FitVerdict, BadgeTone> = { GO: "success", REVIEW: "warning", "NO-GO": "danger" };

export function fitLabel(v: FitVerdict): string {
  return FIT_LABEL[v];
}

export default function FitBadge({
  verdict,
  score,
}: {
  verdict?: FitVerdict | null;
  score?: number | null;
}) {
  if (!verdict) return null;
  const label = FIT_LABEL[verdict] ?? verdict;
  const scoreText = score != null && Number.isFinite(Number(score)) ? ` ${score}점` : "";
  return <Badge tone={FIT_TONE[verdict] ?? "neutral"}>{`${label}${scoreText}`}</Badge>;
}
