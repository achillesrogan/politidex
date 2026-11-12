/** Display dates in the maintainer/user zone, not the UTC calendar date of an ISO timestamp. */
export const DISPLAY_TIME_ZONE = "America/Chicago";

export function fmtDate(iso?: string | null): string {
  if (!iso) return "";
  const s = String(iso).trim();
  // A YYYY-MM-DD value is already a calendar date; Date.parse would treat it as UTC midnight.
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) {
    return s.length >= 10 ? s.slice(0, 10) : s;
  }
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

export const fmtRetrieved = fmtDate;
