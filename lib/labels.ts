import { fmtDate } from "@/lib/dates";
/** Display labels for official FEC codes. Official names stay on the claim; these are for the UI only. */
export const DESIGNATION_PLAIN: Record<string, string> = {
  A: "authorized by a candidate",
  B: "lobbyist/registrant PAC",
  D: "leadership PAC",
  J: "joint fundraising committee",
  P: "the candidate’s principal campaign committee",
  U: "not a candidate’s own committee",
};

export const TYPE_PLAIN: Record<string, string> = {
  C: "communication-cost report",
  D: "delegate committee",
  E: "electioneering communication",
  H: "House campaign committee",
  I: "independent expenditor (a person or group)",
  N: "nonqualified PAC",
  O: "independent expenditure-only committee (Super PAC)",
  P: "presidential campaign committee",
  Q: "qualified PAC",
  S: "Senate campaign committee",
  U: "single-candidate independent expenditure committee",
  V: "nonqualified hybrid PAC",
  W: "qualified hybrid PAC",
  X: "nonqualified party committee",
  Y: "qualified party committee",
  Z: "national party nonfederal account",
};

export function orgCategoryLabel(official?: string | null) {
  if (!official || official === "Interest group category not reported" || official === "Not reported") {
    return "Not categorized by FEC";
  }
  return official;
}

export function designationLabel(code?: string | null, official?: string | null) {
  const resolved = designationCode(code, official);
  const plain = (resolved && DESIGNATION_PLAIN[resolved]) || null;
  if (plain && official && official !== plain) return `${plain} (FEC designation: ${official})`;
  return plain || official || null;
}

export function committeeTypeLabel(code?: string | null, official?: string | null) {
  const resolved = committeeTypeCode(code, official);
  const plain = (resolved && TYPE_PLAIN[resolved]) || null;
  if (plain && official && official !== plain) return `${plain} (FEC committee type: ${official})`;
  return plain || official || null;
}

export function usd(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function fmtRetrieved(iso?: string) {
  return fmtDate(iso);
}

const DESIGNATION_OFFICIAL: Record<string, string> = {
  "Authorized by a candidate": "A",
  "Lobbyist/Registrant PAC": "B",
  "Leadership PAC": "D",
  "Joint fundraiser": "J",
  "Principal campaign committee of a candidate": "P",
  "Unauthorized": "U",
};

const TYPE_OFFICIAL: Record<string, string> = {
  "Communication cost": "C",
  "Delegate committee": "D",
  "Electioneering communication": "E",
  "House": "H",
  "Independent expenditor (person or group)": "I",
  "PAC - nonqualified": "N",
  "Independent expenditure-only (Super PACs)": "O",
  "Presidential": "P",
  "PAC - qualified": "Q",
  "Senate": "S",
  "Single-candidate independent expenditure": "U",
  "Hybrid PAC (with Non-Contribution Account) - Nonqualified": "V",
  "Hybrid PAC (with Non-Contribution Account) - Qualified": "W",
  "Party - nonqualified": "X",
  "Party - qualified": "Y",
  "National party nonfederal account": "Z",
};

export function designationCode(code?: string | null, official?: string | null) {
  return (code && DESIGNATION_PLAIN[code] ? code : null) || (official && DESIGNATION_OFFICIAL[official]) || null;
}

export function committeeTypeCode(code?: string | null, official?: string | null) {
  return (code && TYPE_PLAIN[code] ? code : null) || (official && TYPE_OFFICIAL[official]) || null;
}
