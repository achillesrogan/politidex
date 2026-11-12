import PageHead from "@/components/PageHead";
import { SITE } from "@/lib/site";
export const metadata = { title: "Methodology & Verification Standard" };
export default function Methodology() {
  return (
    <div className="max-w-3xl">
      <PageHead kicker="Methodology" title="The Verification Standard" dek="Zero unsourced claims. If a statement cannot be traced to a credible primary source and re-checked automatically, it does not appear on Politidex." />
      <div className="prose-news">
        <h2>1. Every claim is an object with proof attached</h2>
        <p>Each fact shown on the site — a party affiliation, a vote position, a dollar figure, a committee seat, a connection — is stored as a <em>claim object</em> with:</p>
        <ul>
          <li>a stable claim ID;</li>
          <li>the public source URL a reader can open;</li>
          <li>the retrieval time (UTC);</li>
          <li>the exact supporting field value or excerpt from that source (for example, the member’s recorded position in a roll-call XML file, or the reported receipts figure in the FEC record).</li>
        </ul>
        <h2>2. An automated verifier re-checks every source</h2>
        <p>Before a build, a verifier re-fetches each source and confirms that the cited value is actually there: numbers must match exactly, names and dates must be present, and vote positions must match the official roll call. A claim that fails, or that cannot be checked (for example, because the source is unreachable), is <strong>blocked</strong> and is not rendered.</p>
        <h2>3. AI may only restate verified claims</h2>
        <p>Where AI helps draft a short summary, it is given only verified claim objects and must attach a claim ID to every sentence. A second automated pass rejects any sentence that has no claim ID behind it, or that introduces names, numbers, dates, or assertions that are not in the cited claims. AI is never used as a source of facts.</p>
        <h2>4. What is published, and what is held</h2>
        <p>A fact is published only when automated match rules accept it and the verifier can re-fetch the source and confirm the cited excerpt or total. Ambiguous matches are not published: they are written to a local review queue for later inspection. There is no human-editor approval step between a passing automated match and a passing build. Until launch, the entire site is excluded from search engines.</p>
        <h2>5. Public corrections log</h2>
        <p>Errors are corrected openly and dated on the <a href="/corrections">corrections page</a>. Report a problem to <a href={`mailto:${SITE.correctionsEmail}`}>{SITE.correctionsEmail}</a>.</p>
        <h2>6. Build-time enforcement</h2>
        <p>The site’s build fails if any rendered fact references a claim that is missing, unverified, or lacks a source URL, retrieval time, or supporting value. This check runs automatically on every build.</p>

        <h2>Record versus Analysis</h2>
        <p>Profiles separate two kinds of content, and they are styled differently:</p>
        <ul>
          <li><strong>Record</strong> (blue label): facts copied from official records, each with a citation.</li>
          <li><strong>Analysis</strong> (amber label): measures we compute from the record using the methods described below. Analysis is not an allegation of wrongdoing and is not legal advice.</li>
        </ul>

        <h2 id="on-the-record">On the record (side by side)</h2>
        <p>A planned “On the record” section would place two independently verified records next to each other. Politidex would not add a conclusion. This section is not published on the site today. An entry would be published only when both halves pass verification:</p>
        <ul>
          <li><strong>Record A.</strong> An official House Clerk or Senate roll-call XML file lists the member as Not Voting on a named vote. The claim stores the vote number, question, date, time, and position, and the verifier re-fetches that roll call to confirm the position.</li>
          <li><strong>Record B.</strong> A credible primary source names that same member at a specific event on the same date. Qualifying sources are the organizer’s own event page or official release; the member’s official site, press release, or verified social post; or an official public schedule. A news report on its own does not qualify, unless it quotes a primary record that can be re-checked. The verifier re-fetches the source and requires an exact excerpt match that includes the member’s name.</li>
        </ul>
        <p>Every entry uses a fixed template: “[Member] is recorded as Not Voting on [vote, date, time]. [Source] places [Member] at [event] on [date].” A standing note on the page states that Politidex presents the records without drawing conclusions, and that absences have many causes. Loaded or causal wording is barred from the section, and the build fails if it appears there.</p>

        <h2 id="politi-matrix-version-1">Politi-Matrix, version 1</h2>
        <p>The Politi-Matrix is meant to compare how officials present themselves with what the record shows. Version 1 uses <strong>record data only</strong>. Stated positions will be added only where a sourced quote or official statement exists, and will be labeled as such.</p>
        <h3>Missed-vote rate</h3>
        <p>Of all recorded roll-call votes in the current Congress in which the member is listed on the official tally, the share recorded as “Not Voting.” Members who joined or left mid-term are only counted for roll calls on which they appear.</p>
        <h3>“Present” votes</h3>
        <p>The number of roll calls on which the member voted “Present” rather than Yea or Nay.</p>
        <h3>Party-line rate</h3>
        <p>Of the member’s Yea/Nay votes, the share that matched the majority of their own party’s Yea/Nay votes on the same roll call, using the party listed on the official tally. Ties are excluded. Not computed for independents.</p>
        <h3>Procedural versus final-passage divergence</h3>
        <p>For measures that received both a procedural roll call (such as cloture, a motion to proceed, or ordering the previous question) and a final-passage roll call under the same measure number, the number of measures where the member’s procedural vote and passage vote point in opposite directions. This can have ordinary explanations; it is shown as a pattern in the record, not as a judgment.</p>
        <h3>Limits</h3>
        <ul>
          <li>Roll-call votes are only a subset of congressional action; voice votes and unanimous consent are not recorded by name.</li>
          <li>Absences can reflect illness, family leave, or official duties.</li>
          <li>Official records can be amended or published late. Each profile shows the retrieval date.</li>
        </ul>

        <h2 id="connections">Connections</h2>
        <p>Each current member’s profile has a Connections panel built only from official records. A connection documents that a relationship appears in the record. It does not, by itself, imply coordination, influence, or wrongdoing. Individual contributors are never shown.</p>
        <ul>
          <li><strong>Money.</strong> Itemized committee contributions (FEC transaction type 24K, memo-coded rows excluded from totals) to the member’s principal campaign committee, from the official <a href="https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/">contributions from committees to candidates</a> file, and to the member’s leadership PAC, from the official <a href="https://www.fec.gov/campaign-finance-data/any-transaction-one-committee-another-file-description/">any transaction from one committee to another</a> file, 2026 cycle. Interest group grouping uses only the FEC committee master’s <em>Interest group category</em> (ORG_TP). Politidex does not invent industry labels. The verifier re-fetches those official bulk files and re-sums each published total.</li>
          <li><strong>Lobbying.</strong> Senate Lobbying Disclosure Act quarterly filings retrieved from <a href="https://lda.gov/api/v1/filings/">LDA.gov</a> for 2025–2026. A match is listed only when the filing’s specific-issues text names a bill the member sponsored or cosponsored in the 119th Congress (Congress.gov), the prefix is a case-sensitive bill form, the filing period does not end before that bill was introduced, the excerpt does not cite a 110th–118th Congress law or public law, and the text immediately before the number in a Title (number) list, or between this bill number and the next (including a House/Senate companion cited in the same cluster, such as H.R. 1492/S. 832), contains a distinctive multi-word short title or acronym. A title attached to the next number in a Title (number) list is not used to corroborate this bill. Those titles come from Congress.gov bill titles when a formal short title is listed; when Congress.gov has only a long official title, a short title or acronym is used only if many LDA filings attach the same distinctive name to that bill number (for example, H.R. 1492, the EPIC Act). A filing date is never, by itself, a reason to publish. Bare lists of bill numbers and ambiguous mentions go to a review queue and are not published. The verifier re-fetches the filing and requires an exact excerpt match; that check proves the excerpt exists, not that the bill match is correct — match rules are tested separately. LDA filings do not say which congressional offices were contacted; a listed filing does not mean the member was lobbied. Each lobbying page states that the Senate Office of Public Records cannot vouch for the accuracy of the data after retrieval, and Politidex does not use the Senate seal.</li>
          <li><strong>Outside spending.</strong> Independent expenditures in the official FEC 2026 independent expenditures file, supporting or opposing the member. For each spender, candidate, and transaction ID, the row with the highest file number (latest amendment) is used. A later filing is merged with an earlier one only when the later row's previous-file number (or amendment chain) points to the earlier filing and they share spender, candidate, amount, payee, and support or oppose. Two unlinked notices or reports with the same amount are counted as separate expenditures. The verifier re-fetches the file and re-sums each published total.</li>
          <li><strong>People.</strong> Cosponsorship counts from Congress.gov (the same verified figures already shown on the profile) are listed separately from lobbyists. A lobbyist is listed only when the covered-position text names the member. Title, chamber, and state-tag checks apply to every match kind, including full-name matches. Title plus surname only is never published. Where legislators-historical records another person who shares the first and last name (or a nickname variant such as Rob/Robert/Bob), a published match also needs a state tag, service years, or chamber that uniquely fits this member; otherwise the row is rejected or sent to review. Clear mismatches (wrong chamber, wrong state, years that do not overlap this member’s service) are dropped. A covered position is a government job the lobbyist reports having held. It does not mean the lobbyist works for or with this member now. The covered-position excerpt is shown as filed; Politidex does not characterize the relationship. Duplicate rows for the same lobbyist and registrant are collapsed to one.</li>
        </ul>
        <p>Remaining limits on bill matching: two Congresses can use the same bill number. Even with a short-title or acronym match in the local window, a filing can still be discussing a similarly named measure if it does not cite an earlier Congress or public law. Year-like Senate numbers (2000–2030) are published only with that distinctive-title corroboration. Mentions that cannot be corroborated, and bare lists of bill numbers, are queued for review rather than shown.</p>
                <p>Record cards use a plain-English summary of the verified total. The machine-check expression stays on the claim and behind a “How this was checked” disclosure, with links to the official FEC filing image (when the bulk file lists an image number), the FEC receipts or disbursements view filtered by committee and cycle, and the official bulk file. Interest group category is shown as “Not categorized by FEC” when the committee master leaves ORG_TP blank. Committee type and designation are explained in plain words, with the official FEC label in parentheses. A connected organization name is shown only as listed on the FEC committee master. Committee assignment pop-ups describe what a committee does and when it was created only when an official House or Senate committee page or history office supplies a verified excerpt; committees without such a source have no pop-up.</p>
        <p>Organization pages at <code>/org/…</code> list current members whose published Connections panel includes that committee, client, or registrant. That list is not a complete extract of every row in the official file.</p>
      </div>
    </div>
  );
}
