import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { MONEYFLOW_CACHE, MONEYFLOW_ERROR, moneyflowErrorResponse } from "./moneyflow-http.mjs";
import {
  FEC_MASTER_URL,
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
  httpsPageHref,
  layoutTree,
  NO_STATED_PURPOSE,
  officialSourceHref,
  blankMasterValue,
  plainCommitteeKind,
  statedPurposeLine,
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

test("committees are ordered by name, not by party", () => {
  const shown = presentCommittees([
    { committee_id: "D1", party: "DEM", selection_rule: "party-qualified-top3", name: "Delta" },
    { committee_id: "R1", party: "REP", selection_rule: "party-qualified-top3", name: "Alpha" },
    { committee_id: "D2", party: "DEM", selection_rule: "party-qualified-top3", name: "Cedar" },
    { committee_id: "P", party: null, selection_rule: "org-type-largest-no-party", name: "Baker" },
  ]);
  assert.deepEqual(shown.map((c) => c.committee_id), ["R1", "P", "D2", "D1"]);
  const flipped = presentCommittees(shown.map((c) => ({ ...c, party: c.party === "DEM" ? "REP" : "DEM" })));
  assert.deepEqual(flipped.map((c) => c.name), shown.map((c) => c.name));
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
    assert.notEqual(item.color.toLowerCase(), "#1f4e79");
    assert.ok(!["#ff0000", "#0000ff", "#e81b23", "#0033a0", "#2e5aac"].includes(item.color.toLowerCase()));
    assert.ok(item.label.length > 0);
  }
  const explorer = readFileSync(path.join(root, "components/moneyflow/MoneyFlowExplorer.tsx"), "utf8");
  const css = readFileSync(path.join(root, "app/globals.css"), "utf8");
  assert.equal(explorer.includes("#1f4e79") || explorer.includes("var(--color-record)"), false);
  assert.match(css, /--mf-neutral:\s*#3d4a59/);
  assert.doesNotMatch(css, /\.moneyflow[^{]*\{[^}]*#1f4e79/);
  assert.doesNotMatch(css, /\.moneyflow[^{]*\{[^}]*var\(--color-record\)/);
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
  const sponsor = profile({
    committee_type: "Q",
    designation: "U",
    org_type: "C",
    connected_organization: "EXAMPLE WIDGETS INC",
    party: null,
  });
  const ssf = entityFacts(sponsor);
  assert.equal(plainCommitteeKind(sponsor), "PAC");
  assert.equal(ssf.map((f) => f.text).join(" ").includes("Separate segregated fund"), false);
  assert.ok(ssf.some((f) => f.label === "Connected organization" && f.text === "EXAMPLE WIDGETS INC"));
  const filedNone = [
    { committee_id: "C00165159", committee_type: "Q", designation: "U" },
    { committee_id: "C00433060", committee_type: "Q", designation: "U" },
    { committee_id: "C00771246", committee_type: "N", designation: "J" },
    { committee_id: "C00649574", committee_type: "N", designation: "J" },
  ];
  for (const row of filedNone) {
    for (const connected of ["NONE", "N/A", "NA", null]) {
      const card = profile({ ...row, org_type: null, connected_organization: connected, party: null });
      const kind = plainCommitteeKind(card);
      const text = entityFacts(card).map((f) => f.text).join(" ");
      assert.equal(kind.includes("Separate segregated fund"), false, row.committee_id);
      assert.equal(text.includes("always has a sponsoring corporation"), false, row.committee_id);
      assert.equal(text.includes("NONE"), false, row.committee_id);
      assert.equal(entityFacts(card).some((f) => f.label === "Connected organization"), false);
    }
  }
  assert.equal(plainCommitteeKind(profile({ committee_type: "Q", designation: "U", connected_organization: "NONE" })), "PAC");
  assert.equal(plainCommitteeKind(profile({ committee_type: "N", designation: "J", connected_organization: "NONE" })), "Joint fundraising committee");
  assert.equal(blankMasterValue("NONE"), "");
  assert.equal(blankMasterValue("N/A"), "");
  assert.equal(blankMasterValue("NA"), "");
  const superPac = entityFacts(profile({ committee_type: "O", designation: "U", party: null, org_type: null }));
  assert.match(superPac[0].text, /Super PAC \(independent expenditure-only\)/);
  assert.match(superPac[0].text, /AO 2010-09/);
  const all = party.concat(ssf, superPac);
  for (const fact of all) {
    assert.match(fact.href, /^https:\/\/www\.fec\.gov\//);
    assert.doesNotMatch(fact.text, /motive|corrupt|bought/i);
  }
  assert.equal(entityFacts({ committee_type: "Y" }).length, 0);
  assert.ok(party.some((f) => f.label === "Filing frequency" && f.href === FEC_MASTER_URL));
  assert.ok(party.some((f) => f.label === "State"));
});

test("only official FEC https links are clickable", () => {
  assert.equal(officialSourceHref("https://www.fec.gov/data/committee/C00003418/"), "https://www.fec.gov/data/committee/C00003418/");
  assert.equal(officialSourceHref("https://docquery.fec.gov/cgi-bin/fecimg/?202610209916461850"), "https://docquery.fec.gov/cgi-bin/fecimg/?202610209916461850");
  assert.equal(officialSourceHref("http://www.fec.gov/data/"), null);
  assert.equal(officialSourceHref("https://fec.gov/data/"), null);
  assert.equal(officialSourceHref("https://www.fec.gov.evil.example/data/"), null);
  assert.equal(officialSourceHref("https://evil.example/?u=https://www.fec.gov/"), null);
  assert.equal(officialSourceHref("https://user:pass@www.fec.gov/data/"), null);
  assert.equal(officialSourceHref("javascript:alert(1)"), null);
  assert.equal(officialSourceHref("https://www.fec.gov:8443/data/"), null);
  assert.equal(httpsPageHref("https://example.org:444/about"), null);
  const explorer = readFileSync(path.join(root, "components/moneyflow/MoneyFlowExplorer.tsx"), "utf8");
  assert.match(explorer, /officialSourceHref\(card\.source\.source_url\)/);
  assert.doesNotMatch(explorer, /href=\{card\.source\.source_url\}/);
});

test("money-flow errors stay generic", () => {
  const failure = moneyflowErrorResponse();
  assert.equal(failure.status, 500);
  assert.equal(failure.cacheControl, "no-store");
  assert.deepEqual(failure.body, MONEYFLOW_ERROR);
  assert.equal(JSON.stringify(failure.body).includes("path") || JSON.stringify(failure.body).includes("stack"), false);
  assert.match(MONEYFLOW_CACHE, /^public, max-age=\d+$/);
  const index = readFileSync(path.join(root, "app/api/moneyflow/route.ts"), "utf8");
  const shard = readFileSync(path.join(root, "app/api/moneyflow/[id]/route.ts"), "utf8");
  for (const text of [index, shard]) {
    assert.match(text, /MONEYFLOW_CACHE/);
    assert.match(text, /catch/);
    assert.match(text, /MONEYFLOW_ERROR/);
    assert.match(text, /moneyflowPublished/);
    assert.match(shard, /pilotCommitteeIds/);
    assert.doesNotMatch(text, /err\.stack|error\.message|stack:/);
  }
});

test("a stated purpose is a sourced quote or an explicit gap", () => {
  const quote = statedPurposeLine({
    review_status: "approved",
    found: true,
    speaker: "committee",
    source: {
      source_name: "Example Committee",
      source_url: "https://example.org/about",
      retrieved_at: "2026-11-17T02:30:00+00:00",
      excerpt: "We exist to file reports.",
    },
  });
  assert.match(quote.text, /^In its own words: “We exist to file reports.”$/);
  assert.equal(statedPurposeLine({ found: true, source: { source_url: "https://example.org/about", excerpt: "We exist to file reports.", source_name: "Example" } }), null);
  assert.equal(statedPurposeLine({ found: true, source: { source_url: "http://example.org/about", retrieved_at: "2026-11-17T02:30:00+00:00", excerpt: "We exist to file reports.", source_name: "Example" } }), null);
  const gap = statedPurposeLine({ review_status: "approved", found: false });
  assert.equal(gap.text, NO_STATED_PURPOSE);
  const proposed = statedPurposeLine({
    review_status: "proposed",
    found: true,
    speaker: "committee",
    source: {
      source_name: "Example Committee",
      source_url: "https://example.org/about",
      retrieved_at: "2026-11-17T02:30:00+00:00",
      excerpt: "We exist to file reports.",
    },
  });
  assert.equal(proposed, null);
  const sponsor = statedPurposeLine({
    review_status: "approved",
    found: true,
    speaker: "connected_organization",
    source: {
      source_name: "Example Sponsor",
      source_url: "https://sponsor.example/about",
      retrieved_at: "2026-11-17T02:30:00+00:00",
      excerpt: "Our mission is to advocate for quality care.",
    },
  });
  assert.match(sponsor.text, /^In its connected organization's own words: /);
  const purposes = JSON.parse(readFileSync(path.join(root, "data/moneyflow/purposes.json"), "utf8"));
  const manifest = JSON.parse(readFileSync(path.join(root, "data/moneyflow/pilot/manifest.json"), "utf8"));
  assert.equal(manifest.not_in_web_bundle, false);
  const pilotIds = manifest.pilot.map((row) => row.committee_id);
  assert.deepEqual(purposes.committees.map((row) => row.committee_id), pilotIds);
  const approvedIds = new Set(["C00010603", "C00000935", "C00042366", "C00003418", "C00075820", "C00027466", "C00348540", "C00140061", "C00298000"]);
  assert.equal(purposes.committees.filter((row) => row.found).length, 9);
  for (const row of purposes.committees) {
    if (!row.found) {
      assert.equal(row.review_status, "proposed");
      assert.equal(row.source, null);
      assert.equal(statedPurposeLine(row), null);
      continue;
    }
    assert.equal(approvedIds.has(row.committee_id), true, row.committee_id);
    assert.equal(row.review_status, "approved");
    const approvedAt = { C00010603: "2026-11-17T02:34:00+00:00", C00003418: "2026-11-17T02:35:00+00:00" };
    assert.equal(row.approved_at, approvedAt[row.committee_id] || "2026-11-17T02:32:00+00:00");
    if (row.committee_id === "C00003418") {
      assert.match(row.source.excerpt, /general management of the Republican Party/);
      assert.match(row.source.source_name, /Rule No\. 1\(a\)/);
    }
    assert.equal(statedPurposeLine(row).source.source_url, row.source.source_url);
    assert.match(row.source.source_url, /^https:\/\//);
    assert.ok(row.source.retrieved_at);
    assert.ok(row.source.excerpt);
    assert.doesNotMatch(row.source.excerpt, /motive|corrupt intent|bought/i);
  }
});

test("record cards use the shared popover", () => {
  for (const file of ["components/SourceCard.tsx", "components/CommitteeInfo.tsx", "components/moneyflow/MoneyFlowExplorer.tsx"]) {
    const text = readFileSync(path.join(root, file), "utf8");
    assert.match(text, /RecordPopover/);
    assert.doesNotMatch(text, /showModal/);
  }
});
