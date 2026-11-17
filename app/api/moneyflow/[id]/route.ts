import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { MONEYFLOW_CACHE, MONEYFLOW_ERROR, moneyflowFixture, moneyflowPublished, moneyflowSourceReady, moneyflowSources, pilotCommitteeIds } from "@/lib/moneyflow-http.mjs";

const ID = /^C[0-9]{8}$/;

export async function GET(_req: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    if (!ID.test(id)) {
      return NextResponse.json({ error: "Unknown committee." }, { status: 404, headers: { "cache-control": "no-store" } });
    }
    const manifestPath = path.join(process.cwd(), "data", "moneyflow", "pilot", "manifest.json");
    const fixture = moneyflowFixture();
    const manifest = (fixture?.manifest ?? JSON.parse(readFileSync(manifestPath, "utf8"))) as { not_in_web_bundle?: boolean; pilot?: Array<{ committee_id?: string }> };
    if (!moneyflowPublished(manifest) || !pilotCommitteeIds(manifest).has(id)) {
      return NextResponse.json({ error: "No shard for this committee." }, { status: 404, headers: { "cache-control": "no-store" } });
    }
    const dir = path.resolve(process.cwd(), "data", "moneyflow", "pilot", "shards");
    const file = path.resolve(dir, `${id}.json`);
    if (!file.startsWith(dir + path.sep) || !existsSync(file)) {
      return NextResponse.json({ error: "No shard for this committee." }, { status: 404, headers: { "cache-control": "no-store" } });
    }
    const shard = JSON.parse(readFileSync(file, "utf8"));
    if (!moneyflowSources(shard).every((source) => moneyflowSourceReady(source))) {
      return NextResponse.json({ error: "No shard for this committee." }, { status: 404, headers: { "cache-control": "no-store" } });
    }
    return NextResponse.json(shard, {
      headers: { "cache-control": MONEYFLOW_CACHE },
    });
  } catch {
    return NextResponse.json(MONEYFLOW_ERROR, {
      status: 500,
      headers: { "cache-control": "no-store" },
    });
  }
}
