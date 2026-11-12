import Link from "next/link";
import PageHead from "@/components/PageHead";
import Fact from "@/components/Fact";
import RaceTable, { statusBadge, raceTitle } from "@/components/RaceTable";
import { elections, verified, fmtInt } from "@/lib/data";

export const metadata = { title: "2026 General Election Results", alternates: { canonical: "/elections-2026" } };

export default function Elections2026() {
  const E = elections();
  if (!E) return <PageHead kicker="Elections" title="2026 general election" dek="Results are not available in this build." />;
  const races = E.races.filter((r: any) => verified(r.claim));
  const by = (s: string) => races.filter((r: any) => r.status === s);
  const states = Object.values(E.states as Record<string, any>).sort((a: any, b: any) => a.stateName.localeCompare(b.stateName));
  const nc = E.not_covered;
  const offices = ["U.S. Senate", "Governor", "U.S. House"];
  return (
    <div>
      <PageHead kicker="Elections · November 3, 2026" title="2026 general election results" dek="Winners shown here come only from official state election office results. Unless a state has certified its results, every winner is labeled “Projected — uncertified” with the state office and the date we retrieved its results." />
      <section className="newspaper-card p-5 mb-6 grid gap-3 sm:grid-cols-4 text-center font-sans">
        <div><div className="font-display text-3xl font-black">{states.length}</div><div className="text-sm">states read from official sources</div></div>
        <div><div className="font-display text-3xl font-black">{races.length}</div><div className="text-sm">contests (House, Senate, governor)</div></div>
        <div><div className="font-display text-3xl font-black">{by("projected").length + by("certified").length}</div><div className="text-sm">winners shown ({by("certified").length} certified)</div></div>
        <div><div className="font-display text-3xl font-black">{by("uncalled").length}</div><div className="text-sm">not projected (too close or still counting)</div></div>
      </section>

      <section className="prose-news max-w-3xl mb-8">
        <h2>How a winner is shown</h2>
        <p>Politidex does not call races from news reports. A winner appears only when the official state results page itself shows one of the following:</p>
        <ul>
          <li><strong>Certified</strong> — the state marks the results official or certified.</li>
          <li><strong>Projected — uncertified</strong> — the state’s own results mark a winner, <em>or</em> every reporting unit the state lists is in and the leader is ahead of the runner-up by at least {E.rule.margin_pts} percentage points of all votes in the contest ({E.rule.late_margin_pts} points in states that count many ballots after election night: {E.rule.late_count_states.join(", ")}). Where state law requires a majority (runoff or ranked-choice: {E.rule.majority_states.join(", ")}), the leader must also have more than 50%.</li>
        </ul>
        <p>Everything else is listed as <strong>not projected</strong>, with the reason. Uncontested candidates who do not appear on the ballot are not shown. District numbers refer to the 2026 maps; several states redrew districts, so “currently held by” names the member who represents the district with that number today, whose boundaries may differ. Vote counts are re-checked against the state source before every build and change until certification. See the <Link className="link" href="/methodology#elections-2026">methodology</Link>.</p>
      </section>

      <h2 className="font-display text-3xl font-bold mb-3">New members-elect and governors</h2>
      <p className="mb-3 text-[var(--color-muted)]">Projected or certified winners who are not current members of Congress. Governors are listed with every projected winner; Politidex does not yet track sitting governors, so incumbency is not shown for them.</p>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 mb-10">
        {E.elect.filter((e: any) => verified(e.claim)).map((e: any) => (
          <li key={e.slug} className="newspaper-card p-3 min-w-0">
            <Link className="link font-semibold" href={`/elect/${e.slug}`}>{e.name}</Link>
            <div className="text-sm">{e.office}{e.office === "U.S. House" ? ` · ${e.state}-${e.district || "AL"}` : ` · ${e.state}`} · {e.party}</div>
            <div className="text-xs text-[var(--color-muted)]">{e.label}</div>
          </li>
        ))}
      </ul>

      {states.map((s: any) => {
        const rs = races.filter((r: any) => r.state === s.state).sort((a: any, b: any) => offices.indexOf(a.office) - offices.indexOf(b.office) || a.district - b.district);
        if (!rs.length) return null;
        return (
          <section key={s.state} id={s.state.toLowerCase()} className="mb-10">
            <h2 className="font-display text-3xl font-bold border-b-2 border-[var(--color-ink)] mb-2">{s.stateName}</h2>
            <p className="text-sm text-[var(--color-muted)] mb-3">Source: <a className="link" href={s.page} rel="noopener noreferrer">{s.source_name}</a> · retrieved {s.retrieved_at.slice(0, 16).replace("T", " ")} UTC</p>
            <div className="grid gap-4 lg:grid-cols-2">
              {rs.map((r: any) => (
                <article key={r.id} id={r.id} className="newspaper-card p-4 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 justify-between">
                    <h3 className="font-display text-xl font-bold">{raceTitle(r)}</h3>
                    {statusBadge(r)}
                  </div>
                  {r.winner ? (
                    <p className="mt-1">
                      <strong>{r.winner.slug ? <Link className="link" href={r.winner.reelected || r.winner.current_member ? `/p/${r.winner.slug}` : `/elect/${r.winner.slug}`}>{r.winner.name}</Link> : r.winner.name}</strong>
                      {" "}({r.winner.party}) — <Fact claim={r.claim}>{fmtInt(r.winner.votes)} votes</Fact>
                      {r.winner.reelected ? " · current officeholder" : r.winner.current_member ? " · current member of Congress" : ""}
                      <span className="block text-xs text-[var(--color-muted)]">{r.winner.label}</span>
                    </p>
                  ) : (
                    <p className="mt-1 text-sm">Not projected: {r.note}.</p>
                  )}
                  {r.incumbent && verified(r.incumbent.claim) && (
                    <p className="text-sm mt-1">Seat{r.office === "U.S. House" ? " number" : ""} currently held by <Fact claim={r.incumbent.claim}><Link className="link" href={`/p/${r.incumbent.slug}`}>{r.incumbent.name}</Link></Fact>{r.seat_class ? ` (${r.seat_class})` : ""}.</p>
                  )}
                  <details className="mt-2"><summary className="cursor-pointer text-sm font-semibold">Full official tally</summary><RaceTable r={r} /></details>
                </article>
              ))}
            </div>
          </section>
        );
      })}

      <section className="prose-news max-w-3xl">
        <h2 id="not-covered">States not included yet</h2>
        <p>We only publish results we can read from the state’s own election office and re-check automatically. These states are not included in this build:</p>
        <h3>Official site blocked automated reading</h3>
        <ul>{Object.entries(nc.blocked).map(([k, v]: any) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>
        <h3>Official statewide results not located or not yet published</h3>
        <ul>{Object.entries(nc.not_located).map(([k, v]: any) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>
        <h3>Not yet attempted</h3>
        <p>{nc.not_attempted.join(", ")}.</p>
      </section>
    </div>
  );
}
