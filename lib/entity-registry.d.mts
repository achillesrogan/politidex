export const CONFIDENCE_BADGES: readonly ["exact ID match", "amended filing", "proposed / in review"];

export function confidenceBadge(record: {
  review_status?: string;
  amended?: boolean;
  official_id?: string | null;
  source_url?: string | null;
  check?: Record<string, unknown> | null;
} | null | undefined): "exact ID match" | "amended filing" | "proposed / in review" | null;

export function badgeForClaim(claim: {
  source_url?: string;
  check?: Record<string, any> | null;
} | null | undefined): "exact ID match" | "amended filing" | "proposed / in review" | null;

export type EntityRecord = {
  kind: string;
  name: string;
  official_id: string | null;
  source_name: string;
  source_url: string;
  retrieved_at: string | null;
  href: string | null;
  badge: "exact ID match" | "amended filing" | "proposed / in review" | null;
};

export function entityRecord(input: {
  kind?: string;
  name?: string;
  official_id?: string | null;
  source_name?: string;
  source_url?: string;
  retrieved_at?: string | null;
  href?: string | null;
  amended?: boolean;
  review_status?: string;
}): EntityRecord | null;

export function registryIndex(entities: Array<EntityRecord | null | undefined>): Map<string, EntityRecord>;
export function findEntity(index: Map<string, EntityRecord>, kind: string, officialId: string | null | undefined): EntityRecord | null;
export function latestRetrieved(values: Array<string | null | undefined>): string | null;
