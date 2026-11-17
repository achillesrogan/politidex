/**
 * Pure helpers for the money-flow tree. No FEC calls and no shard imports.
 * The browser loads shards with fetch() from this app.
 */
import { hierarchy, tree } from "d3-hierarchy";
import { createElement } from "react";

export const FUNGIBILITY_NOTE =
  "Reported money out of this account. Money in an account is fungible, so this is not a record that a particular dollar went to a particular payee.";

export const INDIVIDUALS_NOTE =
  "This bucket sums reported disbursements tied to individual people. Names are not shown.";

export const OTHER_NOTE =
  "This bucket sums reported disbursements that are not listed separately: payees below the top 25, rows whose entity type was not identified, and the difference between the official total and the itemized rows in the ingested files.";

export const DEFAULT_DEPTH = 2;
export const MAX_DEPTH = 6;
export const EDGE_KINDS = ["reported contribution", "reported transfer", "reported disbursement", "spent"];
const COMMITTEE_ID = /^C[0-9]{8}$/;

// One palette for every committee. Colors mark the reported kind, not a party.
export const FLOW_PALETTE = {
  transfer: { id: "transfer", label: "Reported transfer", color: "#0e5c56" },
  contribution: { id: "contribution", label: "Reported contribution", color: "#5b3a86" },
  spent: { id: "spent", label: "Spent", color: "#8a4b08" },
  individuals: { id: "individuals", label: "Reported assistance to individuals", color: "#3d5a12" },
  other: { id: "other", label: "Other reported disbursements", color: "#3d4a59" },
  disbursement: { id: "disbursement", label: "Reported disbursement", color: "#6a3d2a" },
  account: { id: "account", label: "Committee account", color: "#1a1a1a" },
};
export const FLOW_LEGEND = ["transfer", "contribution", "spent", "individuals", "other", "disbursement", "account"].map((id) => FLOW_PALETTE[id]);

export const FEC_TYPE_URL = "https://www.fec.gov/campaign-finance-data/committee-type-code-descriptions/";
export const FEC_MASTER_URL = "https://www.fec.gov/campaign-finance-data/committee-master-file-description/";
export const FEC_NONCONNECTED_URL = "https://www.fec.gov/help-candidates-and-committees/registering-pac/understanding-nonconnected-pacs/";

// Sentences below are the FEC's own committee-type explanations.
const TYPE_EXPLANATION = {
  C: "Organizations like corporations or unions may prepare communications for their employees or members that advocate the election of specific candidates and they must disclose them under certain circumstances. These are usually paid with direct corporate or union funds rather than from PACs.",
  D: "Delegate committees are organized for the purpose of influencing the selection of delegates to Presidential nominating conventions. The term includes a group of delegates, a group of individuals seeking to become delegates, and a group of individuals supporting delegates.",
  E: "Groups (other than PACs) making electioneering communications.",
  H: "Campaign committees for candidates for the U.S. House of Representatives.",
  I: "Individuals or groups (other than PACs) making independent expenditures over $250 in a year must disclose those expenditures.",
  N: "PACs that have not yet been in existence for six months and received contributions from 50 people and made contributions to five federal candidates. These committees have lower limits for their contributions to candidates.",
  O: "Political committee that has filed a statement consistent with AO 2010-09 or AO 2010-11.",
  P: "Campaign committee for candidate for U.S. President.",
  Q: "PACs that have been in existence for six months and received contributions from 50 people and made contributions to five federal candidates.",
  S: "Campaign committee for candidate for Senate.",
  U: "Single-candidate independent expenditure.",
  V: "Political committees with non-contribution accounts.",
  W: "Political committees with non-contribution accounts.",
  X: "Party committees that have not yet been in existence for six months and received contributions from 50 people, unless they are affiliated with another party committee that has met these requirements.",
  Y: "Party committees that have existed for at least six months and received contributions from 50 people or are affiliated with another party committee that meets these requirements.",
  Z: "National party nonfederal accounts. Not permitted after enactment of Bipartisan Campaign Reform Act of 2002.",
};
const DESIGNATION_LABEL = {
  A: "Authorized by a candidate",
  B: "Lobbyist/Registrant PAC",
  D: "Leadership PAC",
  J: "Joint fundraiser",
  P: "Principal campaign committee of a candidate",
  U: "Unauthorized",
};
const ORG_LABEL = {
  C: "Corporation",
  L: "Labor organization",
  M: "Membership organization",
  T: "Trade association",
  V: "Cooperative",
  W: "Corporation without capital stock",
};
const FILING_FREQUENCY = {
  A: "Administratively terminated",
  D: "Debt",
  M: "Monthly filer",
  Q: "Quarterly filer",
  T: "Terminated",
  W: "Waived",
};
const SSF_PAREN = {
  C: "corporate PAC",
  L: "labor PAC",
  M: "membership organization",
  T: "trade association",
  V: "cooperative",
  W: "corporation without capital stock",
};

