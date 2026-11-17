/** Load one member's career facts. The big files are read only from this module. */
import fs from "node:fs";
import path from "node:path";
import { memberUrl, publicBillUrl } from "./career-public.mjs";

const dir = path.join(process.cwd(), "data", "career");

function read(name) {
  return JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
}

let coverageFile;
let congressFile;
let fecMembersFile;
let ldaFile;

export function readCoverage() {
  if (!coverageFile) coverageFile = read("coverage.json");
  return coverageFile;
}

function congress() {
  if (!congressFile) congressFile = read("congress.json");
  return congressFile;
}

function fecMembers() {
  if (!fecMembersFile) fecMembersFile = read("fec-members.json");
  return fecMembersFile;
}

function lda() {
  if (!ldaFile) ldaFile = read("lda.json");
  return ldaFile;
}

export function memberFirstYear(bioguide) {
  if (!bioguide) return null;
  try {
    const year = read("first-years.json")[bioguide];
    return Number.isInteger(year) ? year : null;
  } catch {
    return null;
  }
}

function committeeUrl(id) {
  return "https://www.fec.gov/data/committee/" + id + "/";
}

function bulkUrl(cycle) {
  const yy = String(cycle % 100).padStart(2, "0");
  return "https://www.fec.gov/files/bulk-downloads/" + cycle + "/cm" + yy + ".zip";
}

export function careerFor(bioguide) {
  if (!bioguide) return null;
  let row;
  try {
    row = congress().members[bioguide];
  } catch {
    return null;
  }
  if (!row) return null;
  const member = memberUrl(bioguide);
  const retrieved = row.retrieved_at;
  const terms = (row.terms || []).map((term) => {
    const end = term.endYear == null ? "end year not on this record" : String(term.endYear);
    const place = term.district != null ? term.state + "-" + term.district : term.state;
    return {
      text: [term.chamber, term.startYear + "–" + end, "Congress " + term.congress, place].filter(Boolean).join(", ") + ".",
      href: member,
      retrieved_at: retrieved,
      source_name: "Congress.gov",
    };
  });
  const byCongress = new Map();
  for (const bill of row.sponsored_bills || []) {
    const [congressNumber, type, number] = bill;
    const href = publicBillUrl(congressNumber, type, number);
    if (!href) continue;
    if (!byCongress.has(congressNumber)) byCongress.set(congressNumber, []);
    byCongress.get(congressNumber).push({ type, number, href });
  }
  const bills = [...byCongress.entries()].sort((a, b) => a[0] - b[0]).map(([congressNumber, list]) => ({
    congress: congressNumber,
    count: list.length,
    text: "Congress " + congressNumber + ": " + list.length + " sponsored bills and resolutions. Amendments are not included.",
    href: member,
    retrieved_at: retrieved,
    source_name: "Congress.gov",
    links: list,
  }));
  let committees = [];
  try {
    const fec = fecMembers();
    committees = (fec.members[bioguide] || []).map((item) => {
      const years = item.cycles.join(", ");
      return {
        text: item.name + " (" + item.committee_id + "), candidate " + item.candidate_id + ", designation " + (item.designation || "blank") + " as filed, cycles " + years + ".",
        href: committeeUrl(item.committee_id),
        bulk: bulkUrl(item.cycles[item.cycles.length - 1]),
        retrieved_at: fec.retrieved_at,
        source_name: "Federal Election Commission",
      };
    });
  } catch {
    committees = [];
  }
  let lobbying = null;
  try {
    const file = lda();
    const begins = file.begins;
    const years = (row.terms || []).map((term) => term.startYear).filter((year) => Number.isInteger(year));
    const ends = (row.terms || []).map((term) => term.endYear).filter((year) => Number.isInteger(year));
    const first = years.length ? Math.min(...years) : null;
    const open = (row.terms || []).some((term) => term.endYear == null);
    const last = open ? new Date().getUTCFullYear() : (ends.length ? Math.max(...ends) : new Date().getUTCFullYear());
    const start = first == null ? begins : Math.max(begins, first);
    let count = 0;
    const seen = new Set();
    for (const period of file.periods || []) {
      if (!Number.isInteger(period.year) || period.year < start || period.year > last) continue;
      if (!Number.isInteger(period.count)) continue;
      const key = period.year + period.filing_type;
      if (seen.has(key)) continue;
      seen.add(key);
      count += period.count;
    }
    lobbying = {
      text: count
        ? "Activity-bearing lobbying filings in " + start + "–" + last + ", the years this member's service overlaps the lobbying record: " + count.toLocaleString("en-US") + ". This is every filing in those years, not a list of filings that name this member."
        : "Lobbying records begin in " + begins + ". This member's Congress.gov service does not overlap those years.",
      href: file.source_url,
      retrieved_at: file.retrieved_at,
      source_name: file.source_name,
    };
  } catch {
    lobbying = null;
  }
  return {
    firstYear: Number.isInteger(row.first_year) ? row.first_year : null,
    terms,
    bills,
    committees,
    lobbying,
    sponsoredBillCount: row.sponsored_bill_count,
  };
}
