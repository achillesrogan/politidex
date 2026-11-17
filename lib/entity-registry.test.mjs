import assert from "node:assert/strict";
import test from "node:test";
import { badgeForClaim, confidenceBadge, entityRecord, findEntity, latestRetrieved, registryIndex } from "./entity-registry.mjs";

test("a name without an official source is not an entity", () => {
  assert.equal(entityRecord({ kind: "member", name: "Example", source_name: "Congress.gov" }), null);
  assert.equal(entityRecord({ kind: "member", name: "Example", source_name: "Congress.gov", source_url: "http://www.congress.gov/member/x/A000001" }), null);
});

test("confidence badges are only the three allowed labels", () => {
  const exact = entityRecord({
    kind: "member",
    name: "Example",
    official_id: "A000001",
    source_name: "Congress.gov",
    source_url: "https://www.congress.gov/member/example/A000001",
    retrieved_at: "2026-11-17T00:00:00Z",
  });
  assert.equal(exact.badge, "exact ID match");
  assert.equal(confidenceBadge({ amended: true, official_id: "A000001", source_url: exact.source_url }), "amended filing");
  assert.equal(confidenceBadge({ review_status: "proposed", amended: true, official_id: "A000001", source_url: exact.source_url }), "proposed / in review");
  assert.equal(confidenceBadge({ official_id: "A000001", source_url: "https://www.congress.gov/member/example" }), null);
  assert.equal(badgeForClaim({ source_url: "https://www.fec.gov/data/committee/C00000001/", check: { committee_id: "C00000001" } }), "exact ID match");
  assert.equal(badgeForClaim({ source_url: "https://www.fec.gov/data/committee/C00000001/", check: { committee_id: "C0000000" } }), null);
  assert.equal(badgeForClaim({ source_url: "https://clerk.house.gov/xml/lists/MemberData.xml", check: { bioguide: "A000001", kind: "house-committee" } }), null);
  const disbursements = "https://www.fec.gov/data/disbursements/?committee_id=C00000001&recipient_committee_id=C00401224&two_year_transaction_period=2026";
  assert.equal(badgeForClaim({ source_url: disbursements, check: { match: { committee_id: "C00000001" } } }), "exact ID match");
  assert.equal(badgeForClaim({ source_url: disbursements, check: { committee_id: "C00401224" } }), "exact ID match");
  assert.equal(badgeForClaim({ source_url: disbursements, check: { committee_id: "C0000000" } }), null);
  assert.equal(confidenceBadge({ official_id: "data", source_url: "https://www.fec.gov/data/committee/C00000001/" }), null);
  assert.equal(confidenceBadge({ official_id: "C00000001", source_url: "https://www.congress.gov/data/committee/C00000001/" }), null);
  assert.equal(confidenceBadge({ official_id: "C00000001", source_url: "https://evil.example/data/disbursements/?committee_id=C00000001" }), null);
  assert.equal(confidenceBadge({ official_id: "A000001", source_url: "https://api.congress.gov/v3/member/A000001" }), null);
  assert.equal(confidenceBadge({ official_id: "A000001", source_url: "https://www.fec.gov/data/committee/A000001/" }), null);
  assert.equal(confidenceBadge({ official_id: "A000001", source_url: "https://bioguide.congress.gov/search/bio/A000001" }), null);
  assert.equal(confidenceBadge({ official_id: "A000001", source_url: "https://user:pass@www.congress.gov/member/example/A000001" }), null);
  const senate = "https://www.senate.gov/general/committee_membership/committee_memberships_SSEV.xml";
  assert.equal(confidenceBadge({ official_id: "SSEV", source_url: senate }), "exact ID match");
  assert.equal(confidenceBadge({ official_id: "SSAP", source_url: senate }), null);
  assert.equal(confidenceBadge({ official_id: "SSEV", source_url: "https://evil.example/committee_memberships_SSEV.xml" }), null);
  assert.equal(confidenceBadge({ official_id: "SSEV", source_url: "https://user:pass@www.senate.gov/general/committee_membership/committee_memberships_SSEV.xml" }), null);
});

test("the registry finds a committee or bill only by its own id", () => {
  const bill = entityRecord({
    kind: "bill",
    name: "H.R. 1",
    official_id: "119th-congress/house-bill/1",
    source_name: "Congress.gov",
    source_url: "https://www.congress.gov/bill/119th-congress/house-bill/1",
  });
  const pac = entityRecord({
    kind: "pac",
    name: "Example PAC",
    official_id: "C00000001",
    source_name: "Federal Election Commission",
    source_url: "https://www.fec.gov/data/committee/C00000001/",
    href: "/org/example-pac",
  });
  const index = registryIndex([bill, pac, null]);
  assert.equal(findEntity(index, "bill", "119th-congress/house-bill/1").name, "H.R. 1");
  assert.equal(findEntity(index, "pac", "119th-congress/house-bill/1"), null);
  assert.equal(pac.href, "/org/example-pac");
  assert.equal(latestRetrieved(["2026-11-01T00:00:00Z", "2026-11-17T00:00:00Z", ""]), "2026-11-17T00:00:00Z");
});
