/** Public citation for a proposed committee bill count. The API URL is not a page link. */

export function publicBillCountUrl(row) {
  const url = row && row.congress_gov_url;
  if (typeof url !== "string" || !url.startsWith("https://www.congress.gov/")) return null;
  if (url.includes("api.congress.gov")) return null;
  return url;
}
