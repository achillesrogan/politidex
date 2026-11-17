/** Where each source on a profile begins. Individual contribution files are excluded. */

export function coverageSentence(earliestCongressYear) {
  const congress = Number.isInteger(earliestCongressYear)
    ? "Congress.gov records from " + earliestCongressYear
    : "Congress.gov records from the 119th Congress";
  return "FEC records from 1980; lobbying records from 1999; " + congress + ". Individual contribution files are not included.";
}
