import { fmtDate as fmtDateTz } from "@/lib/dates";
import fs from "node:fs";
import path from "node:path";

const DIR = path.join(process.cwd(), "data", "build", "site");
export type Claim = { id: string; text: string; value: unknown; excerpt: string; source_name: string; source_url: string; retrieved_at: string; status: string; verified_at?: string; check: Record<string, unknown> };
export type Person = { slug: string; bioguide: string | null; name: string; kind: "congress" | "executive" | "elect"; chamber: string; role: string; party: string | null; state: string | null; stateName: string | null; district: number | null };

function readJSON<T>(f: string, fallback: T): T {
  try { return JSON.parse(fs.readFileSync(path.join(DIR, f), "utf8")) as T; } catch { return fallback; }
}
let _claims: Record<string, Claim> | null = null;
export function claims(): Record<string, Claim> {
  if (!_claims) _claims = readJSON<{ claims: Record<string, Claim> }>("claims.json", { claims: {} }).claims;
  return _claims;
}
/** Returns the claim only if it passed automated verification. Unverified or blocked claims never render. */
export function verified(id?: string | null): Claim | null {
  if (!id) return null;
  const c = claims()[id];
  if (!c || c.status !== "verified" || !c.source_url || !c.retrieved_at) return null;
  return c;
}
export function people(): Person[] {
  if (process.env.POLITIDEX_DATA === "0") return [];
  return readJSON<{ people: Person[] }>("people.json", { people: [] }).people;
}
export function profile(slug: string): any | null {
  if (process.env.POLITIDEX_DATA === "0") return null;
  return readJSON<any>(path.join("profiles", `${slug}.json`), null);
}
export function connections(): any { return readJSON<any>("connections.json", { cosponsor_pairs: [], pacs: [] }); }
export function committeeHistory(code?: string | null): { code: string; name: string; chamber: string; claims: string[]; facts: { kind: string; label: string; claim: string }[] } | null {
  if (!code) return null;
  const all = readJSON<{ committees: Record<string, any> }>("committee-history.json", { committees: {} });
  return all.committees?.[code] || null;
}

export function getStats() {
  const s = readJSON<any>("stats.json", { people: 0, congress: 0, executive: 0, votes: 0, claims: 0, retrieved: "" });
  const c = claims();
  return { ...s, claims: Object.values(c).filter((x) => x.status === "verified").length, people: process.env.POLITIDEX_DATA === "0" ? 0 : s.people };
}
export function bySlug(): Map<string, Person> { return new Map(people().map((p) => [p.bioguide || p.slug, p])); }
export const fmtUSD = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
export const fmtDate = (iso?: string) => fmtDateTz(iso);

/** Approved human-reviewed summary only (status 'approved' set by the editor). Every sentence must cite verified claims. */
export function approvedSummary(slug: string): { sentences: { text: string; ids: string[] }[] } | null {
  try {
    const q = JSON.parse(fs.readFileSync(path.join(process.cwd(), "data", "review-queue", `${slug}.json`), "utf8"));
    if (q.status !== "approved" || !q.second_pass?.ok) return null;
    const sentences = String(q.text).split(/(?<=\])\s+/).map((s: string) => ({ text: s.replace(/\s*\[claim:c_[0-9a-f]{14}\]/g, "").trim(), ids: [...s.matchAll(/\[claim:(c_[0-9a-f]{14})\]/g)].map((m) => m[1]) }));
    if (!sentences.length || sentences.some((s: { ids: string[] }) => !s.ids.length || s.ids.some((i) => !verified(i)))) return null;
    return { sentences };
  } catch { return null; }
}

/** 2026 general election results (official state sources only). */
export function elections(): any | null {
  // Election results are not part of the site build. The file may still exist on disk.
  return readJSON<any>("elections.json", null);
}
export function onTheRecord(): { entries: any[]; note?: string; generated?: string } {
  if (process.env.POLITIDEX_DATA === "0") return { entries: [] };
  return readJSON<any>("on-the-record.json", { entries: [] });
}
export function orgIndex(): { orgs: { slug: string; name: string; kind: string; member_count: number }[]; note?: string } {
  if (process.env.POLITIDEX_DATA === "0") return { orgs: [] };
  return readJSON<any>("orgs-index.json", { orgs: [] });
}
export function org(slug: string): any | null {
  if (process.env.POLITIDEX_DATA === "0") return null;
  return readJSON<any>(path.join("orgs", `${slug}.json`), null);
}
export const fmtInt = (n: number) => n.toLocaleString("en-US");