function channel(hex, index) {
  const v = parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16) / 255;
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

export function contrastRatio(foreground, background) {
  const lum = (hex) => 0.2126 * channel(hex, 0) + 0.7152 * channel(hex, 1) + 0.0722 * channel(hex, 2);
  const hi = Math.max(lum(foreground), lum(background));
  const lo = Math.min(lum(foreground), lum(background));
  return (hi + 0.05) / (lo + 0.05);
}

export function flowOf(node) {
  if (!node) return "disbursement";
  const name = String(node.name || "").toLowerCase();
  if (node.kind === "residual" && name.includes("individual")) return "individuals";
  if (node.kind === "residual") return "other";
  if (node.kind === "business" || node.terminalLabel === "Spent" || node.edgeKind === "spent") return "spent";
  if (node.edgeKind === "reported transfer") return "transfer";
  if (node.edgeKind === "reported contribution") return "contribution";
  if (node.edgeKind === "reported disbursement") return "disbursement";
  return "account";
}

export function flowColor(node) {
  return (FLOW_PALETTE[flowOf(node)] || FLOW_PALETTE.disbursement).color;
}

export function plainCommitteeKind(profile) {
  if (!profile?.committee_type) return null;
  const type = profile.committee_type;
  const org = profile.org_type || "";
  if (type === "X" || type === "Y") return "Party committee";
  if (type === "Z") return "National party nonfederal account";
  if (type === "O") return "Super PAC (independent expenditure-only)";
  if (type === "H") return "House campaign committee";
  if (type === "S") return "Senate campaign committee";
  if (type === "P") return "Presidential campaign committee";
  if (type === "V" || type === "W") return "Hybrid PAC";
  if (type === "U") return "Single-candidate independent expenditure committee";
  if (type === "I") return "Independent expenditor";
  if (type === "C") return "Communication cost";
  if (type === "E") return "Electioneering communication";
  if (type === "D") return "Delegate committee";
  if (type === "Q" || type === "N") {
    if (org || profile.connected_organization) {
      return SSF_PAREN[org] ? "Separate segregated fund (" + SSF_PAREN[org] + ")" : "Separate segregated fund";
    }
    return "Nonconnected PAC";
  }
  return null;
}

