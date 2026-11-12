import PageHead from "@/components/PageHead";
import { SITE } from "@/lib/site";
import log from "@/data/manual/corrections-log.json";
export const metadata = { title: "Corrections" };
type Entry = { date: string; page: string; was: string; now: string; source: string };
export default function Corrections() {
  const entries = (log.entries as Entry[]) || [];
  return (
    <div className="max-w-3xl">
      <PageHead kicker="Accountability" title="Corrections" dek="We correct errors openly. Every correction is dated and listed here." />
      <div className="prose-news">
        <h2>Report an error</h2>
        <p>Email <a href={`mailto:${SITE.correctionsEmail}`}>{SITE.correctionsEmail}</a> with the page link, what is wrong, and a link to a public record that shows the correct information. Please do not send private personal information about anyone.</p>
        <h2>How we handle reports</h2>
        <ol>
          <li>We check the report against the cited primary source and any source you provide.</li>
          <li>If the record supports the correction, we fix the claim, re-run verification, and log the change below.</li>
          <li>If an official source itself is later amended, we update to the amended record and note the date.</li>
        </ol>
        <p>Politidex is maintained by a small volunteer team; we do not promise a fixed response time, but corrections take priority over new features.</p>
        <h2>Corrections log</h2>
      </div>
      {entries.length === 0 ? (
        <p className="newspaper-card p-5 text-[var(--color-muted)]">No corrections have been logged yet. Log last updated {log.updated}.</p>
      ) : (
        <ul className="grid gap-3">{entries.map((e, i) => (
          <li key={i} className="newspaper-card p-4"><strong>{e.date}</strong> — {e.page}: “{e.was}” → “{e.now}” (<a className="link" href={e.source}>source</a>)</li>
        ))}</ul>
      )}
    </div>
  );
}
