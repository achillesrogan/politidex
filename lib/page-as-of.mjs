/** Newest retrieval time among the facts a page actually shows. */
import { readFileSync } from "node:fs";
import path from "node:path";

function readJson(parts) {
  return JSON.parse(readFileSync(path.join(process.cwd(), ...parts), "utf8"));
}

export function moneyFlowAsOf() {
  return newestRetrieved(moneyFlowDates(
    readJson(["data", "moneyflow", "pilot", "manifest.json"]),
    readJson(["data", "moneyflow", "purposes.json"]),
  ));
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

export function moneyFlowDates(manifest, purposes) {
  const dates = [manifest && manifest.retrieved_at, purposes && purposes.retrieved_at];
  for (const row of (purposes && purposes.committees) || []) {
    dates.push(row.retrieved_at, row.approved_at, row.source && row.source.retrieved_at);
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