export function entityFacts(profile) {
  if (!profile?.committee_id || !profile?.source?.source_url || !profile?.source?.excerpt || !profile?.source?.source_name) return [];
  const facts = [];
  const type = profile.committee_type || "";
  const kind = plainCommitteeKind(profile);
  const explanation = TYPE_EXPLANATION[type];
  if (kind && explanation) {
    const ssf = (type === "Q" || type === "N") && (profile.org_type || profile.connected_organization);
    const nonconnected = (type === "Q" || type === "N") && !profile.org_type && !profile.connected_organization;
    let text = kind + ". FEC committee type " + type + ". " + explanation;
    let href = FEC_TYPE_URL;
    let linkLabel = "FEC committee type code descriptions";
    if (nonconnected) {
      text += " A nonconnected committee is a political committee that is not a party committee, an authorized committee of a candidate or a separate segregated fund established by a corporation or labor organization.";
      href = FEC_NONCONNECTED_URL;
      linkLabel = "FEC explanation of nonconnected PACs";
    }
    facts.push({ label: "Committee type", text, href, linkLabel });
    if (ssf) {
      facts.push({
        label: "Separate segregated fund",
        text: "An SSF, by definition, always has a sponsoring corporation or labor organization.",
        href: FEC_NONCONNECTED_URL,
        linkLabel: "FEC explanation of nonconnected PACs and separate segregated funds",
      });
    }
  }
  if (profile.designation && DESIGNATION_LABEL[profile.designation]) {
    facts.push({
      label: "Designation",
      text: "FEC designation " + profile.designation + ": " + DESIGNATION_LABEL[profile.designation] + ".",
      href: FEC_MASTER_URL,
      linkLabel: "FEC committee master file description",
    });
  }
  if (profile.connected_organization) {
    facts.push({
      label: "Connected organization",
      text: profile.connected_organization,
      href: profile.source.source_url,
      linkLabel: "Committee page on FEC.gov",
    });
  }
  if (profile.org_type && ORG_LABEL[profile.org_type]) {
    facts.push({
      label: "Interest group category",
      text: ORG_LABEL[profile.org_type] + ".",
      href: FEC_MASTER_URL,
      linkLabel: "FEC committee master file description",
    });
  }
  facts.push({
    label: "Party affiliation",
    text: profile.party
      ? "Party code " + profile.party + ", as filed on the committee master."
      : "Party affiliation is blank on the committee master.",
    href: FEC_MASTER_URL,
    linkLabel: "FEC committee master file description",
  });
  if (profile.filing_frequency && FILING_FREQUENCY[profile.filing_frequency]) {
    facts.push({
      label: "Filing frequency",
      text: FILING_FREQUENCY[profile.filing_frequency] + ".",
      href: FEC_MASTER_URL,
      linkLabel: "FEC committee master file description",
    });
  }
  if (profile.state) {
    facts.push({
      label: "State",
      text: "Committee state on the committee master: " + profile.state + ".",
      href: profile.source.source_url,
      linkLabel: "Committee page on FEC.gov",
    });
  }
  return facts;
}

export function hasSource(source) {
  return Boolean(source && source.source_url && source.retrieved_at && source.excerpt && source.source_name);
}

