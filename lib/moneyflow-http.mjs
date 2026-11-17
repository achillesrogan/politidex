/** Headers and the fixed error body for the money-flow routes. No paths or stack text. */
export const MONEYFLOW_CACHE = "public, max-age=300";
export const MONEYFLOW_ERROR = { error: "The record could not be loaded." };

export function moneyflowErrorResponse() {
  return { status: 500, body: MONEYFLOW_ERROR, cacheControl: "no-store" };
}

/** True only when the manifest explicitly allows the pages onto the site. */
export function moneyflowPublished(manifest) {
  return Boolean(manifest) && manifest.not_in_web_bundle !== true;
}

export function pilotCommitteeIds(manifest) {
  const ids = new Set();
  for (const row of (manifest && manifest.pilot) || []) {
    if (row && row.committee_id) ids.add(row.committee_id);
  }
  return ids;
}

export function moneyflowSources(shard) {
  const sources = [];
  const node = shard && shard.node;
  if (node && node.source) sources.push(node.source);
  if (node && node.profile && node.profile.source) sources.push(node.profile.source);
  for (const child of (shard && shard.children) || []) {
    if (child.node && child.node.source) sources.push(child.node.source);
    if (child.node && child.node.profile && child.node.profile.source) sources.push(child.node.profile.source);
    if (child.edge && child.edge.source) sources.push(child.edge.source);
  }
  return sources;
}

/** FEC filing hosts, plus the committee sites already allowlisted for stated purposes. */
export const MONEYFLOW_SOURCE_HOSTS = [
  "fec.gov",
  "democrats.org",
  "dccc.org",
  "www.dscc.org",
  "prod-static.gop.com",
  "www.nrcc.org",
  "www.nrsc.org",
  "www.1199seiu.org",
  "www.acep.org",
  "madisonproject.com",
];

export function moneyflowSourceHost(url) {
  let host = "";
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" || parsed.username || parsed.password) return "";
    host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  } catch (err) {
    return "";
  }
  if (host === "fec.gov" || host.endsWith(".fec.gov")) return host;
  if (MONEYFLOW_SOURCE_HOSTS.includes(host)) return host;
  return "";
}

export function moneyflowSourceReady(source) {
  return Boolean(
    source
    && source.status === "verified"
    && moneyflowSourceHost(source.source_url)
    && source.retrieved_at
    && source.excerpt,
  );
}
