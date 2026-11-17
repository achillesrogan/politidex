export function newestRetrieved(values?: Array<string | null | undefined>): string | null;
export function moneyFlowDates(manifest: { retrieved_at?: string } | null, purposes: { retrieved_at?: string; committees?: Array<Record<string, any>> } | null): Array<string | null | undefined>;
export function committeeDates(doc: { retrieved_at?: string; sources?: Array<{ retrieved_at?: string }>; committees?: Record<string, { retrieved_at?: string; website_retrieved_at?: string | null }> } | null): Array<string | null | undefined>;
export function moneyFlowAsOf(): string | null;
export function committeeAsOf(): string | null;
