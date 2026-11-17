/** Public source links. FEC candidate pages 404 when `cycle` is a year that candidate is not on the ballot. */

export function publicSourceHref(raw) {
  if (typeof raw !== "string" || !raw) return null;
  let url;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (url.username || url.password) return null;
  if (url.hostname === "www.fec.gov" && /^\/data\/candidate\/[A-Z0-9]+\/?$/i.test(url.pathname)) {
    url.searchParams.delete("cycle");
    const rest = [...url.searchParams.keys()];
    if (!rest.length) url.search = "";
  }
  return url.toString();
}
