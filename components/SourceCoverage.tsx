import { coverageSentence } from "@/lib/career-coverage.mjs";
import { readCoverage } from "@/lib/career-record.mjs";

export default function SourceCoverage({ firstYear }: { firstYear?: number | null }) {
  let sentence = "";
  try {
    sentence = coverageSentence(firstYear ?? null, readCoverage());
  } catch {
    return null;
  }
  return <p className="mt-2 text-sm text-[var(--color-muted)]">{sentence}</p>;
}
