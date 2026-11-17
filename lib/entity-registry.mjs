/** Links a published name to the official record that identified it. No score and no conclusion. */

export const CONFIDENCE_BADGES = ["exact ID match", "amended filing", "proposed / in review"];

const MIN_OFFICIAL_ID_LENGTH = 5;

export function confidenceBadge(record) {
  if (!record || typeof record !== "object") return null;
  if (record.review_status === "proposed") return "proposed / in review";
  if (record.amended === true) return "amended filing";
  const url = String(record.source_url || "");
  const ids = officialIds(record).filter((id) => urlHasOfficialId(url, id));
  if (url.startsWith("https://") && ids.length) return "exact ID match";
  return null;
}

function isFecHost(host) {
  return host === "www.fec.gov" || host === "fec.gov";
}

function isCongressHost(host) {
  return host === "www.congress.gov" || host === "congress.gov";
}

function isOfficialHost(host) {
  return isFecHost(host) || isCongressHost(host)
    || host === "clerk.house.gov"
    || host === "www.house.gov" || host.endsWith(".house.gov")
    || host === "www.senate.gov" || host.endsWith(".senate.gov");
}

function hostMatchesId(id, host) {
  if (/^C\d{8}$/i.test(id)) return isFecHost(host);
  if (/^[A-Z]\d{6}$/.test(id)) return isCongressHost(host);
  if (String(id).includes("/")) return isCongressHost(host);
  return isOfficialHost(host);
}

function urlHasOfficialId(url, id) {
  const text = String(id);
  if (text.length < MIN_OFFICIAL_ID_LENGTH) return false;
  let parsed;
  try {
    parsed = new URL(url);
  } catch (err) {
    return false;
  }
  const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  if (!hostMatchesId(text, host)) return false;
  if (pathHasWholeId(parsed.pathname, text)) return true;
  return queryHasExactId(parsed, text);
}

function pathHasWholeId(pathname, id) {
  const segments = String(pathname || "").split("/").filter(Boolean).map((part) => {
    try {
      return decodeURIComponent(part);
    } catch (err) {
      return part;
    }
  });
  const want = String(id).split("/").filter(Boolean);
  if (!want.length) return false;
  for (let i = 0; i + want.length <= segments.length; i += 1) {
    if (want.every((part, j) => segments[i + j] === part)) return true;
  }
  return false;
}

function queryHasExactId(parsed, id) {
  for (const [key, value] of parsed.searchParams.entries()) {
    if (!/(?:^|_)id$|^bioguide$|^comcode$/i.test(key)) continue;
    if (value === id) return true;
  }
  return false;
}


function officialIds(record) {
  const check = record.check && typeof record.check === "object" ? record.check : {};
  const match = check.match && typeof check.match === "object" ? check.match : {};
  return [record.official_id, check.bioguide, check.comcode, check.committee_id, match.committee_id]
    .filter((id) => id !== undefined && id !== null && String(id).trim() !== "")
    .map((id) => String(id).trim());
}

export function badgeForClaim(claim) {
  if (!claim?.source_url) return null;
  return confidenceBadge({
    review_status: claim.check?.review_status,
    amended: claim.check?.amended === true,
    source_url: claim.source_url,
    check: claim.check,
  });
}

export function entityRecord(input) {
  const name = String(input?.name || "").trim();
  const source_url = String(input?.source_url || "").trim();
  const source_name = String(input?.source_name || "").trim();
  if (!name || !source_name || !source_url.startsWith("https://")) return null;
  const href = typeof input.href === "string" && input.href.startsWith("/") && !input.href.startsWith("//") ? input.href : null;
  return {
    kind: input.kind || "record",
    name,
    official_id: input.official_id ? String(input.official_id) : null,
    source_name,
    source_url,
    retrieved_at: input.retrieved_at || null,
    href,
    badge: confidenceBadge(input),
  };
}

export function registryIndex(entities) {
  const index = new Map();
  for (const entity of entities || []) {
    if (!entity?.official_id) continue;
    index.set(`${entity.kind}:${entity.official_id}`, entity);
  }
  return index;
}

export function findEntity(index, kind, officialId) {
  if (!index || !officialId) return null;
  return index.get(`${kind}:${officialId}`) || null;
}

export function latestRetrieved(values) {
  let best = "";
  for (const value of values || []) {
    const text = String(value || "");
    if (text && text > best) best = text;
  }
  return best || null;
}
