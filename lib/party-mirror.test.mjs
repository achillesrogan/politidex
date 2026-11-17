import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { applyFilters, entityFacts, flowColor, presentCommittees, strokeWidth } from "./moneyflow-ui.mjs";

const PARTY_CODES = ["DEM", "REP", "IND", "LIB", "GRE", "CON"];
const PARTY_NAMES = {
  DEM: "Democrat",
  REP: "Republican",
  IND: "Independent",
  LIB: "Libertarian",
  GRE: "Green",
  CON: "Conservative",
};

function swapParty(value) {
  const next = { DEM: "IND", IND: "LIB", LIB: "GRE", GRE: "CON", CON: "REP", REP: "DEM" };
  if (typeof value === "string" && next[value]) return next[value];
  if (typeof value === "string" && Object.values(PARTY_NAMES).includes(value)) {
    const code = Object.keys(PARTY_NAMES).find((key) => PARTY_NAMES[key] === value);
    return PARTY_NAMES[next[code]];
  }
  if (value === "Democratic") return "Independent";
  if (Array.isArray(value)) return value.map(swapParty);
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, item] of Object.entries(value)) out[key] = swapParty(item);
    return out;
  }
  return value;
}

function neutralize(value) {
  return JSON.stringify(value).replace(/\b(DEM|REP|IND|LIB|GRE|CON|Democrat|Democratic|Republican|Independent|Libertarian|Green|Conservative)\b/g, "PARTY");
}

function sameAfterSwap(label, view) {
  assert.equal(neutralize(view("DEM")), neutralize(view("REP")), label);
}

test("money-flow views do not change when the party code is swapped", () => {
  const committees = [
    { committee_id: "C00000001", party: "DEM", name: "Alpha", official_total_out: "30.00", selection_rule: "party-qualified-top3" },
    { committee_id: "C00000002", party: "REP", name: "Cedar", official_total_out: "10.00", selection_rule: "party-qualified-top3" },
    { committee_id: "C00000003", party: null, name: "Baker", official_total_out: "20.00", selection_rule: "org-type-largest-no-party" },
  ];
  assert.equal(
    neutralize(presentCommittees(committees)),
    neutralize(presentCommittees(swapParty(committees))),
  );

  const profile = (party) => ({
    committee_id: "C00000001",
    committee_type: "Q",
    designation: "U",
    party,
    filing_frequency: "M",
    state: "DC",
    org_type: "T",
    connected_organization: "Example Trade Group",
    source: {
      source_name: "Federal Election Commission",
      source_url: "https://www.fec.gov/data/committee/C00000001/",
      retrieved_at: "2026-11-17T00:00:00Z",
      excerpt: "Committee master C00000001.",
    },
  });
  const demFacts = neutralize(entityFacts(profile("DEM")));
  for (const code of PARTY_CODES) {
    assert.equal(neutralize(entityFacts(profile(code))), demFacts, code);
  }
  sameAfterSwap("entity facts", (party) => entityFacts(profile(party)));

  const node = (party) => ({ name: "Example", kind: "committee", edgeKind: "reported contribution", party, amount_cents: 1500000 });
  sameAfterSwap("flow color", (party) => flowColor(node(party)));
  sameAfterSwap("stroke width", (party) => strokeWidth(node(party).amount_cents, 3000000));

  const children = (party) => [
    { edge: { amount_cents: 500, purpose_code: "001" }, node: { kind: "party", party, period: { cycle: 2026 } } },
    { edge: { amount_cents: 50, purpose_code: "002" }, node: { kind: "business", party, period: { cycle: 2026 } } },
  ];
  sameAfterSwap("filters", (party) => applyFilters(children(party), { minCents: 100, kind: "party", cycle: 2026 }));
});

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(tsx|mjs|ts)$/.test(name)) out.push(full);
  }
  return out;
}

const PARTY_BRANCHES = [
  /party\s*===?\s*["'][^"']+["']\s*\?/,
  /party\s*!==?\s*["']/,
  /party\s*==\s*["']/,
  /switch\s*\(\s*[^)]*\bparty\b[^)]*\)/,
  /\[\s*[A-Za-z0-9_$.]*\bparty\b\s*\]/,
  /\bparty\b\s*\?\?\s*["']/,
  /\bparty\b\.includes\s*\(/,
  /\.includes\s*\(\s*[^)\n]*\bparty\b/,
  /partyColor\s*\(\s*[^)\n]*\bparty\b/,
  /\.find\s*\(\s*(?:[^)\n]|\([^)\n]*\))*\bparty\b/,
];

test("party branches the lint looks for are the ones that change a view", () => {
  const caught = [
    'party === "DEM" ? "blue" : "red"',
    'party == "REP"',
    'p.party !== "IND"',
    'party != "GRE"',
    'switch (p.party) { case "DEM": break; }',
    "colors[p.party]",
    'p.party ?? ""',
    'p.party ?? \'\'',
    'party.includes("DEM")',
    'codes.includes(p.party)',
    "partyColor(p.party)",
    'rows.find((row) => row.party === "DEM")',
  ];
  for (const sample of caught) {
    assert.equal(PARTY_BRANCHES.some((pattern) => pattern.test(sample)), true, sample);
  }
  const allowed = [
    'party === "all" || p.party === party',
    "p.party ? ` · ${p.party}` : \"\"",
    "p.name.toLowerCase().includes(q.toLowerCase())",
    "READING_TERMS.find((item) => item.id === id)",
    "CONFIDENCE_BADGES.includes(badge)",
  ];
  for (const sample of allowed) {
    assert.equal(PARTY_BRANCHES.some((pattern) => pattern.test(sample)), false, sample);
  }
});

test("no view picks a color, order, or metric from a party code", () => {
  const root = process.cwd();
  const files = [...walk(path.join(root, "app")), ...walk(path.join(root, "components"))];
  const hits = [];
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    if (PARTY_BRANCHES.some((pattern) => pattern.test(text))) hits.push(path.relative(root, file));
  }
  assert.deepEqual(hits, []);
});
