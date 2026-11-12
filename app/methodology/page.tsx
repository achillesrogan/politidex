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
        <h2>4. Nothing publishes automatically</h2>
        <p>Everything that passes verification goes into a review queue. A human editor approves it before it is published. Until launch, the entire site is excluded from search engines.</p>
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
        <p>The <a href="/on-the-record">On the record</a> section places two independently verified records next to each other. Politidex does not add a conclusion. An entry is published only when both halves pass verification:</p>
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

        <h2>Connections</h2>
        <p>Version 1 connections are built only from records:</p>
        <ul>
          <li><strong>Shared committee:</strong> both members appear on the same official committee roster.</li>
          <li><strong>Cosponsorship:</strong> one member cosponsored a bill the other sponsored, as listed by Congress.gov.</li>
          <li><strong>Shared committee-level contributor:</strong> both members’ principal campaign committees reported receiving contributions from the same political committee (PAC or party committee) in the 2025–2026 cycle, per FEC filings. Individual contributors are never shown.</li>
        </ul>
        <p>A connection documents that a relationship appears in the record. It does not, by itself, imply coordination, influence, or wrongdoing.</p>
      </div>
    </div>
  );
}
