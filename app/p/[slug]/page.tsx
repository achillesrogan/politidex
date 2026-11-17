import CareerRecord from "@/components/CareerRecord";
import CommitteeInfo from "@/components/CommitteeInfo";
import SourceCoverage from "@/components/SourceCoverage";
import EntityLink from "@/components/EntityLink";
import PageTrust from "@/components/PageTrust";
import { notFound } from "next/navigation";
import Link from "next/link";
import Fact from "@/components/Fact";
import { RecordModule, AnalysisModule } from "@/components/Module";
import { people, profile, verified, fmtUSD, claims, approvedSummary, committeeHistory } from "@/lib/data";
import { approvedCommitteeFacts, committeeSite } from "@/lib/committees";
import { entityRecord } from "@/lib/entity-registry.mjs";
import { ldaClaimDates, profileAsOf } from "@/lib/page-as-of.mjs";
import { publicSourceHref, renderedSourceHref } from "@/lib/source-href.mjs";
import ConnectionsPanel from "@/components/ConnectionsPanel";
import { careerFor, memberFirstYear } from "@/lib/career-record.mjs";
import { fmtDate } from "@/lib/dates";

function billId(url?: string | null) {
  const match = String(url || "").match(/\/(bill\/\d+th-congress\/[a-z-]+\/\d+)/i);
  return match ? match[1] : null;
}

function namedEntity(kind: string, name: string | null | undefined, officialId: string | null | undefined, claimId: string | null | undefined, href?: string | null, sourceUrl?: string | null) {
  const claim = verified(claimId);
  if (!claim || !name) return null;
  return entityRecord({
    kind,
    name,
    official_id: officialId,
    source_name: claim.source_name,
    source_url: sourceUrl || renderedSourceHref(claim) || claim.source_url,
    retrieved_at: claim.retrieved_at,
    href,
    amended: claim.check?.amended === true,
    review_status: typeof claim.check?.review_status === "string" ? claim.check.review_status : undefined,
  });
}

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

function pageAsOf(pr: any) {
  const claimDates = [
    ...(pr.facts || []).map((f: { claim?: string }) => verified(f.claim)?.retrieved_at),
    ...(pr.bills || []).map((b: { claim?: string }) => verified(b.claim)?.retrieved_at),
    ...(pr.money || []).map((m: { claim?: string }) => verified(m.claim)?.retrieved_at),
    ...(pr.pacs || []).map((x: { claim?: string }) => verified(x.claim)?.retrieved_at),
    ...(pr.committees || []).map((c: { claim?: string }) => verified(c.claim)?.retrieved_at),
    ...ldaClaimDates(pr.ties, (id) => verified(id)?.retrieved_at),
  ];
  const sites: Record<string, NonNullable<ReturnType<typeof committeeSite>>> = {};
  for (const committee of pr.committees || []) {
    const site = committeeSite(committee?.code);
    if (site && committee.code) sites[committee.code] = site;
  }
  return profileAsOf(claimDates, (pr.committees || []).map((committee: { code?: string }) => committee?.code), sites);
}

