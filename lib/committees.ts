import fs from "node:fs";
import path from "node:path";
import { publicSourceHref } from "@/lib/source-href.mjs";

export type CommitteeSite = {
  code: string;
  name: string;
  chamber: "senate" | "house" | "joint";
  website: string | null;
  website_source_url: string | null;
  website_retrieved_at: string | null;
};

export type CommitteeFact = {
  kind: string;
  text: string;
  source_name: string;
  source_url: string;
  retrieved_at: string;
  excerpt: string;
};

type SummaryEntry = {
  review_status?: string;
  facts?: CommitteeFact[];
};

const root = process.cwd();

function readJSON<T>(rel: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(path.join(root, rel), "utf8")) as T;
  } catch {
    return fallback;
  }
}

export function committeeSite(code?: string | null): CommitteeSite | null {
  if (!code) return null;
  const doc = readJSON<{ committees?: Record<string, CommitteeSite> }>("data/committees/sites.json", {});
  const row = doc.committees?.[code];
  if (!row) return null;
  const website = row.website ? publicSourceHref(row.website) : null;
  return { ...row, website };
}

/** Editor-approved sentences only. Proposed text is never rendered. */
export function approvedCommitteeFacts(code?: string | null): CommitteeFact[] {
  if (!code) return [];
  const doc = readJSON<{ committees?: Record<string, SummaryEntry> }>("data/committees/summaries.json", {});
  const row = doc.committees?.[code];
  if (!row || row.review_status !== "approved" || !Array.isArray(row.facts)) return [];
  return row.facts.filter((f) => f && f.text && f.source_url && f.retrieved_at && f.excerpt && publicSourceHref(f.source_url));
}
