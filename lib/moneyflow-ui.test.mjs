import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import {
  FEC_MASTER_URL,
  FEC_NONCONNECTED_URL,
  FEC_TYPE_URL,
  FLOW_LEGEND,
  FLOW_PALETTE,
  FUNGIBILITY_NOTE,
  MAX_DEPTH,
  applyFilters,
  barPercent,
  buildVisible,
  canExpand,
  contrastRatio,
  createNestedList,
  entityFacts,
  flowOf,
  hasSource,
  layoutTree,
  plainCommitteeKind,
  presentCommittees,
  shardUrl,
  strokeWidth,
} from "./moneyflow-ui.mjs";

const root = path.join(import.meta.dirname, "..");
const src = (id) => ({
  source_name: "Federal Election Commission",
  source_url: "https://www.fec.gov/data/committee/" + id + "/",
  retrieved_at: "2026-11-17T00:00:00+00:00",
  excerpt: "Reported amount for " + id + ".",
  text: "Reported amount for " + id + ".",
});

function child(name, kind, cents, code, id) {
  return {
    node: {
      id: kind + ":" + name,
      name,
      kind,
      official_id: id || null,
      terminal: kind === "business" || kind === "residual",
      terminal_label: kind === "business" ? "Spent" : null,
      period: { cycle: 2026 },
      source: src(name),
    },
    edge: {
      id: "e-" + name,
      kind: kind === "business" ? "spent" : "reported transfer",
      amount: (cents / 100).toFixed(2),
      amount_cents: cents,
      purpose: null,
      purpose_code: code,
      source: src("edge-" + name),
    },
  };
}

function shard(id, name, children, cycle = 2026) {
  return {
    cycle,
    fungibility_note: FUNGIBILITY_NOTE,
    node: { id: "committee:" + id, name, kind: "party", official_id: id, terminal: false, source: src(id), official_total_out: "15.00" },
    children,
  };
}

test("fungibility note matches the wording file", () => {
  const words = JSON.parse(readFileSync(path.join(root, "data/moneyflow/wording.json"), "utf8"));
  assert.equal(FUNGIBILITY_NOTE, words.fungibility_note);
  assert.doesNotMatch(FUNGIBILITY_NOTE, /funnel|earmark|bought influence/i);
});

test("filters, source gate, and amount text", () => {
  const rows = [
    child("ACME", "business", 1000, "001"),
    child("OTHER", "party", 500, "24G", "C00000002"),
    { node: { name: "UNSOURCED", kind: "business", source: {} }, edge: { amount_cents: 9000, amount: "90.00", kind: "spent", source: src("x") } },
  ];
  const base = shard("C00000001", "ROOT", rows);
  const view = buildVisible(base, { filters: {}, expanded: new Set(), loaded: new Map(), shardIds: new Set() });
  assert.equal(view.children.length, 2);
  assert.equal(view.children.some((c) => c.name === "UNSOURCED"), false);
  const min = buildVisible(base, { filters: { minCents: 600 }, expanded: new Set(), loaded: new Map(), shardIds: new Set() });
  assert.deepEqual(min.children.map((c) => c.name), ["ACME"]);
  const kind = applyFilters(rows, { kind: "party" });
  assert.equal(kind.length, 1);
  const purpose = applyFilters(rows, { purpose: "24G" });
  assert.equal(purpose[0].node.name, "OTHER");
  const html = renderToStaticMarkup(createNestedList(view, {}));
  assert.match(html, /ACME/);
  assert.match(html, /\$10\.00/);
  assert.match(html, /role="tree"/);
  assert.doesNotMatch(html, /UNSOURCED/);
  assert.equal(hasSource({}), false);
});

test("narrow list bars and buttons", () => {
  const view = buildVisible(shard("C00000001", "ROOT", [child("ACME", "business", 1000, "001"), child("BETA", "business", 250, "002")]), {
    filters: {}, expanded: new Set(), loaded: new Map(), shardIds: new Set(),
  });
  const html = renderToStaticMarkup(createNestedList(view, {}));
  assert.match(html, /<button/);
  assert.match(html, /Record/);
  assert.match(html, /width:100%/);
  assert.match(html, /width:25%/);
  assert.ok(barPercent(1000, 1000) >= barPercent(250, 1000));
});

