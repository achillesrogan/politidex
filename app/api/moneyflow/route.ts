import { readFileSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { MONEYFLOW_CACHE, MONEYFLOW_ERROR } from "@/lib/moneyflow-http.mjs";

/** Slim index. Shard files are not imported into the client bundle. */
export function GET() {
  try {
    const file = path.join(process.cwd(), "data", "moneyflow", "pilot", "manifest.json");
    const manifest = JSON.parse(readFileSync(file, "utf8"));
    const purposeFile = path.join(process.cwd(), "data", "moneyflow", "purposes.json");
    const purposeDoc = JSON.parse(readFileSync(purposeFile, "utf8"));
    const purposes: Record<string, unknown> = {};
    for (const entry of purposeDoc.committees || []) {
      if (entry && entry.review_status === "approved" && entry.committee_id) purposes[entry.committee_id] = entry;
    }
    const shown = manifest.not_in_web_bundle !== true;
    const committees = shown ? (manifest.pilot || []).map((row: { committee_id?: string; name?: string; party?: string | null; official_total_out?: string; coverage_end?: string | null; selection_rule?: string }) => ({
      committee_id: row.committee_id,
      name: row.name,
      party: row.party || null,
      official_total_out: row.official_total_out,
      coverage_end: row.coverage_end || null,
      selection_rule: row.selection_rule,
    })) : [];
    return NextResponse.json(
      {
        cycle: manifest.cycle,
        fungibility_note: manifest.fungibility_note,
        committees,
        purposes,
      },
      { headers: { "cache-control": MONEYFLOW_CACHE } },
    );
  } catch {
    return NextResponse.json(MONEYFLOW_ERROR, {
      status: 500,
      headers: { "cache-control": "no-store" },
    });
  }
}
