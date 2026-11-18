/** Newest retrieval time among the facts a page actually shows. */
import { readFileSync } from "node:fs";
import path from "node:path";

function readJson(parts) {
  return JSON.parse(readFileSync(path.join(process.cwd(), ...parts), "utf8"));
}

export function moneyFlowAsOf(now = Date.now()) {
  const manifest = readJson(["data", "moneyflow", "pilot", "manifest.json"]);
  const purposes = readJson(["data", "moneyflow", "purposes.json"]);
  const floorMs = retrievalFloorMs(manifest.cycle);
  return newestMoneyFlow(moneyFlowDates(manifest, purposes, now), now, floorMs);
}

export function committeeAsOf() {
  return newestRetrieved(committeeDates(readJson(["data", "committees", "sites.json"])));
}

export function newestRetrieved(values) {
  let best = "";
  for (const value of values || []) {
    if (typeof value === "string" && value > best) best = value;
  }
  return best || null;
}

/** Retrieval times before this instant are not from this project. */
export const RETRIEVAL_FLOOR = "2020-01-01T00:00:00Z";
/** FEC cycles whose files this build will accept. */
export const MONEY_FLOW_CYCLES = [2026];
/** Clock skew allowed past the build clock. */
export const MONEY_FLOW_SKEW_MS = 5 * 60 * 1000;
const RETRIEVAL_FLOOR_MS = Date.parse(RETRIEVAL_FLOOR);
const UTC_ISO = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|\+00:00)$/;

export function retrievalFloorMs(cycle) {
  if (cycle == null || cycle === "") return RETRIEVAL_FLOOR_MS;
  const year = Number(cycle);
  if (!MONEY_FLOW_CYCLES.includes(year)) throw new Error("money-flow cycle is not allowed: " + cycle);
  return Math.max(RETRIEVAL_FLOOR_MS, Date.parse((year - 1) + "-01-01T00:00:00Z"));
}

/** Valid UTC ISO-8601 instant, or throw. Null means the field was absent. */
export function moneyFlowTimestamp(value, now = Date.now(), floorMs = RETRIEVAL_FLOOR_MS) {
  if (value == null) return null;
  if (typeof value !== "string") {
    throw new Error("money-flow date is not a UTC ISO-8601 timestamp");
  }
  const match = UTC_ISO.exec(value);
  if (!match) throw new Error("money-flow date is not a UTC ISO-8601 timestamp: " + value);
  const zulu = match[8] === "Z" ? value : value.slice(0, -6) + "Z";
  const ms = Date.parse(zulu);
  if (!Number.isFinite(ms)) throw new Error("money-flow date is not a valid UTC timestamp: " + value);
  const date = new Date(ms);
  const pad = (part) => String(part).padStart(2, "0");
  const normalized = date.getUTCFullYear() + "-" + pad(date.getUTCMonth() + 1) + "-" + pad(date.getUTCDate())
    + "T" + pad(date.getUTCHours()) + ":" + pad(date.getUTCMinutes()) + ":" + pad(date.getUTCSeconds());
  const given = match[1] + "-" + match[2] + "-" + match[3] + "T" + match[4] + ":" + match[5] + ":" + match[6];
  if (normalized !== given) throw new Error("money-flow date is not a valid UTC timestamp: " + value);
  if (ms < floorMs) throw new Error("money-flow date is before the retrieval floor: " + value);
  if (ms > now + MONEY_FLOW_SKEW_MS) throw new Error("money-flow date is after build time: " + value);
  return ms;
}

/** Newest money-flow retrieval time, compared as UTC instants. */
export function newestMoneyFlow(values, now = Date.now(), floorMs = RETRIEVAL_FLOOR_MS) {
  let best = null;
  let bestMs = -Infinity;
  for (const value of values || []) {
    if (value == null || value === "") continue;
    const ms = moneyFlowTimestamp(value, now, floorMs);
    if (ms > bestMs) {
      bestMs = ms;
      best = value;
    }
  }
  return best;
}

export function moneyFlowDates(manifest, purposes, now = Date.now()) {
  const floorMs = retrievalFloorMs(manifest && manifest.cycle);
  const dates = [manifest && manifest.retrieved_at, purposes && purposes.retrieved_at];
  for (const row of (purposes && purposes.committees) || []) {
    dates.push(row.retrieved_at, row.source && row.source.retrieved_at);
  }
  for (const value of dates) {
    if (value == null || value === "") continue;
    moneyFlowTimestamp(value, now, floorMs);
  }
  return dates;
}

/** Site rows for committees this page shows. A code with no site adds nothing. */
export function pageCommitteeDates(codes, sites) {
  const dates = [];
  const lookup = typeof sites === "function" ? sites : (code) => sites && sites[code];
  for (const code of codes || []) {
    const row = lookup(code);
    if (!row) continue;
    dates.push(row.retrieved_at, row.website_retrieved_at);
  }
  return dates;
}

export function profileAsOf(claimDates, committeeCodes, sites) {
  return newestRetrieved([...(claimDates || []), ...pageCommitteeDates(committeeCodes, sites)]);
}

/** Retrieval times for lobbying-disclosure claims the connections panel shows. */
export function ldaClaimDates(ties, retrievedAt) {
  const dates = [];
  const groups = [ties && ties.lobbying, ties && ties.revolving];
  for (const group of groups) {
    for (const row of (group && group.rows) || []) {
      const when = typeof retrievedAt === "function" ? retrievedAt(row && row.claim) : null;
      if (typeof when === "string" && when) dates.push(when);
    }
  }
  return dates;
}

export function committeeDates(doc) {
  const dates = [doc && doc.retrieved_at];
  for (const source of (doc && doc.sources) || []) dates.push(source.retrieved_at);
  for (const row of Object.values((doc && doc.committees) || {})) {
    dates.push(row.retrieved_at, row.website_retrieved_at);
  }
  return dates;
}
