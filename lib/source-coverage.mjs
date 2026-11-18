/** The coverage line is a Congress.gov career sentence. Executive profiles have no bioguide id. */

export function sourceCoverageFor(person) {
  const bioguide = person && person.bioguide;
  if (typeof bioguide !== "string" || !/^[A-Z]\d{6}$/.test(bioguide)) return null;
  return { bioguide };
}
