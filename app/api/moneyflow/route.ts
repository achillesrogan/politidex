import { readFileSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

/** Slim index. Shard files are not imported into the client bundle. */
export function GET() {
  const file = path.join(process.cwd(), "data", "moneyflow", "pilot", "manifest.json");
  const manifest = JSON.parse(readFileSync(file, "utf8"));
  const committees = (manifest.pilot || []).map((row: any) => ({
    committee_id: row.committee_id,
    name: row.name,
    party: row.party || null,
    official_total_out: row.official_total_out,
    coverage_end: row.coverage_end || null,
    selection_rule: row.selection_rule,
  }));
  return NextResponse.json({
    cycle: manifest.cycle,
    fungibility_note: manifest.fungibility_note,
    committees,
  });
}