test("lazy shard urls stay on this app and depth stops at 6", () => {
  assert.equal(shardUrl("C00000001"), "/api/moneyflow/C00000001");
  assert.equal(shardUrl("../oth26"), null);
  assert.equal(shardUrl("https://api.open.fec.gov/v1"), null);
  const ids = new Set(["C00000002"]);
  const childNode = { terminal: false, kind: "party", officialId: "C00000002" };
  assert.equal(canExpand(childNode, 2, ids), true);
  assert.equal(canExpand(childNode, MAX_DEPTH, ids), false);
  assert.equal(canExpand({ terminal: true, kind: "business", officialId: "C00000002" }, 2, ids), false);
  const chain = shard("C00000001", "ROOT", [child("NEXT", "party", 100, "24G", "C00000002")]);
  let current = chain;
  const loaded = new Map();
  const expanded = new Set();
  for (let level = 2; level <= 8; level += 1) {
    const id = "C" + String(level).padStart(8, "0");
    const next = "C" + String(level + 1).padStart(8, "0");
    loaded.set(current.node.official_id, current);
    ids.add(current.node.official_id);
    current = shard(id, "L" + level, [child("N" + level, "party", 100, "24G", next)]);
  }
  ids.add("C00000001");
  const top = loaded.get("C00000001");
  const view = buildVisible(top, { filters: {}, expanded, loaded, shardIds: ids });
  const walk = (node, depth = 1) => {
    assert.ok(depth <= MAX_DEPTH);
    (node.children || []).forEach((child) => walk(child, depth + 1));
  };
  walk(view);
});

test("party committees share one control class", () => {
  const shown = presentCommittees([
    { committee_id: "D1", party: "DEM", selection_rule: "party-qualified-top3", name: "D one" },
    { committee_id: "D2", party: "DEM", selection_rule: "party-qualified-top3", name: "D two" },
    { committee_id: "R1", party: "REP", selection_rule: "party-qualified-top3", name: "R one" },
    { committee_id: "R2", party: "REP", selection_rule: "party-qualified-top3", name: "R two" },
    { committee_id: "P", party: null, selection_rule: "org-type-largest-no-party", name: "Pac" },
  ]);
  assert.deepEqual(shown.map((c) => c.committee_id), ["D1", "R1", "D2", "R2", "P"]);
  assert.equal(new Set(shown.map((c) => c.controlClass)).size, 1);
});

test("stroke width grows with the amount and stays one scale", () => {
  assert.ok(strokeWidth(100, 100) > strokeWidth(10, 100));
  assert.equal(strokeWidth(50, 100), strokeWidth(50, 100));
});

test("opening a recipient with a shard shows the next level", () => {
  const childShard = shard("C00000002", "CHILD", [child("PAYEE", "business", 400, "001")]);
  const top = shard("C00000001", "ROOT", [child("CHILD", "party", 500, "24G", "C00000002")]);
  const ids = new Set(["C00000001", "C00000002"]);
  const loaded = new Map([["C00000002", childShard]]);
  const closed = buildVisible(top, { filters: {}, expanded: new Set(), loaded, shardIds: ids });
  assert.equal(closed.children[0].expandable, true);
  assert.equal(closed.children[0].children, null);
  const expanded = buildVisible(top, { filters: {}, expanded: new Set([closed.children[0].key]), loaded, shardIds: ids });
  assert.equal(expanded.children[0].expanded, true);
  assert.equal(expanded.children[0].children[0].name, "PAYEE");
  assert.equal(expanded.children[0].children[0].depth, 3);
});

test("layout includes a line and a label for each sourced child", () => {
  const view = buildVisible(shard("C00000001", "ROOT", [child("ACME", "business", 1000, "001")]), {
    filters: {}, expanded: new Set(), loaded: new Map(), shardIds: new Set(),
  });
  const layout = layoutTree(view);
  assert.equal(layout.nodes.length, 2);
  assert.equal(layout.links.length, 1);
  assert.ok(layout.links[0].cents === 1000);
});

test("client code does not import shard files", () => {
  const files = [
    "app/money-flow/page.tsx",
    "components/moneyflow/MoneyFlowExplorer.tsx",
    "lib/moneyflow-ui.mjs",
  ];
  for (const file of files) {
    const text = readFileSync(path.join(root, file), "utf8");
    assert.equal(text.includes("pilot/shards/"), false, file);
    assert.equal(text.includes("api.open.fec.gov"), false, file);
    assert.equal(/api_key=|DATA_GOV_API_KEY/.test(text), false, file);
  }
  const clientDir = path.join(root, "components", "moneyflow");
  for (const name of readdirSync(clientDir)) {
    const text = readFileSync(path.join(clientDir, name), "utf8");
    assert.equal(text.includes("from \"@/data"), false, name);
  }
});

