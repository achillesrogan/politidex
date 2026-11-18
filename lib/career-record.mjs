/** Load one member's career facts. Only the files this page reads are opened. */
import fs from "node:fs";
import path from "node:path";
import { memberUrl, publicBillUrl, sponsoredSearchUrl } from "./career-public.mjs";

function readAt(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

let coverageFile;
let congressFile;
let fecMembersFile;
let firstYearsFile;

export function readCoverage() {
  if (!coverageFile) coverageFile = readAt(path.join(process.cwd(), "data/career/coverage.json"));
  return coverageFile;
}

function congress() {
  if (!congressFile) congressFile = readAt(path.join(process.cwd(), "data/career/congress.json"));
  return congressFile;
}

function fecMembers() {
  if (!fecMembersFile) fecMembersFile = readAt(path.join(process.cwd(), "data/career/fec-members.json"));
  return fecMembersFile;
}

export function memberFirstYear(bioguide) {
  if (!bioguide) return null;
  try {
    if (!firstYearsFile) firstYearsFile = readAt(path.join(process.cwd(), "data/career/first-years.json"));
    const year = firstYearsFile[bioguide];
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

const DESIGNATION = {
  P: "principal campaign committee",
  A: "authorized committee",
  J: "joint fundraising committee",
};

function yearList(cycles) {
  return cycles.join(", ");
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
    href: sponsoredSearchUrl(bioguide, congressNumber) || member,
    retrieved_at: retrieved,
    source_name: "Congress.gov",
    links: list,
  }));
  let committees = [];
  try {
    const fec = fecMembers();
    committees = (fec.members[bioguide] || []).map((item) => {
      const label = DESIGNATION[item.designation] || ("designation " + (item.designation || "blank"));
      const latest = item.cycles[item.cycles.length - 1];
      return {
        text: item.name + " (" + item.committee_id + "), " + label + " (" + item.designation + ") as filed in " + yearList(item.cycles) + ", candidate " + item.candidate_id + ".",
        href: committeeUrl(item.committee_id),
        bulk: bulkUrl(latest),
        retrieved_at: fec.retrieved_at,
        source_name: "Federal Election Commission",
      };
    });
  } catch {
    committees = [];
  }
  return {
    firstYear: Number.isInteger(row.first_year) ? row.first_year : null,
    terms,
    bills,
    committees,
    sponsoredBillCount: row.sponsored_bill_count,
  };
}
