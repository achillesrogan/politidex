import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { coverageSentence } from "./career-coverage.mjs";
import { publicBillUrl, sponsoredSearchUrl } from "./career-public.mjs";

const coverage = JSON.parse(readFileSync(new URL("../data/career/coverage.json", import.meta.url), "utf8"));

test("the coverage line names each source start", () => {
  const lda = coverage.lda.begins === coverage.lda.ends
    ? "lobbying records " + coverage.lda.begins
    : "lobbying records " + coverage.lda.begins + "–" + coverage.lda.ends;
  assert.equal(
    coverageSentence(1975, coverage),
    "FEC records from " + coverage.fec.begins + "; " + lda + "; Congress.gov records from 1975. Individual contribution files are not included.",
  );
  assert.match(coverageSentence(1975, coverage), /lobbying records 2025–2026/);
  assert.match(coverageSentence(null, coverage), /Congress\.gov records from the 119th Congress/);
  assert.doesNotMatch(coverageSentence(1975, coverage), /indiv/);
  const source = readFileSync(new URL("./career-coverage.mjs", import.meta.url), "utf8");
  assert.doesNotMatch(source, /\b1980\b|\b1999\b/);
});

test("bill links are rebuilt for the public congress.gov site", () => {
  assert.equal(publicBillUrl(101, "HR", "7"), "https://www.congress.gov/bill/101st-congress/house-bill/7");
  assert.equal(publicBillUrl(119, "S", 12), "https://www.congress.gov/bill/119th-congress/senate-bill/12");
  assert.equal(publicBillUrl(119, "HAMDT", "1"), null);
  assert.equal(
    sponsoredSearchUrl("S000033", 118),
    "https://www.congress.gov/search?q=" + encodeURIComponent('{"source":"legislation","congress":"118","sponsor":"S000033"}'),
  );
});
