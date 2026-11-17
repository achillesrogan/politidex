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
  const rows = Array.isArray(list) ? list : [];
  const dem = rows.filter((c) => c.party === "DEM" && c.selection_rule === "party-qualified-top3");
  const rep = rows.filter((c) => c.party === "REP" && c.selection_rule === "party-qualified-top3");
  const rest = rows.filter((c) => c.selection_rule !== "party-qualified-top3");
  const paired = [];
  const n = Math.max(dem.length, rep.length);
  for (let i = 0; i < n; i += 1) {
    if (dem[i]) paired.push(dem[i]);
    if (rep[i]) paired.push(rep[i]);
  }
  return paired.concat(rest).map((c) => ({ ...c, controlClass: "moneyflow-start" }));
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
    depth,
    expandable: false,
    expanded: false,
    children: null,
  };
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
  return {
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
    depth,
    expandable: false,
    expanded: open,
    children,
    fungibilityNote: shard.fungibility_note || FUNGIBILITY_NOTE,
  };
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
  tree().nodeSize([88, 320])(root);
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
  const bits = [
    createElement("span", { className: "moneyflow-list-name", key: "n" }, row.name),
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
      ? button("moneyflow-text-btn", "Record", () => handlers.onRecord(row.nodeSource, row.name, row.bucketNote), { key: "rn" })
      : null,
    row.edgeSource
      ? button("moneyflow-text-btn", "Amount record", () => handlers.onRecord(row.edgeSource, row.edgeKind || "Reported amount", row.bucketNote), { key: "re" })
      : null,
  ];
  return createElement(
    "li",
    { key: row.key, className: "moneyflow-list-item", role: "treeitem", "aria-expanded": row.expandable ? (row.expanded ? "true" : "false") : undefined },
    createElement("div", { className: "moneyflow-list-row" }, bits, controls),
    createElement("span", { className: "moneyflow-bar", "aria-hidden": "true" }, createElement("span", { style: { width: bar + "%" } })),
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
      createElement("span", { className: "moneyflow-list-amt" }, formatMoney(view.amount)),
      view.nodeSource ? button("moneyflow-text-btn", "Record", () => handlers.onRecord(view.nodeSource, view.name, null)) : null,
    ),
    createElement(
      "ul",
      { role: "tree", "aria-label": "Reported money out" },
      (view.children || []).map((row) => rowElement(row, max, handlers)),
    ),
  );
}
