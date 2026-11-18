export function newestRetrieved(values?: Array<string | null | undefined>): string | null;
export const RETRIEVAL_FLOOR: string;
export const MONEY_FLOW_CYCLES: readonly number[];
export function retrievalFloorMs(cycle?: number | string | null): number;
export const MONEY_FLOW_SKEW_MS: number;
export function moneyFlowTimestamp(value: string | null | undefined, now?: number): number | null;
export function newestMoneyFlow(values?: Array<string | null | undefined>, now?: number): string | null;
export function moneyFlowDates(manifest: { retrieved_at?: string } | null, purposes: { retrieved_at?: string; committees?: Array<Record<string, any>> } | null, now?: number): Array<string | null | undefined>;
export function moneyFlowAsOf(now?: number): string | null;
export function committeeDates(doc: { retrieved_at?: string; sources?: Array<{ retrieved_at?: string }>; committees?: Record<string, { retrieved_at?: string; website_retrieved_at?: string | null }> } | null): Array<string | null | undefined>;
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
export function ldaClaimDates(
  ties?: { lobbying?: { rows?: Array<{ claim?: string | null }> }; revolving?: { rows?: Array<{ claim?: string | null }> } } | null,
  retrievedAt?: (claimId?: string | null) => string | null | undefined,
): string[];