test("colors follow the reported kind and clear WCAG AA", () => {
  const transfer = { kind: "party", edgeKind: "reported transfer", party: "DEM" };
  const same = { kind: "party", edgeKind: "reported transfer", party: "REP" };
  assert.equal(flowOf(transfer), flowOf(same));
  assert.equal(flowOf({ kind: "business", edgeKind: "spent", terminalLabel: "Spent" }), "spent");
  assert.equal(flowOf({ kind: "candidate_committee", edgeKind: "reported contribution" }), "contribution");
  assert.equal(flowOf({ kind: "residual", name: "reported assistance to individuals — not itemized" }), "individuals");
  assert.equal(flowOf({ kind: "residual", name: "other reported disbursements" }), "other");
  assert.equal(Object.keys(FLOW_PALETTE).includes("DEM") || Object.keys(FLOW_PALETTE).includes("REP"), false);
  for (const item of FLOW_LEGEND) {
    assert.ok(contrastRatio(item.color, "#ffffff") >= 4.5, item.id);
    assert.ok(contrastRatio(item.color, "#f8f6f0") >= 4.5, item.id);
    assert.ok(item.label.length > 0);
  }
  const view = buildVisible(shard("C00000001", "ROOT", [child("ACME", "business", 1000, "001")]), {
    filters: {}, expanded: new Set(), loaded: new Map(), shardIds: new Set(),
  });
  const html = renderToStaticMarkup(createNestedList(view, {}));
  assert.match(html, new RegExp(FLOW_PALETTE.spent.color));
  assert.match(html, /Spent/);
});

function profile(over) {
  return {
    committee_id: "C00000001",
    committee_type: "Y",
    designation: "U",
    party: "REP",
    org_type: null,
    connected_organization: null,
    state: "DC",
    filing_frequency: "M",
    source: {
      source_name: "Federal Election Commission",
      source_url: "https://www.fec.gov/data/committee/C00000001/?cycle=2026&tab=spending",
      retrieved_at: "2026-11-17T00:00:00+00:00",
      excerpt: "Committee master C00000001; type Y; designation U; party REP; filing frequency M; interest group blank; connected organization blank; state DC.",
    },
    ...over,
  };
}

test("entity summary is a template of FEC fields and has a source", () => {
  const party = entityFacts(profile());
  assert.equal(plainCommitteeKind(profile()), "Party committee");
  assert.match(party[0].text, /Party committee/);
  assert.match(party[0].text, /existed for at least six months/);
  assert.equal(party[0].href, FEC_TYPE_URL);
  const dem = entityFacts(profile({ party: "DEM" }));
  const rep = entityFacts(profile({ party: "REP" }));
  assert.equal(
    dem.map((f) => f.text.replace("DEM", "CODE")).join("|"),
    rep.map((f) => f.text.replace("REP", "CODE")).join("|"),
  );
  const ssf = entityFacts(profile({
    committee_type: "Q",
    org_type: "C",
    connected_organization: "EXAMPLE WIDGETS INC",
    party: null,
  }));
  assert.equal(plainCommitteeKind(ssf && profile({ committee_type: "Q", org_type: "C", connected_organization: "EXAMPLE WIDGETS INC" })), "Separate segregated fund (corporate PAC)");
  assert.match(ssf.map((f) => f.text).join(" "), /Separate segregated fund \(corporate PAC\)/);
  assert.match(ssf.map((f) => f.text).join(" "), /always has a sponsoring corporation or labor organization/);
  assert.ok(ssf.some((f) => f.href === FEC_NONCONNECTED_URL));
  assert.ok(ssf.some((f) => f.label === "Connected organization" && f.text === "EXAMPLE WIDGETS INC"));
  const open = entityFacts(profile({ committee_type: "Q", org_type: null, connected_organization: null, party: null }));
  assert.match(open[0].text, /Nonconnected PAC/);
  assert.match(open[0].text, /not a party committee/);
  const superPac = entityFacts(profile({ committee_type: "O", designation: "U", party: null, org_type: null }));
  assert.match(superPac[0].text, /Super PAC \(independent expenditure-only\)/);
  assert.match(superPac[0].text, /AO 2010-09/);
  const all = party.concat(ssf, open, superPac);
  for (const fact of all) {
    assert.match(fact.href, /^https:\/\/www\.fec\.gov\//);
    assert.doesNotMatch(fact.text, /motive|corrupt|bought/i);
  }
  assert.equal(entityFacts({ committee_type: "Y" }).length, 0);
  assert.ok(party.some((f) => f.label === "Filing frequency" && f.href === FEC_MASTER_URL));
  assert.ok(party.some((f) => f.label === "State"));
});

test("record cards use the shared popover", () => {
  for (const file of ["components/SourceCard.tsx", "components/CommitteeInfo.tsx", "components/moneyflow/MoneyFlowExplorer.tsx"]) {
    const text = readFileSync(path.join(root, file), "utf8");
    assert.match(text, /RecordPopover/);
    assert.doesNotMatch(text, /showModal/);
  }
});
