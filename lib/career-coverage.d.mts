export function coverageSentence(
  memberFirstYear: number | null,
  coverage: { fec?: { begins?: number }; lda?: { begins?: number }; congress?: { without_member?: string } },
): string;
