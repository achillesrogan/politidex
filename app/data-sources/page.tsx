import PageHead from "@/components/PageHead";
export const metadata = { title: "Data Sources" };
const SOURCES = [
  ["Congress.gov API v3 (Library of Congress)", "https://api.congress.gov/", "Member records, sponsored and cosponsored legislation.", "U.S. government work; attribution suggested: “Data retrieved from Congress.gov.” Free API key, 5,000 requests/hour."],
  ["Office of the Clerk, U.S. House — roll-call votes", "https://clerk.house.gov/Votes", "Every recorded House vote, member by member (official XML).", "U.S. government work."],
  ["Office of the Clerk, U.S. House — member data", "https://clerk.house.gov/xml/lists/MemberData.xml", "House committee assignments.", "U.S. government work."],
  ["U.S. Senate — roll-call votes", "https://www.senate.gov/legislative/votes_new.htm", "Every recorded Senate vote, senator by senator (official XML).", "U.S. government work."],
  ["U.S. Senate — committee memberships", "https://www.senate.gov/general/committee_assignments/assignments.htm", "Senate committee rosters (official XML).", "U.S. government work."],
  ["Federal Election Commission — OpenFEC API", "https://api.open.fec.gov/developers/", "Candidate financial totals and committee-to-committee contributions.", "Public records. Individual contributor information may not be sold or used to solicit contributions or for commercial purposes (52 U.S.C. § 30111(a)(4)); Politidex shows committee-level data only."],
  ["The White House — The Cabinet", "https://www.whitehouse.gov/administration/cabinet/", "Current Cabinet officials and titles.", "U.S. government work."],
  ["U.S. Senate — senators’ contact information (XML)", "https://www.senate.gov/general/contact_information/senators_cfm.xml", "Senate roster fields used to join official records (state, class, and official listings).", "U.S. government work."],
  ["unitedstates/congress-legislators", "https://github.com/unitedstates/congress-legislators", "Cross-reference IDs (Bioguide, FEC, Senate LIS) used to join records.", "CC0 1.0 (public domain dedication). Used as an index; facts are verified against official sources."],
];
export default function DataSources() {
  return (
    <div className="max-w-4xl">
      <PageHead kicker="Data" title="Data sources" dek="Politidex relies on official, public, primary sources. Third-party datasets are used only to join records and are never the citation of record." />
      <div className="grid gap-4">
        {SOURCES.map(([name, url, use, terms]) => (
          <article key={name} className="newspaper-card p-5">
            <h2 className="font-display text-xl font-bold"><a className="link" href={url} rel="noopener noreferrer">{name}</a></h2>
            <p className="mt-1"><strong>Used for:</strong> {use}</p>
            <p className="mt-1 text-[var(--color-muted)]"><strong>Terms:</strong> {terms}</p>
          </article>
        ))}
      </div>
      <div className="prose-news mt-8">
        <h2>Not used as sources</h2>
        <p>Unsourced social-media claims, leaked documents, paywalled opposition research, and scraped news text. AI models are not sources of fact. The OpenSecrets public API (discontinued April 2025) and the ProPublica Congress API (retired 2024) are not used.</p>
        <h2>Planned</h2>
        <p>Senate Lobbying Disclosure Act filings (LDA.gov), House and Senate financial-disclosure reports, and state campaign-finance and ethics filings. Primary sources used in the <a href="/on-the-record">On the record</a> section (organizer event pages, official member releases, and public schedules) are cited on each entry.</p>
      </div>
    </div>
  );
}
