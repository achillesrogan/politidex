import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { MONEYFLOW_CACHE, MONEYFLOW_ERROR } from "@/lib/moneyflow-http.mjs";

const ID = /^C[0-9]{8}$/;

export async function GET(_req: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    if (!ID.test(id)) {
      return NextResponse.json({ error: "Unknown committee." }, { status: 404, headers: { "cache-control": "no-store" } });
    }
    const dir = path.resolve(process.cwd(), "data", "moneyflow", "pilot", "shards");
    const file = path.resolve(dir, `${id}.json`);
    if (!file.startsWith(dir + path.sep) || !existsSync(file)) {
      return NextResponse.json({ error: "No shard for this committee." }, { status: 404, headers: { "cache-control": "no-store" } });
    }
    return new NextResponse(readFileSync(file, "utf8"), {
      headers: { "content-type": "application/json; charset=utf-8", "cache-control": MONEYFLOW_CACHE },
    });
  } catch {
    return NextResponse.json(MONEYFLOW_ERROR, {
      status: 500,
      headers: { "cache-control": "no-store" },
    });
  }
}