export function formatMoney(amount) {
  const n = Number(amount);
  if (!Number.isFinite(n)) return "";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export function dollarsToCents(dollars) {
  const n = Number(String(dollars).replace(/[$,]/g, ""));
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.round(n * 100);
}

export function strokeWidth(cents, maxCents) {
  const t = maxCents > 0 ? Math.max(0, Number(cents) || 0) / maxCents : 0;
  return Math.round((1.25 + Math.min(1, t) * 10) * 100) / 100;
}

export function barPercent(cents, maxCents) {
  if (!(maxCents > 0)) return 0;
  const t = Math.max(0, Number(cents) || 0) / maxCents;
  return Math.max(t > 0 ? 8 : 0, Math.round(Math.min(1, t) * 100));
}

export function bucketNote(node) {
  if (!node || node.kind !== "residual") return null;
  const name = String(node.name || "").toLowerCase();
  if (name.includes("individual")) return INDIVIDUALS_NOTE;
  if (name.includes("other reported")) return OTHER_NOTE;
  return null;
}

export function shardUrl(id) {
  if (!COMMITTEE_ID.test(id || "")) return null;
  return "/api/moneyflow/" + id;
}

export function presentCommittees(list) {
  const rows = Array.isArray(list) ? list.slice() : [];
  rows.sort((a, b) => {
    const an = String(a?.name || "").toLocaleUpperCase();
    const bn = String(b?.name || "").toLocaleUpperCase();
    if (an < bn) return -1;
    if (an > bn) return 1;
    const ai = String(a?.committee_id || "");
    const bi = String(b?.committee_id || "");
    if (ai < bi) return -1;
    if (ai > bi) return 1;
    return 0;
  });
  return rows.map((c) => ({ ...c, controlClass: "moneyflow-start" }));
}

const FEC_HOSTS = new Set(["www.fec.gov", "docquery.fec.gov"]);

export function officialSourceHref(url) {
  if (typeof url !== "string" || !url) return null;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  if (parsed.username || parsed.password) return null;
  if (!FEC_HOSTS.has(parsed.hostname.toLowerCase())) return null;
  return url;
}

export function applyFilters(children, filters = {}) {
  const min = Number(filters.minCents) || 0;
  const kind = filters.kind && filters.kind !== "any" ? filters.kind : "";
  const purpose = filters.purpose && filters.purpose !== "any" ? filters.purpose : "";
  const cycle = filters.cycle ? Number(filters.cycle) : 0;
  return (children || []).filter((ch) => {
    const cents = Number(ch?.edge?.amount_cents);
    if (!Number.isFinite(cents)) return false;
    if (min && cents < min) return false;
    if (kind && ch?.node?.kind !== kind) return false;
    if (purpose && (ch?.edge?.purpose_code || "") !== purpose) return false;
    const childCycle = ch?.node?.period?.cycle;
    if (cycle && childCycle && Number(childCycle) !== cycle) return false;
    return true;
  });
}

export function purposeCodes(children) {
  return [...new Set((children || []).map((ch) => ch?.edge?.purpose_code).filter(Boolean))].sort();
}

export const NO_STATED_PURPOSE = "No stated purpose found in primary sources.";

function compact(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

export function httpsPageHref(url) {
  if (typeof url !== "string" || !url) return null;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  if (parsed.username || parsed.password) return null;
  if (!parsed.hostname.includes(".")) return null;
  return url;
}

export function statedPurposeLine(entry) {
  if (!entry || typeof entry !== "object") return null;
  if (!entry.found) return { kind: "none", text: NO_STATED_PURPOSE, source: null };
  const source = entry.source;
  const excerpt = compact(source?.excerpt);
  if (!source || !httpsPageHref(source.source_url) || !source.retrieved_at || !source.source_name || !excerpt) return null;
  const lead = entry.speaker === "connected_organization"
    ? "In its connected organization's own words: "
    : "In its own words: ";
  return {
    kind: "quote",
    text: lead + "\u201c" + excerpt + "\u201d",
    source,
  };
}

function lookupPurpose(id, opts) {
  if (!id || !opts || !opts.purposes) return null;
  return opts.purposes[id] || null;
}

function terminalOf(node) {
  return node?.terminal === true || node?.kind === "business" || node?.kind === "residual";
}

export function canExpand(node, depth, shardIds) {
  if (!node || terminalOf(node)) return false;
  if (depth >= MAX_DEPTH) return false;
  return Boolean(node.officialId && shardIds && shardIds.has(node.officialId));
}

function toChild(ch, opts, depth) {
  if (!hasSource(ch?.node?.source) || !hasSource(ch?.edge?.source)) return null;
  const cents = Number(ch.edge.amount_cents);
  if (!Number.isFinite(cents)) return null;
  const officialId = ch.node.official_id || null;
  const view = {
    key: (ch.node.id || ch.node.name) + ":" + (ch.edge.id || ch.edge.kind || "edge"),
    name: ch.node.name || officialId || "Reported payee",
    kind: ch.node.kind,
    officialId,
    terminal: terminalOf(ch.node),
    terminalLabel: ch.node.terminal_label || (ch.node.kind === "business" ? "Spent" : null),
    amount: ch.edge.amount,
    amountCents: cents,
    edgeKind: ch.edge.kind,
    purpose: ch.edge.purpose || null,
    purposeCode: ch.edge.purpose_code || null,
    nodeSource: ch.node.source,
    edgeSource: ch.edge.source,
    bucketNote: bucketNote(ch.node),
    profile: ch.node.profile || null,
    statedPurpose: lookupPurpose(officialId, opts),
    depth,
    expandable: false,
    expanded: false,
    children: null,
  };
  view.flow = flowOf(view);
  view.expandable = canExpand(view, depth, opts.shardIds);
  const open = view.expandable && opts.expanded && opts.expanded.has(view.key);
  if (open) {
    const sub = opts.loaded && opts.loaded.get(view.officialId);
    view.expanded = true;
    if (sub) {
      const opened = new Set(opts.expanded);
      opened.add(sub.node.id);
      const nested = buildVisible(sub, { ...opts, expanded: opened }, depth);
      view.children = nested ? nested.children : [];
    } else {
      view.children = [];
      view.loading = true;
    }
  }
  return view;
}

export function buildVisible(shard, opts = {}, depth = 1) {
  if (!shard?.node || !hasSource(shard.node.source)) return null;
  const filters = opts.filters || {};
  if (filters.cycle && shard.cycle && Number(shard.cycle) !== Number(filters.cycle)) {
    return null;
  }
  const open = depth === 1 || (opts.expanded && opts.expanded.has(shard.node.id));
  let children = [];
  if (open && depth < MAX_DEPTH) {
    children = applyFilters(shard.children || [], filters)
      .map((ch) => toChild(ch, opts, depth + 1))
      .filter(Boolean);
  }
  const view = {
    key: shard.node.id,
    name: shard.node.name,
    kind: shard.node.kind,
    officialId: shard.node.official_id || null,
    terminal: false,
    terminalLabel: null,
    amount: shard.node.official_total_out,
    amountCents: Math.round(Number(shard.node.official_total_out) * 100) || 0,
    edgeKind: null,
    purpose: null,
    purposeCode: null,
    nodeSource: shard.node.source,
    edgeSource: null,
    bucketNote: null,
    profile: shard.node.profile || null,
    statedPurpose: lookupPurpose(shard.node.official_id, opts),
    depth,
    expandable: false,
    expanded: open,
    children,
    fungibilityNote: shard.fungibility_note || FUNGIBILITY_NOTE,
  };
  view.flow = flowOf(view);
  return view;
}

function layoutNode(node) {
  return {
    ...node,
    children: node.expanded && Array.isArray(node.children) && node.children.length ? node.children.map(layoutNode) : undefined,
  };
}

export function layoutTree(view) {
  if (!view) return { width: 320, height: 80, nodes: [], links: [] };
  const root = hierarchy(layoutNode(view));
  tree().nodeSize([144, 320])(root);
  const nodes = root.descendants();
  const minX = Math.min(...nodes.map((d) => d.x));
  const maxX = Math.max(...nodes.map((d) => d.x));
  const maxY = Math.max(...nodes.map((d) => d.y));
  const shiftY = 12 - minX;
  const placed = nodes.map((d) => ({
    key: d.data.key,
    x: d.y + 12,
    y: d.x + shiftY,
    data: d.data,
  }));
  const byKey = new Map(placed.map((n) => [n.key, n]));
  const links = root.links().map((l) => {
    const s = byKey.get(l.source.data.key);
    const t = byKey.get(l.target.data.key);
    return {
      key: l.target.data.key,
      x1: s.x + 248,
      y1: s.y + 32,
      x2: t.x,
      y2: t.y + 32,
      cents: l.target.data.amountCents,
      flow: l.target.data.flow,
    };
  });
  const maxCents = Math.max(0, ...links.map((l) => l.cents));
  return { width: maxY + 280, height: maxX - minX + 100, nodes: placed, links, maxCents };
}

export function linkPath(link) {
  const mid = (link.x1 + link.x2) / 2;
  return `M${link.x1},${link.y1} C${mid},${link.y1} ${mid},${link.y2} ${link.x2},${link.y2}`;
}

function button(className, label, onClick, extra) {
  return createElement("button", { type: "button", className, onClick, ...extra }, label);
}

function rowElement(row, maxCents, handlers) {
  const bar = barPercent(row.amountCents, maxCents);
  const color = FLOW_PALETTE[row.flow]?.color || FLOW_PALETTE.disbursement.color;
  const plain = plainCommitteeKind(row.profile);
  const bits = [
    createElement("span", { className: "moneyflow-list-name", key: "n" }, row.name),
    plain ? createElement("span", { className: "moneyflow-list-kind", key: "p" }, plain) : null,
    row.terminalLabel ? createElement("span", { className: "tag", key: "t" }, row.terminalLabel) : null,
    createElement("span", { className: "moneyflow-list-amt", key: "a" }, formatMoney(row.amount)),
    row.edgeKind && row.edgeKind.toLowerCase() !== String(row.terminalLabel || "").toLowerCase()
      ? createElement("span", { className: "moneyflow-list-kind", key: "k" }, row.edgeKind)
      : null,
  ];
  const controls = [
    row.expandable
      ? button("moneyflow-text-btn", row.expanded ? "Hide reported outflows" : "Show reported outflows", () => handlers.onToggle(row), {
          "aria-expanded": row.expanded ? "true" : "false",
          key: "x",
        })
      : null,
    row.nodeSource
      ? button("moneyflow-text-btn", "Record", (event) => handlers.onRecord(row.nodeSource, row.name, row.bucketNote, row.profile, event, row.statedPurpose), { key: "rn" })
      : null,
    row.edgeSource
      ? button("moneyflow-text-btn", "Amount record", (event) => handlers.onRecord(row.edgeSource, row.edgeKind || "Reported amount", row.bucketNote, row.profile, event, row.statedPurpose), { key: "re" })
      : null,
  ];
  return createElement(
    "li",
    { key: row.key, className: "moneyflow-list-item", role: "treeitem", "data-flow": row.flow, "aria-expanded": row.expandable ? (row.expanded ? "true" : "false") : undefined },
    createElement("div", { className: "moneyflow-list-row" }, bits, controls),
    createElement("span", { className: "moneyflow-bar", "aria-hidden": "true" }, createElement("span", { style: { width: bar + "%", background: color } })),
    statedPurposeLine(row.statedPurpose) ? createElement("p", { className: "moneyflow-purpose" }, statedPurposeLine(row.statedPurpose).text) : null,
    row.bucketNote ? createElement("p", { className: "moneyflow-bucket-note" }, row.bucketNote) : null,
    row.expanded && row.children && row.children.length
      ? createElement("ul", { role: "group" }, row.children.map((child) => rowElement(child, Math.max(...row.children.map((c) => c.amountCents), 1), handlers)))
      : null,
  );
}

export function createNestedList(view, handlers = {}) {
  if (!view) return null;
  const max = Math.max(...(view.children || []).map((c) => c.amountCents), 1);
  return createElement(
    "div",
    { className: "moneyflow-list" },
    createElement(
      "div",
      { className: "moneyflow-list-row moneyflow-list-root" },
      createElement("span", { className: "moneyflow-list-name" }, view.name),
      plainCommitteeKind(view.profile) ? createElement("span", { className: "moneyflow-list-kind" }, plainCommitteeKind(view.profile)) : null,
      createElement("span", { className: "moneyflow-list-amt" }, formatMoney(view.amount)),
      view.nodeSource ? button("moneyflow-text-btn", "Record", (event) => handlers.onRecord(view.nodeSource, view.name, null, view.profile, event, view.statedPurpose)) : null,
    ),
    createElement(
      "ul",
      { role: "tree", "aria-label": "Reported money out" },
      (view.children || []).map((row) => rowElement(row, max, handlers)),
    ),
  );
}
