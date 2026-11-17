export type CareerTerm = { text: string; href: string; retrieved_at: string; source_name: string };
export type CareerBill = { type: string; number: string; href: string };
export type CareerBillGroup = { congress: number; count: number; text: string; href: string; retrieved_at: string; source_name: string; links: CareerBill[] };
export type CareerCommittee = { text: string; href: string; bulk: string; retrieved_at: string; source_name: string };
export type CareerLobbying = { text: string; href: string; retrieved_at: string; source_name: string };
export type Career = {
  firstYear: number | null;
  terms: CareerTerm[];
  bills: CareerBillGroup[];
  committees: CareerCommittee[];
  lobbying: CareerLobbying | null;
  sponsoredBillCount: number;
};
export function readCoverage(): { fec: { begins: number }; lda: { begins: number }; congress: { begins: number; without_member: string } };
export function memberFirstYear(bioguide: string | null | undefined): number | null;
export function careerFor(bioguide: string | null | undefined): Career | null;
