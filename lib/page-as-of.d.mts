export function newestRetrieved(values?: Array<string | null | undefined>): string | null;
export function moneyFlowDates(manifest: { retrieved_at?: string } | null, purposes: { retrieved_at?: string; committees?: Array<Record<string, any>> } | null): Array<string | null | undefined>;
export function committeeDates(doc: { retrieved_at?: string; sources?: Array<{ retrieved_at?: string }>; committees?: Record<string, { retrieved_at?: string; website_retrieved_at?: string | null }> } | null): Array<string | null | undefined>;
export function moneyFlowAsOf(): string | null;
export function committeeAsOf(): string | null;
export function pageCommitteeDates(
  codes?: Array<string | null | undefined>,
  sites?: Record<string, { retrieved_at?: string | null; website_retrieved_at?: string | null } | null> | ((code?: string | null) => { retrieved_at?: string | null; website_retrieved_at?: string | null } | null | undefined),
): Array<string | null | undefined>;
export function profileAsOf(
  claimDates?: Array<string | null | undefined>,
  committeeCodes?: Array<string | null | undefined>,
  sites?: Record<string, { retrieved_at?: string | null; website_retrieved_at?: string | null } | null> | ((code?: string | null) => { retrieved_at?: string | null; website_retrieved_at?: string | null } | null | undefined),
): string | null;
