import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { committeeDates, ldaClaimDates, moneyFlowDates, newestRetrieved, profileAsOf } from "./page-as-of.mjs";

const root = process.cwd();

function read(rel) {
  return JSON.parse(readFileSync(path.join(root, rel), "utf8"));
}

test("money-flow and committee dates come from retrieval times in the files", () => {
  const manifest = read("data/moneyflow/pilot/manifest.json");
  const purposes = read("data/moneyflow/purposes.json");
  const sites = read("data/committees/sites.json");
  const moneyExpected = [manifest.retrieved_at, purposes.retrieved_at];
  for (const row of purposes.committees || []) {
    moneyExpected.push(row.retrieved_at, row.source && row.source.retrieved_at);
  }
  const committeeExpected = [sites.retrieved_at];
  for (const source of sites.sources || []) committeeExpected.push(source.retrieved_at);
  for (const row of Object.values(sites.committees || {})) {
    committeeExpected.push(row.retrieved_at, row.website_retrieved_at);
  }
  assert.equal(newestRetrieved(moneyFlowDates(manifest, purposes)), newestRetrieved(moneyExpected));
  assert.equal(newestRetrieved(committeeDates(sites)), newestRetrieved(committeeExpected));
  assert.equal(newestRetrieved(moneyFlowDates(manifest, purposes)) > manifest.retrieved_at, true);
});

test("an approval time does not set the money-flow date", () => {
  const manifest = { retrieved_at: "2001-01-01T00:00:00Z" };
  const purposes = {
    retrieved_at: "2001-01-02T00:00:00Z",
    committees: [{
      retrieved_at: "2001-01-03T00:00:00Z",
      approved_at: "2009-12-31T23:00:00Z",
      source: { retrieved_at: "2001-01-04T00:00:00Z" },
    }],
  };
  assert.equal(
    newestRetrieved(moneyFlowDates(manifest, purposes)),
    purposes.committees[0].source.retrieved_at,
  );
});

test("a profile date stays inside that page's committee sites", () => {
  const sites = read("data/committees/sites.json");
  const purposes = read("data/moneyflow/purposes.json");
  const manifest = read("data/moneyflow/pilot/manifest.json");
  const globalCommittee = newestRetrieved(committeeDates(sites));
  const money = newestRetrieved(moneyFlowDates(manifest, purposes));
  const later = newestRetrieved([globalCommittee, money]);
  const claim = "1998-05-05T00:00:00Z";
  const fixture = {
    shown: { website_retrieved_at: "1999-01-01T00:00:00Z" },
    other: { website_retrieved_at: later },
  };
  assert.equal(profileAsOf([claim], ["shown"], fixture), fixture.shown.website_retrieved_at);
  assert.ok(profileAsOf([claim], ["shown"], fixture) < later);
  assert.equal(profileAsOf([claim], ["not-on-this-page"], fixture), claim);
  assert.equal(profileAsOf([claim], [], fixture), claim);

  const committees = sites.committees;
  const codes = Object.keys(committees);
  const ownDate = (code) => newestRetrieved([committees[code].retrieved_at, committees[code].website_retrieved_at]);
  const undated = codes.filter((code) => ownDate(code) === null);
  const dated = codes.filter((code) => ownDate(code));
  assert.ok(undated.includes("SSEV09"));
  assert.ok(dated.includes("SSEV"));
  for (const code of undated) {
    assert.equal(profileAsOf([claim], [code], committees), claim);
  }
  for (const code of dated) {
    assert.equal(profileAsOf([claim], [code], committees), newestRetrieved([claim, ownDate(code)]));
    assert.notEqual(profileAsOf([claim], [undated[0]], committees), ownDate(code));
  }
  assert.equal(profileAsOf([claim], ["SSEV09"], committees), claim);
  assert.notEqual(profileAsOf([claim], ["SSEV09"], committees), ownDate("SSEV"));

  const ties = {
    lobbying: { rows: [{ claim: "lda-lobby" }] },
    revolving: { rows: [{ claim: "lda-revolving" }] },
    money: { rows: [{ claim: "fec-money" }] },
  };
  const retrieved = {
    "lda-lobby": "2002-02-02T00:00:00Z",
    "lda-revolving": "2003-03-03T00:00:00Z",
    "fec-money": "2009-09-09T00:00:00Z",
  };
  const ldaDates = ldaClaimDates(ties, (id) => retrieved[id]);
  assert.deepEqual(ldaDates, ["2002-02-02T00:00:00Z", "2003-03-03T00:00:00Z"]);
  assert.equal(profileAsOf([claim, ...ldaDates], ["SSEV09"], committees), "2003-03-03T00:00:00Z");

  const page = readFileSync(path.join(root, "app/p/[slug]/page.tsx"), "utf8");
  assert.equal(page.includes("moneyFlowAsOf"), false);
  assert.equal(page.includes("committeeAsOf"), false);
  assert.match(page, /committeeSite/);
  assert.match(page, /ldaClaimDates/);
});
