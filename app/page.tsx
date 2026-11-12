import Link from "next/link";
import { SITE } from "@/lib/site";
import { getStats } from "@/lib/data";

export default function Home() {
  const s = getStats();
  return (
    <div>
      <section className="text-center border-b-4 border-double border-[var(--color-ink)] pb-6">
        <div className="tag text-[var(--color-muted)]">Open source · Non-profit · Public record</div>
        <h1 className="font-display font-black text-5xl sm:text-7xl md:text-8xl tracking-tight masthead-shadow mt-2">POLITIDEX</h1>
        <p className="font-display italic text-xl sm:text-2xl mt-2">The public record of power — who holds it, how they use it, and who they are connected to.</p>
      </section>

      <section className="grid gap-6 md:grid-cols-3 mt-8">
        <article className="newspaper-card paper-crease p-6 md:col-span-2">
          <div className="tag text-[var(--color-record)]">What this is</div>
          <h2 className="font-display text-3xl font-bold mt-1">A field guide to U.S. politicians, built only from verifiable records</h2>
          <div className="prose-news mt-3">
            <p>Politidex profiles public officials using official public records: congressional roll-call votes, bill sponsorships, committee rosters, and campaign-finance reports filed with the Federal Election Commission. Each fact on a profile links to the record it came from and shows the date we retrieved it.</p>
            <p>Connections between people are shown only when a public record supports them — for example, serving on the same committee, cosponsoring the same bills, or receiving contributions from the same political committee. A connection is a documented fact, not an accusation.</p>
          </div>
          {SITE.dataEnabled && s.people > 0 ? (
            <p className="mt-4 flex flex-wrap gap-3">
              <Link href="/people" className="inline-block bg-[var(--color-ink)] text-white px-5 py-2 font-sans text-sm font-semibold">Browse {s.people.toLocaleString()} profiles</Link>
              <Link href="/connections" className="inline-block border border-[var(--color-ink)] px-5 py-2 font-sans text-sm font-semibold">See record-based connections</Link>
            </p>
          ) : (
            <p className="mt-4 font-sans text-sm text-[var(--color-muted)]">Profiles are being built and verified. They will appear here after review.</p>
          )}
        </article>
        <aside className="newspaper-card p-6">
          <div className="tag text-[var(--color-analysis)]">Our rule</div>
          <h2 className="font-display text-2xl font-bold mt-1">Zero unsourced claims</h2>
          <ul className="prose-news mt-3">
            <li>Every claim carries a source link, a retrieval time, and the exact value it relies on.</li>
            <li>An automated verifier re-checks each source. Anything it cannot confirm is not published.</li>
            <li>AI may only restate verified records, and a human editor approves every AI-drafted summary before it renders.</li>
          </ul>
          <Link className="link" href="/methodology">The Verification Standard →</Link>
        </aside>
      </section>

      {SITE.dataEnabled && s.people > 0 && (
        <section className="mt-8 grid gap-4 grid-cols-2 md:grid-cols-4">
          {[["Members of Congress", s.congress], ["Executive officials", s.executive], ["Roll-call votes indexed", s.votes], ["Verified claims", s.claims]].map(([k, v]) => (
            <div key={k as string} className="newspaper-card p-4 text-center">
              <div className="font-display text-3xl font-black">{(v as number).toLocaleString()}</div>
              <div className="tag text-[var(--color-muted)] mt-1">{k}</div>
            </div>
          ))}
          <p className="col-span-2 md:col-span-4 text-sm text-[var(--color-muted)] font-sans">Counts from the current data snapshot (retrieved {s.retrieved || "—"}). See <Link className="link" href="/data-sources">data sources</Link>.</p>
        </section>
      )}

      <section className="mt-10 grid gap-6 md:grid-cols-2">
        <article className="newspaper-card p-6">
          <div className="tag text-[var(--color-muted)]">Why</div>
          <h2 className="font-display text-2xl font-bold mt-1">The other edge of the sword</h2>
          <p className="prose-news mt-3">Artificial intelligence is a double-edged tool. It can concentrate power in the hands of those who control it — and it can also help ordinary people read thousands of public records quickly and see patterns that would otherwise take years of work. Politidex aims to be the public-interest edge: accountability backed by evidence anyone can check.</p>
          <Link className="link" href="/about">About Politidex →</Link>
        </article>
        <article className="newspaper-card p-6">
          <div className="tag text-[var(--color-muted)]">Coming next</div>
          <h2 className="font-display text-2xl font-bold mt-1">Roadmap</h2>
          <ul className="prose-news mt-3">
            <li>Federal: all current members of Congress, the President, Vice President, and Cabinet.</li>
            <li>Then state legislatures, statewide offices, and local officials.</li>
          </ul>
        </article>
      </section>
    </div>
  );
}