export default async function ProfilePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const pr = profile(slug);
  if (!pr || !verified(pr.facts?.[0]?.claim)) notFound();
  const p = pr.person;
  const bioguide = people().find((person) => person.slug === slug)?.bioguide || null;
  const career = bioguide ? careerFor(bioguide) : null;
  const firstYear = memberFirstYear(bioguide);
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
        <div className="mt-3">
          <PageTrust retrieved={pageAsOf(pr)} />
        </div>
        <SourceCoverage firstYear={firstYear} />
      </header>

      {career && <CareerRecord career={career} />}
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
                  <dd className="min-w-0 break-words"><Fact claim={track(f.claim)}>{f.link && publicSourceHref(f.link) ? <a className="link" href={publicSourceHref(f.link) || undefined} rel="noopener noreferrer">{f.value}</a> : f.value}</Fact></dd>
                </div>
              ))}
            </dl>
          </RecordModule>

          {pr.committees?.some((c: any) => c?.name && verified(c.claim)) && (
            <RecordModule title="Committee assignments">
              <ul className="grid gap-1">
                {pr.committees.filter((c: any) => c?.name && verified(c.claim)).map((c: any) => {
                  const claim = verified(c.claim);
                  if (!claim) return null;
                  track(c.claim);
                  const meta = committeeHistory(c.code);
                  const hist = (c.history_claims || []).map((id: string) => {
                    const history = verified(id);
                    if (!history) return null;
                    track(id);
                    const fact = meta?.facts?.find((x: any) => x.claim === id);
                    return {
                      id: history.id,
                      label: fact?.label || "Official record",
                      text: String(history.text),
                      excerpt: history.excerpt,
                      source_name: history.source_name,
                      source_url: history.source_url,
                      retrieved_at: history.retrieved_at,
                    };
                  }).filter(Boolean);
                  const site = committeeSite(c.code);
                  const summary = approvedCommitteeFacts(c.code).map((f) => ({
                    label: f.kind === "created" ? "Established" : f.kind === "purpose" ? "Jurisdiction" : f.kind === "roster" ? "Roster" : "Official record",
                    text: f.text,
                    excerpt: f.excerpt,
                    source_name: f.source_name,
                    source_url: f.source_url,
                    retrieved_at: f.retrieved_at,
                  }));
                  return (
                    <li key={c.code || c.claim}>
                      <CommitteeInfo
                        name={c.name}
                        role={c.role}
                        officialId={c.code}
                        claimId={claim.id}
                        website={site?.website}
                        membershipUrl={claim.source_url}
                        facts={hist}
                        summary={summary}
                      />
                    </li>
                  );
                })}
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
                {pr.bills.map((b: any) => <Fact key={b.claim} as="li" claim={track(b.claim)}><EntityLink entity={namedEntity("bill", b.label, billId(b.url), b.claim, null, b.url)}>{b.label}</EntityLink> — {b.title} <span className="text-[var(--color-muted)]">({b.date})</span></Fact>)}
              </ul>
            </RecordModule>
          )}

          {pr.ties && (
            <ConnectionsPanel ties={pr.ties} personName={p.name} cosponsors={pr.cosponsors} />
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
              <p className="mt-3 text-sm text-[var(--color-muted)]">Committee-level totals reported to the FEC{pr.money_meta?.coverage_end ? `, through ${fmtDate(pr.money_meta.coverage_end)}` : ""}. Individual contributors are not shown.</p>
            </RecordModule>
          )}

          {!pr.ties?.money?.rows?.length && pr.pacs?.some((x: any) => verified(x.claim)) && (
            <RecordModule title="Political committees giving the most">
              <ul className="grid gap-2">
                {pr.pacs.map((x: any) => <Fact key={x.committee_id} as="li" claim={track(x.claim)}><EntityLink entity={namedEntity("pac", x.name, x.committee_id, x.claim, x.org_slug ? `/org/${x.org_slug}` : null, x.url)}>{x.name}</EntityLink> — {fmtUSD(x.largest)} <span className="text-[var(--color-muted)] text-sm">({x.count} {x.count === 1 ? "payment" : "payments"})</span></Fact>)}
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
                    <Fact claim={track(c.claim)}><EntityLink entity={namedEntity("member", c.partner_name, c.partner, c.claim, c.partner_slug ? `/p/${c.partner_slug}` : null)}>{c.partner_name}</EntityLink> — {c.count} bills</Fact>
                    <ul className="text-sm mt-1 pl-3 border-l border-[var(--color-rule)]">
                      {c.examples.filter((e: any) => verified(e.claim) && verified(e.sponsor_claim)).map((e: any) => (
                        <Fact key={e.claim} as="li" claim={track(e.claim)}><EntityLink entity={namedEntity("bill", e.label, billId(e.url), e.claim, null, e.url)}>{e.label}</EntityLink> {e.title}</Fact>
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
