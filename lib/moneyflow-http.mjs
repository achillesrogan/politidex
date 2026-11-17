/** Headers and the fixed error body for the money-flow routes. No paths or stack text. */
export const MONEYFLOW_CACHE = "public, max-age=300";
export const MONEYFLOW_ERROR = { error: "The record could not be loaded." };

export function moneyflowErrorResponse() {
  return { status: 500, body: MONEYFLOW_ERROR, cacheControl: "no-store" };
}
