import { CONFIDENCE_BADGES } from "@/lib/entity-registry.mjs";

export default function ConfidenceBadge({ badge }: { badge?: string | null }) {
  if (!badge || !CONFIDENCE_BADGES.includes(badge as (typeof CONFIDENCE_BADGES)[number])) return null;
  return <span className="tag ml-2 align-middle">{badge}</span>;
}
