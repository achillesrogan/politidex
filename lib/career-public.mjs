/** Public congress.gov bill URLs. Amendments are not given a link here. */

const TYPE_PATH = {
  HR: "house-bill",
  S: "senate-bill",
  HRES: "house-resolution",
  SRES: "senate-resolution",
  HJRES: "house-joint-resolution",
  SJRES: "senate-joint-resolution",
  HCONRES: "house-concurrent-resolution",
  SCONRES: "senate-concurrent-resolution",
};

export function ordinal(congress) {
  const number = Number(congress);
  const teen = number % 100;
  const suffix = teen >= 10 && teen <= 20 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[number % 10] || "th";
  return String(number) + suffix;
}

export function publicBillUrl(congress, billType, number) {
  const slug = TYPE_PATH[String(billType || "").toUpperCase()];
  if (!slug || !/^\d+$/.test(String(number)) || !/^\d+$/.test(String(congress))) return null;
  return "https://www.congress.gov/bill/" + ordinal(congress) + "-congress/" + slug + "/" + Number(number);
}

export function memberUrl(bioguide) {
  if (!/^[A-Z][0-9]{6}$/.test(bioguide || "")) return null;
  return "https://www.congress.gov/member/" + bioguide;
}
