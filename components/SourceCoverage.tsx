import fs from "node:fs";
import path from "node:path";
import { coverageSentence } from "@/lib/career-coverage.mjs";

export default function SourceCoverage() {
  let year: number | null = null;
  try {
    const file = path.join(process.cwd(), "data", "career", "congress.json");
    const data = JSON.parse(fs.readFileSync(file, "utf8")) as { earliest_year?: unknown };
    if (Number.isInteger(data.earliest_year)) year = data.earliest_year as number;
  } catch {
    year = null;
  }
  return <p className="mt-2 text-sm text-[var(--color-muted)]">{coverageSentence(year)}</p>;
}
