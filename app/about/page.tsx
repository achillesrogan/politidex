import PageHead from "@/components/PageHead";
import { SITE } from "@/lib/site";
export const metadata = { title: "About" };
export default function About() {
  return (
    <div className="max-w-3xl">
      <PageHead kicker="About" title="An open-source public record of power" dek="Politidex is a non-profit, open-source project that aggregates official public records about U.S. politicians and the documented connections between them." />
      <div className="prose-news">
        <h2>The double-edged sword</h2>
        <p>Artificial intelligence cuts both ways. In the hands of the powerful, it can become a mechanism of influence and control that the rest of us grow dependent on without seeing how it works. Used in the open, the same technology can read through votes, filings, and disclosures at a speed no newsroom or volunteer could match, and surface connections that would otherwise take people months or years to assemble.</p>
        <p>Politidex is built to be the second edge of that sword: a public tool that helps citizens hold officials accountable — with every claim tied to a credible, verifiable source that anyone can open and check.</p>
        <h2>What we publish</h2>
        <ul>
          <li><strong>Record:</strong> facts taken directly from official public records — offices held, roll-call votes, bill sponsorships, committee assignments, and campaign-finance totals reported to the FEC.</li>
          <li><strong>Connections:</strong> relationships documented in those records, such as shared committees, cosponsored bills, and contributions from the same political committee. Each connection links to its evidence.</li>
          <li><strong>Analysis:</strong> clearly labeled, method-documented measures computed from the record, such as how often a member missed votes. Analysis is kept visually separate from Record.</li>
          <li><strong>On the record:</strong> two independently verified records shown side by side — an official roll-call absence and a primary source placing the same member at an event on the same date — without a stated conclusion.</li>
        </ul>
        <h2>What we do not publish</h2>
        <ul>
          <li>Claims that cannot be traced to a public record.</li>
          <li>Speculation about motives, private lives, or wrongdoing.</li>
          <li>Contact details or addresses of private individuals, including individual campaign contributors. Federal law restricts the use of individual contributor information from FEC reports, and we only publish committee-level figures.</li>
        </ul>
        <h2>How AI is used</h2>
        <p>AI helps us find, organize, and summarize records. It never publishes on its own. An AI-drafted sentence may only restate a claim that our verifier has already confirmed against its source, a second automated pass rejects anything unsupported, and a human editor reviews every item before it goes live. See the <a href="/methodology">Verification Standard</a>.</p>
        <h2>Open source and non-profit</h2>
        <p>Politidex is a public-good project, not a commercial product. The code is released under the GNU AGPL-3.0, and our original data compilations under CC BY 4.0 where the underlying source terms allow. Coverage starts with the federal government and will expand to state and local officials.</p>
        <h2>Contact</h2>
        <p>Editorial: <a href={`mailto:${SITE.editorEmail}`}>{SITE.editorEmail}</a><br />Corrections: <a href={`mailto:${SITE.correctionsEmail}`}>{SITE.correctionsEmail}</a></p>
      </div>
    </div>
  );
}
