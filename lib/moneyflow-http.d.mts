export const MONEYFLOW_CACHE: string;
export const MONEYFLOW_ERROR: { error: string };
export function moneyflowErrorResponse(): { status: number; body: { error: string }; cacheControl: string };
export function moneyflowPublished(manifest: { not_in_web_bundle?: boolean } | null | undefined): boolean;
export function pilotCommitteeIds(manifest: { pilot?: Array<{ committee_id?: string }> } | null | undefined): Set<string>;
export function moneyflowSources(shard: any): Array<Record<string, any>>;
export function moneyflowSourceReady(source: Record<string, any> | null | undefined): boolean;
