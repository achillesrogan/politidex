/** The publish gate is the route handlers, not a helper called beside them. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { register } from "node:module";
import path from "node:path";
import test from "node:test";
import { moneyflowSourceReady, moneyflowSources, withMoneyflowFixture } from "./moneyflow-http.mjs";

register(new URL("../scripts/route-test-hook.mjs", import.meta.url));

const root = process.cwd();
const indexRoute = await import("../app/api/moneyflow/route.ts");
const shardRoute = await import("../app/api/moneyflow/[id]/route.ts");

function publishedManifest() {
  return JSON.parse(readFileSync(path.join(root, "data", "moneyflow", "pilot", "manifest.json"), "utf8"));
}

test("a gated manifest hides the index and returns 404 for a real shard", async () => {
  const manifest = publishedManifest();
  const row = (manifest.pilot || []).find((item) => item && item.committee_id);
  assert.ok(row, "pilot manifest has a committee");
  const id = row.committee_id;
  const shard = JSON.parse(readFileSync(path.join(root, "data", "moneyflow", "pilot", "shards", `${id}.json`), "utf8"));
  assert.equal(moneyflowSources(shard).every((source) => moneyflowSourceReady(source)), true);
  const gated = { ...manifest, not_in_web_bundle: true, pilot: manifest.pilot };

  await withMoneyflowFixture({ manifest: gated, purposes: { committees: [] } }, async () => {
    const index = await indexRoute.GET(new Request("https://politidex.icu/api/moneyflow"));
    assert.equal(index.status, 200);
    const body = await index.json();
    assert.deepEqual(body.committees, []);

    const shardResponse = await shardRoute.GET(new Request(`https://politidex.icu/api/moneyflow/${id}`), {
      params: Promise.resolve({ id }),
    });
    assert.equal(shardResponse.status, 404);
  });
});

test("the money-flow page and deploy note state the counting rules", () => {
  const page = readFileSync(path.join(root, "app/money-flow/page.tsx"), "utf8");
  const deploy = readFileSync(path.join(root, "docs/DEPLOY.md"), "utf8");
  for (const text of [page, deploy]) {
    assert.match(text, /Repeated SUB_IDs count once/);
    assert.match(text, /Zero-dollar rows are excluded/);
    assert.match(text, /Type 42 recount-account disbursements are included/);
    assert.match(text, /Negative rows are netted/);
  }
  assert.match(deploy, /moneyflow\.py fetch --refresh/);
  assert.doesNotMatch(deploy, /moneyflow\.py fetch`/);
});
