import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { committeeDates, moneyFlowDates, newestRetrieved } from "./page-as-of.mjs";

const root = process.cwd();

test("money-flow and committee pages use their own November 17 retrieval dates", () => {
  const manifest = JSON.parse(readFileSync(path.join(root, "data/moneyflow/pilot/manifest.json"), "utf8"));
  const purposes = JSON.parse(readFileSync(path.join(root, "data/moneyflow/purposes.json"), "utf8"));
  const sites = JSON.parse(readFileSync(path.join(root, "data/committees/sites.json"), "utf8"));
  const money = newestRetrieved(moneyFlowDates(manifest, purposes));
  const committees = newestRetrieved(committeeDates(sites));
  assert.equal(money > manifest.retrieved_at, true);
  assert.equal(money.startsWith("2026-11-17"), true);
  assert.equal(committees, "2026-11-17T02:54:55+00:00");
  assert.equal(newestRetrieved([money, committees, "2026-01-01T00:00:00Z"]), committees);
});
