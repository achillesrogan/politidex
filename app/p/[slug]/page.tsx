import { notFound } from "next/navigation";
import Link from "next/link";
import Fact from "@/components/Fact";
import { RecordModule, AnalysisModule } from "@/components/Module";
import { people, profile, verified, fmtUSD, claims, approvedSummary } from "@/lib/data";

export const dynamicParams = false;
export function generateStaticParams() {
  const ps = people().map((p) => ({ slug: p.slug }));
  return ps.length ? ps : [{ slug: "_none" }];
}
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const pr = profile(slug);
  return { title: pr ? pr.person.name : "Profile", alternates: { canonical: `/p/${slug}` } };
}
const pct = (a: number, b: number) => (b ? `${((a / b) * 100).toFixed(1)}%` : "—");

export default async function ProfilePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const pr = profile(slug);
  if (!pr || !verified(pr.facts?.[0]?.claim)) notFound();
  const p = pr.person;
  const an = pr.analysis;
  const C = claims();
  const used: string[] = [];
  const track = (id?: string) => { if (id && verified(id)) used.push(id); return id; };
  return (
    <article>
      <header className="mb-6 border-b-4 border-double border-[var(--color-ink)] pb-4">
        <div className="tag text-[var(--color-muted)]">{p.kind === "executive" ? "Executive branch" : p.chamber === "senate" ? "U.S. Senate" : "U.S. House of Representatives"}</div>
        <h1 className="font-display text-4xl sm:text-5xl font-black masthead-shadow mt-1">{p.name}</h1>
        <p className="text-xl text-[var(--color-muted)] mt-1">{p.role}{p.stateName ? ` · ${p.stateName}` : ""}{p.party ? ` · ${p.party}` : ""}</p>
      </header>

      {(() => { const sm = approvedSummary(slug); return sm && (
        <section className="newspaper-card p-5 mb-6">
          <div className="tag text-[var(--color-record)]">Summary · editor-reviewed restatement of verified records</div>
          <p className="mt-2 text-lg">{sm.sentences.map((s, i) => <Fact key={i} claim={track(s.ids[0])}>{s.text} </Fact>)}</p>
        </section>); })()}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 grid gap-6 content-start min-w-0">
          <RecordModule title="Office">
            <dl className="grid gap-2 sm:grid-cols-[12rem_1fr]">
              {pr.facts.map((f: any) => verified(f.claim) && (
                <div key={f.label} className="contents">
                  <dt className="font-semibold">{f.label}</dt>
                  <dd className="min-w-0 break-words"><Fact claim={track(f.claim)}>{f.link ? <a className="link" href={f.link} rel="noopener noreferrer">{f.value}</a> : f.value}</Fact></dd>
                </div>
              ))}
            </dl>
          </RecordModule>

          {pr.committees?.some((c: any) => verified(c.claim)) && (
            <RecordModule title="Committee assignments">
              <ul className="grid gap-1">
                {pr.committees.map((c: any) => <Fact key={c.code} as="li" claim={track(c.claim)}>{c.name}{c.role && c.role !== "Member" ? ` — ${c.role}` : ""}</Fact>)}
              </ul>
            </RecordModule>
          )}

          {pr.recent_votes?.some((v: any) => verified(v.claim)) && (
            <RecordModule title="Most recent roll-call votes">
              <div className="overflow-x-auto -mx-1">
                <table className="w-full text-left text-[0.98rem]">
                  <thead><tr className="border-b border-[var(--color-rule)] font-sans text-xs uppercase tracking-wide"><th className="py-2 pr-3">Date</th><th className="pr-3">Question</th><th className="pr-3">Vote</th><th>Result</th></tr></thead>
                  <tbody>
                    {pr.recent_votes.filter((v: any) => verified(v.claim)).map((v: any) => (
                      <tr key={v.claim} className="border-b border-[var(--color-rule)]/60 align-top">
                        <td className="py-2 pr-3 whitespace-nowrap">{v.date}</td>
                        <td className="pr-3 min-w-[12rem]">{v.question}{v.legis ? ` — ${v.legis}` : ""}</td>
                        <Fact as="td" className="pr-3 font-semibold whitespace-nowrap" claim={track(v.claim)}>{v.position}</Fact>
                        <td>{v.result}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </RecordModule>
          )}

          {pr.bills?.some((b: any) => verified(b.claim)) && (
            <RecordModule title="Recently sponsored legislation (119th Congress)">
              <ul className="grid gap-2">
                {pr.bills.map((b: any) => <Fact key={b.claim} as="li" claim={track(b.claim)}><a className="link" href={b.url} rel="noopener noreferrer">{b.label}</a> — {b.title} <span className="text-[var(--color-muted)]">({b.date})</span></Fact>)}
              </ul>
            </RecordModule>
          )}

          {an && (
            <AnalysisModule title="Politi-Matrix v1: participation and party alignment">
              <dl className="grid gap-3 sm:grid-cols-2">
                {verified(an.missed.claim) && <div><dt className="tag">Missed votes</dt><dd className="font-display text-3xl font-black"><Fact claim={track(an.missed.claim)}>{pct(an.missed.count, an.total)}</Fact></dd><dd className="text-sm text-[var(--color-muted)]">{an.missed.count} of {an.total} roll calls recorded “Not Voting”</dd></div>}
                {verified(an.present.claim) && <div><dt className="tag">“Present” votes</dt><dd className="font-display text-3xl font-black"><Fact claim={track(an.present.claim)}>{an.present.count}</Fact></dd></div>}
                {an.party_line && verified(an.party_line.claim) && <div><dt className="tag">Votes with own party’s majority</dt><dd className="font-display text-3xl font-black"><Fact claim={track(an.party_line.claim)}>{pct(an.party_line.with, an.party_line.of)}</Fact></dd><dd className="text-sm text-[var(--color-muted)]">{an.party_line.with} of {an.party_line.of} Yea/Nay votes</dd></div>}
                {verified(an.divergence.claim) && <div><dt className="tag">Procedural vs. final-passage splits</dt><dd className="font-display text-3xl font-black"><Fact claim={track(an.divergence.claim)}>{an.divergence.count}</Fact></dd><dd className="text-sm text-[var(--color-muted)]">of {an.divergence.of} measures with both vote types{an.divergence.measures?.length ? `: ${an.divergence.measures.join(", ")}` : ""}</dd></div>}
              </dl>
              {(p.role === "Delegate" || p.role === "Resident Commissioner") && <p className="mt-3 text-sm font-sans text-[var(--color-muted)]">Note: delegates and the resident commissioner may vote on the House floor only in limited circumstances, so these figures are not comparable with voting members’.</p>}
              <p className="mt-3 text-sm font-sans text-[var(--color-muted)]">Stated positions (“the mask”) will be compared only where a sourced quote or official statement exists. None are shown yet.</p>
            </AnalysisModule>
          )}
        </div>

        <aside className="grid gap-6 content-start min-w-0">
          {pr.money?.some((m: any) => verified(m.claim)) && (
            <RecordModule title="Campaign finance, 2025–26">
              <dl className="grid gap-2">
                {pr.money.map((m: any) => verified(m.claim) && (
                  <div key={m.label}><dt className="text-sm text-[var(--color-muted)]">{m.label}</dt><dd className="font-semibold"><Fact claim={track(m.claim)}>{fmtUSD(m.value)}</Fact></dd></div>
                ))}
              </dl>
              <p className="mt-3 text-sm text-[var(--color-muted)]">Committee-level totals reported to the FEC{pr.money_meta?.coverage_end ? `, through ${pr.money_meta.coverage_end.slice(0, 10)}` : ""}. Individual contributors are not shown.</p>
            </RecordModule>
          )}

          {pr.pacs?.some((x: any) => verified(x.claim)) && (
            <RecordModule title="Political committees giving the most">
              <ul className="grid gap-2">
                {pr.pacs.map((x: any) => <Fact key={x.committee_id} as="li" claim={track(x.claim)}><a className="link" href={x.url} rel="noopener noreferrer">{x.name}</a> — {fmtUSD(x.largest)} <span className="text-[var(--color-muted)] text-sm">({x.count} {x.count === 1 ? "payment" : "payments"})</span></Fact>)}
              </ul>
              <p className="mt-3 text-sm text-[var(--color-muted)]">Totals the paying committees reported to the FEC as disbursements to this member’s principal campaign committee in 2025–26. Includes PACs, party committees, and joint fundraising committees. Individual donors are never shown.</p>
            </RecordModule>
          )}

          {pr.cosponsors?.some((c: any) => verified(c.claim)) && (
            <RecordModule title="Connections: cosponsorship">
              <p className="text-sm text-[var(--color-muted)] mb-2">Members whose bills {p.name} cosponsored most often (119th Congress).</p>
              <ul className="grid gap-3">
                {pr.cosponsors.map((c: any) => verified(c.claim) && (
                  <li key={c.partner}>
                    <Fact claim={track(c.claim)}>{c.partner_slug ? <Link className="link" href={`/p/${c.partner_slug}`}>{c.partner_name}</Link> : c.partner_name} — {c.count} bills</Fact>
                    <ul className="text-sm mt-1 pl-3 border-l border-[var(--color-rule)]">
                      {c.examples.filter((e: any) => verified(e.claim) && verified(e.sponsor_claim)).map((e: any) => (
                        <Fact key={e.claim} as="li" claim={track(e.claim)}><a className="link" href={e.url} rel="noopener noreferrer">{e.label}</a> {e.title}</Fact>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </RecordModule>
          )}

          <section className="newspaper-card p-5 text-sm">
            <h2 className="tag mb-2">Sources on this page</h2>
            <p className="text-[var(--color-muted)]">{used.length} verified claims. Each <span className="cite">[source]</span> link opens the record; hover for the retrieval date and the exact value checked.</p>
            <p className="mt-2 text-[var(--color-muted)]">Official records can be amended or published late. Something wrong? <Link className="link" href="/corrections">Report a correction</Link>.</p>
          </section>
        </aside>
      </div>
    </article>
  );
}
