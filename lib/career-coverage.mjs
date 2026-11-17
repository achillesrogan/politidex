/** Where each source on a profile begins. Years come from coverage.json. */

export function coverageSentence(memberFirstYear, coverage) {
  const fec = coverage && coverage.fec && coverage.fec.begins;
  const lda = coverage && coverage.lda && coverage.lda.begins;
  const fallback = coverage && coverage.congress && coverage.congress.without_member;
  const congress = Number.isInteger(memberFirstYear)
    ? "Congress.gov records from " + memberFirstYear
    : "Congress.gov records from the " + (fallback || "119th Congress");
  return "FEC records from " + fec + "; lobbying records from " + lda + "; " + congress + ". Individual contribution files are not included.";
}
