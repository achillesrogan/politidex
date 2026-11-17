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
    dates.push(row.retrieved_at, row.source && row.source.retrieved_at);
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
