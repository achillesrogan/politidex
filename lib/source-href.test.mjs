import assert from "node:assert/strict";
import test from "node:test";
import { officialGovHref, publicSourceHref } from "./source-href.mjs";

test("a candidate page drops the cycle that makes FEC return 404", () => {
  assert.equal(
    publicSourceHref("https://www.fec.gov/data/candidate/S4VT00033/?cycle=2026"),
    "https://www.fec.gov/data/candidate/S4VT00033/",
  );
  assert.equal(
    publicSourceHref("https://www.fec.gov/data/candidate/S4CA00555/?cycle=2026"),
    "https://www.fec.gov/data/candidate/S4CA00555/",
  );
});

test("a candidate page that already has no cycle is unchanged", () => {
  assert.equal(
    publicSourceHref("https://www.fec.gov/data/candidate/H2FL04211/?cycle=2026&tab=summary"),
    "https://www.fec.gov/data/candidate/H2FL04211/?tab=summary",
  );
});

test("committee, disbursement, and other hosts keep their query", () => {
  const committee = "https://www.fec.gov/data/committee/C00406553/?cycle=2026";
  assert.equal(publicSourceHref(committee), committee);
  const disb = "https://www.fec.gov/data/disbursements/?committee_id=C00003251&recipient_committee_id=C00406553&two_year_transaction_period=2026";
  assert.equal(publicSourceHref(disb), disb);
  assert.equal(publicSourceHref("https://www.congress.gov/bill/119th-congress/senate-bill/1"), "https://www.congress.gov/bill/119th-congress/senate-bill/1");
});

test("non-web and credentialed URLs are not linked", () => {
  assert.equal(publicSourceHref("javascript:alert(1)"), null);
  assert.equal(publicSourceHref("http://www.fec.gov/data/candidate/S4VT00033/"), null);
  assert.equal(publicSourceHref("https://user:pass@www.fec.gov/data/candidate/S4VT00033/"), null);
  assert.equal(publicSourceHref(""), null);
});

test("a committee website is https on a .gov host or it is omitted", () => {
  assert.equal(officialGovHref("https://www.budget.senate.gov/"), "https://www.budget.senate.gov/");
  assert.equal(officialGovHref("https://clerk.house.gov/committees/AG00"), "https://clerk.house.gov/committees/AG00");
  assert.equal(officialGovHref("https://www.fec.gov/data/committee/C00003418/"), "https://www.fec.gov/data/committee/C00003418/");
  assert.equal(officialGovHref("http://www.senate.gov/committees/"), null);
  assert.equal(officialGovHref("https://example.com/committee"), null);
  assert.equal(officialGovHref("https://senate.gov.evil.example/"), null);
});
