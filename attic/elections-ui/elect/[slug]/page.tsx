import { notFound } from "next/navigation";
import Link from "next/link";
import Fact from "@/components/Fact";
import { RecordModule } from "@/components/Module";
import RaceTable, { statusBadge, raceTitle } from "@/components/RaceTable";
import { elections, verified, fmtInt } from "@/lib/data";

export const dynamicParams = false;
export function generateStaticParams() {
  const E = elections();
  const ps = (E?.elect || []).map((e: any) => ({ slug: e.slug }));
  return ps.length ? ps : [{ slug: "_none" }];
}
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const e = elections()?.elect.find((x: any) => x.slug === slug);
  return { title: e ? `${e.name} — 2026 ${e.office} result` : "2026 result", alternates: { canonical: `/elect/${slug}` } };
}
export default async function ElectPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const E = elections(); const e = E?.elect.find((x: any) => x.slug === slug);
  if (!e || !verified(e.claim)) notFound();
  const r = E.races.find((x: any) => x.id === e.race);
  const gov = e.office === "Governor";
  return (
    <article>
      <header className="mb-6 border-b-4 border-double border-[var(--color-ink)] pb-4">
        <div className="tag text-[var(--color-muted)]">2026 election · {gov ? "Governor" : e.office === "U.S. Senate" ? "U.S. Senate" : "U.S. House of Representatives"}</div>
        <h1 className="font-display text-4xl sm:text-5xl font-black masthead-shadow mt-1">{e.name}</h1>
        <p className="text-xl text-[var(--color-muted)] mt-1">{gov ? "Projected winner, governor" : `${e.office === "U.S. Senate" ? "Senator" : "Representative"}-elect`} · {raceTitle(r).split(" · ")[1]} · {e.party} (party as listed by the state)</p>
        <div className="mt-2 flex flex-wrap gap-2 items-center">{statusBadge(r)}<span className="text-sm">{e.label}</span></div>
      </header>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 grid gap-6 content-start min-w-0">
          <RecordModule title="Result">
            <p className="mb-2">{e.name} received <Fact claim={e.claim}>{fmtInt(r.winner.votes)} votes ({r.winner.pct.toFixed(1)}% of votes listed)</Fact> in the {raceTitle(r)} contest, according to the official results of {e.source_name.split(" — ")[0]}.</p>
            <RaceTable r={r} />
          </RecordModule>
          <RecordModule title="Source excerpt">
            <p className="text-sm mb-2">Exact text from the official source, re-checked before every build:</p>
            <pre className="text-xs whitespace-pre-wrap break-words bg-[var(--color-paper,#f7f3ea)] p-3 border">{e.excerpt_lines.join("\n")}</pre>
            <p className="text-sm mt-2"><a className="link" href={e.source_url} rel="noopener noreferrer">{e.source_url}</a> · retrieved {e.retrieved_at.slice(0, 16).replace("T", " ")} UTC</p>
          </RecordModule>
        </div>
        <aside className="grid gap-6 content-start min-w-0">
          <section className="newspaper-card p-5 min-w-0">
            <h2 className="font-display text-xl font-bold mb-2">{gov ? "Office" : "Seat"}</h2>
            {gov ? (
              <p className="text-sm">Politidex does not yet track sitting governors, so the current officeholder is not shown here.</p>
            ) : r.incumbent && verified(r.incumbent.claim) ? (
              <p className="text-sm">{e.office === "U.S. House" ? `District ${r.district} is` : `This ${r.seat_class || ""} seat is`} currently held by <Fact claim={r.incumbent.claim}><Link className="link" href={`/p/${r.incumbent.slug}`}>{r.incumbent.name}</Link></Fact> ({r.incumbent.party}).{e.office === "U.S. House" ? " District boundaries may differ under the 2026 map." : ""}</p>
            ) : (
              <p className="text-sm">No current member is listed for this {e.office === "U.S. House" ? "district number" : "seat"} in the official congressional records we use.</p>
            )}
            <p className="text-sm mt-3">This page will gain a full record (votes, committees, money) once the winner takes office and official records exist.</p>
          </section>
          <section className="newspaper-card p-5 min-w-0 text-sm">
            <p><Link className="link" href={`/elections-2026#${r.id}`}>All {r.stateName} results →</Link></p>
            <p className="mt-2">Found an error? <Link className="link" href="/corrections">Report it</Link>.</p>
          </section>
        </aside>
      </div>
    </article>
  );
}
