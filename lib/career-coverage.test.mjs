import assert from "node:assert/strict";
import test from "node:test";
import { coverageSentence } from "./career-coverage.mjs";

test("the coverage line names each source start", () => {
  assert.equal(
    coverageSentence(1975),
    "FEC records from 1980; lobbying records from 1999; Congress.gov records from 1975. Individual contribution files are not included.",
  );
  assert.match(coverageSentence(null), /Congress\.gov records from the 119th Congress/);
  assert.doesNotMatch(coverageSentence(1975), /indiv/);
});
