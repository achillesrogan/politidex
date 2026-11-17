import assert from "node:assert/strict";
import test from "node:test";
import { HOW_TO_READ, READING_TERMS } from "./reading-terms.mjs";

const OFFICIAL = new Set([
  "www.fec.gov",
  "www.congress.gov",
  "lobbyingdisclosure.house.gov",
  "lda.senate.gov",
]);

test("reading terms are plain definitions with official sources", () => {
  const ids = READING_TERMS.map((term) => term.id);
  assert.deepEqual(ids, ["jfc", "pac", "super-pac", "ie", "lobbying-report", "ld-203"]);
  for (const term of READING_TERMS) {
    assert.ok(term.plain.length > 40, term.id);
    assert.equal(term.plain, term.plain.trim());
    assert.doesNotMatch(term.plain, /influence|score|corrupt|bought/i);
    const url = new URL(term.source_url);
    assert.equal(url.protocol, "https:");
    assert.ok(OFFICIAL.has(url.hostname), term.source_url);
  }
  assert.match(HOW_TO_READ, /does not add an influence score/);
});
