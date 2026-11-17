/** Public source links. FEC candidate pages 404 when `cycle` is a year that candidate is not on the ballot. */

export function publicSourceHref(raw) {
  if (typeof raw !== "string" || !raw) return null;
  let url;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== "https:") return null;
  if (url.username || url.password) return null;
  if (url.hostname === "api.congress.gov") return null;
  if (url.hostname === "www.fec.gov" && /^\/data\/candidate\/[A-Z0-9]+\/?$/i.test(url.pathname)) {
    url.searchParams.delete("cycle");
    const rest = [...url.searchParams.keys()];
    if (!rest.length) url.search = "";
  }
  return url.toString();
}

/** A public page link. A Congress.gov API row uses congress_gov_url, not source_url. */
export function renderedSourceHref(record) {
  if (record && typeof record === "object") {
    const pub = publicSourceHref(record.congress_gov_url);
    if (pub && pub.startsWith("https://www.congress.gov/")) return pub;
    return publicSourceHref(record.source_url);
  }
  return publicSourceHref(record);
}

/** Committee websites: https only, and only a .gov host. */
export function officialGovHref(raw) {
  const href = publicSourceHref(raw);
  if (!href) return null;
  let host = "";
  try {
    host = new URL(href).hostname.toLowerCase().replace(/\.$/, "");
  } catch {
    return null;
  }
  if (host === "gov" || host.endsWith(".gov")) return href;
  return null;
}
