import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { sourceCoverageFor } from "./source-coverage.mjs";

test("an executive fixture does not render the coverage line", () => {
  const executive = {
    slug: "jd-vance",
    kind: "executive",
    name: "JD Vance",
    role: "Vice President",
    bioguide: null,
  };
  assert.equal(sourceCoverageFor(executive), null);
  assert.equal(sourceCoverageFor({ slug: "donald-j-trump", kind: "executive" }), null);
  const page = readFileSync(new URL("../app/p/[slug]/page.tsx", import.meta.url), "utf8");
  assert.match(page, /sourceCoverageFor\(\{ bioguide \}\) \? <SourceCoverage/);
  assert.doesNotMatch(page, /<SourceCoverage firstYear=\{firstYear\} \/>\s*$/m);
});

test("a member fixture with a bioguide id renders the coverage line", () => {
  const member = { slug: "bernard-sanders", kind: "legislator", bioguide: "S000033" };
  assert.deepEqual(sourceCoverageFor(member), { bioguide: "S000033" });
});
