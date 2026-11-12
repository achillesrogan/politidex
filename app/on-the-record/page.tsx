import Link from "next/link";
import PageHead from "@/components/PageHead";
import Fact from "@/components/Fact";
import { onTheRecord, verified } from "@/lib/data";

export const metadata = { title: "On the record", alternates: { canonical: "/on-the-record" } };

export default function OnTheRecordPage() {
  const data = onTheRecord();
  const entries = (data.entries || []).filter((e: any) => verified(e.record_a?.claim) && verified(e.record_b?.claim));
  return (
    <div data-section="on-the-record">
      <PageHead
        kicker="Side by side"
        title="On the record"
        dek="Two independently verified public records, shown next to each other. Politidex does not add a conclusion."
      />

      <aside className="newspaper-card p-5 mb-8 max-w-3xl">
        <p className="text-lg">Politidex presents these records side by side without drawing conclusions. Absences have many causes.</p>
        <p className="mt-2 text-sm text-[var(--color-muted)]">If a record is wrong, <Link className="link" href="/corrections">report a correction</Link>.</p>
      </aside>

      {entries.length === 0 ? (
        <section className="newspaper-card p-6 mb-10 max-w-3xl">
          <div className="tag text-[var(--color-muted)]">No entries yet</div>
          <p className="mt-2 text-lg">There are no entries in this section yet. An entry is added only when both records described below have been verified.</p>
        </section>
      ) : (
        <div className="grid gap-8 mb-10">
          {entries.map((e: any) => (
            <article key={e.id} id={e.id} className="newspaper-card p-5 sm:p-6 min-w-0">
              <h2 className="font-display text-2xl font-bold mb-4">
                {e.member_slug ? <Link className="link" href={`/p/${e.member_slug}`}>{e.member_name}</Link> : e.member_name}
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                <section className="min-w-0 border-l-4 border-[var(--color-record)] pl-4">
                  <div className="tag text-[var(--color-record)]">Record A · official roll call</div>
                  <p className="mt-2">
                    <Fact claim={e.record_a.claim}>
                      {e.member_name} is recorded as Not Voting on {e.record_a.vote_label}, {e.record_a.when}.
                    </Fact>
                  </p>
                  {e.record_a.question ? <p className="mt-1 text-sm text-[var(--color-muted)]">{e.record_a.question}{e.record_a.measure ? ` — ${e.record_a.measure}` : ""}</p> : null}
                </section>
                <section className="min-w-0 border-l-4 border-[var(--color-record)] pl-4">
                  <div className="tag text-[var(--color-record)]">Record B · primary source</div>
                  <p className="mt-2">
                    <Fact claim={e.record_b.claim}>
                      {e.record_b.source_name} places {e.member_name} at {e.record_b.event} on {e.record_b.date}.
                    </Fact>
                  </p>
                </section>
              </div>
            </article>
          ))}
        </div>
      )}

      <section className="prose-news max-w-3xl">
        <h2>How an entry is added</h2>
        <p>An entry is published only when both of the following have been verified:</p>
        <ul>
          <li><strong>Record A.</strong> An official House or Senate roll-call record lists the member as Not Voting on a named vote, with the vote number, question, date, and time.</li>
          <li><strong>Record B.</strong> A credible primary source names that same member at a specific event on the same date. Qualifying sources are the organizer’s own event page or official release; the member’s official site, press release, or verified social post; or an official public schedule. News reports on their own do not qualify, unless they quote a primary record that can be checked.</li>
        </ul>
        <p>Each half is re-checked against its source before a build. If either half cannot be confirmed, the entry is not shown. The wording of every entry follows a fixed template: “[Member] is recorded as Not Voting on [vote, date, time]. [Source] places [Member] at [event] on [date].”</p>
        <p>See the <Link className="link" href="/methodology#on-the-record">Verification Standard</Link> and the <Link className="link" href="/corrections">corrections log</Link>.</p>
      </section>
    </div>
  );
}
