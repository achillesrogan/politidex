export const MONEYFLOW_CACHE: string;
export const MONEYFLOW_ERROR: { error: string };
export function moneyflowErrorResponse(): { status: number; body: { error: string }; cacheControl: string };
