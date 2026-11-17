import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next") continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(tsx|ts|mjs|js|py)$/.test(name)) out.push(full);
  }
  return out;
}

test("119th Congress bill counts stay proposed and off the page", () => {
  const file = path.join(root, "data/proposed/committee-bill-counts-119.json");
  const data = JSON.parse(readFileSync(file, "utf8"));
  assert.equal(data.review_status, "proposed");
  assert.equal(data.congress, 119);
  assert.equal(data.committees.length, 230);
  assert.ok(data.committees.every((row) => row.review_status === "proposed"));
  const full = data.committees.filter((row) => !row.is_subcommittee).reduce((sum, row) => sum + row.bills_referred, 0);
  const all = data.committees.reduce((sum, row) => sum + row.bills_referred, 0);
  assert.equal(full, 24665);
  assert.equal(all, 26979);
  assert.equal(data.summary.bills_referred_full_committees, full);
  const text = readFileSync(file, "utf8").toLowerCase();
  assert.equal(text.includes("api_key"), false);
  assert.equal(text.includes("congress_api"), false);
});

test("the Congress.gov link check is recorded and not rendered", () => {
  const file = path.join(root, "data/proposed/congress-link-audit.json");
  const data = JSON.parse(readFileSync(file, "utf8"));
  assert.equal(data.unique_urls, 6168);
  assert.equal(data.ok, 6168);
  assert.equal(data.not_found, 0);
  assert.equal(data.error, 0);
  assert.equal(data.retrieved_on, "2026-11-17");
  assert.equal(data.by_kind.member, 539);
  assert.equal(data.by_kind.bill, 5629);
  assert.match(data.method, /does not call the API/);
  const rendered = walk(path.join(root, "app")).concat(walk(path.join(root, "components")));
  const hits = rendered.filter((filePath) => readFileSync(filePath, "utf8").includes("data/proposed"));
  assert.deepEqual(hits, []);
});
