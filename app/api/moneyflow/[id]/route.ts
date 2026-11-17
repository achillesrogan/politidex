import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

const ID = /^C[0-9]{8}$/;

export function GET(_req: Request, context: { params: Promise<{ id: string }> }) {
  return context.params.then(({ id }) => {
    if (!ID.test(id)) return NextResponse.json({ error: "Unknown committee." }, { status: 404 });
    const dir = path.resolve(process.cwd(), "data", "moneyflow", "pilot", "shards");
    const file = path.resolve(dir, `${id}.json`);
    if (!file.startsWith(dir + path.sep) || !existsSync(file)) {
      return NextResponse.json({ error: "No shard for this committee." }, { status: 404 });
    }
    return new NextResponse(readFileSync(file, "utf8"), {
      headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=300" },
    });
  });
}
