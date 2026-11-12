import Link from "next/link";
import PageHead from "@/components/PageHead";
import ComingSoon from "@/components/ComingSoon";
import Fact from "@/components/Fact";
import { connections, people, verified, fmtUSD } from "@/lib/data";
export const metadata = { title: "Connections" };
export default function ConnectionsPage() {
  const ps = people();
  if (!ps.length) return <ComingSoon title="Connections"><p>The earlier “influence network” demo used hypothetical data and has been removed. Version 1 connections are built only from public records — shared committees, bill cosponsorship, and committee-level campaign contributions — and every connection links to its evidence.</p></ComingSoon>;
  const by = new Map(ps.map((p) => [p.bioguide || p.slug, p]));
  const c = connections();
  const pairs = c.cosponsor_pairs.filter((x: any) => verified(x.claim)).slice(0, 40);
  const pacs = c.pacs.map((x: any) => ({ ...x, members: x.members.filter((m: any) => verified(m.claim)) })).filter((x: any) => x.members.length > 1);
  const name = (id: string) => { const p = by.get(id); return p ? <Link className="link" href={`/p/${p.slug}`}>{p.name}</Link> : id; };
  return (
    <div>
      <PageHead kicker="Connections v1" title="Documented connections" dek="Relationships that appear in public records. A connection documents a fact; it does not by itself imply coordination, influence, or wrongdoing." />
      <section className="newspaper-card p-5 sm:p-6">
        <div className="tag text-[var(--color-record)]">Record</div>
        <h2 className="font-display text-2xl font-bold mt-1 mb-3">Most frequent cosponsorship relationships</h2>
        <p className="text-[var(--color-muted)] mb-3">Pairs where one member cosponsored the other’s bills most often in the 119th Congress (Congress.gov).</p>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr className="border-b border-[var(--color-rule)] font-sans text-xs uppercase"><th className="py-2 pr-3">Cosponsor</th><th className="pr-3">Sponsor</th><th>Bills</th></tr></thead>
            <tbody>{pairs.map((x: any) => (
              <tr key={x.claim} className="border-b border-[var(--color-rule)]/60"><td className="py-2 pr-3">{name(x.from)}</td><td className="pr-3">{name(x.to)}</td><Fact as="td" claim={x.claim}>{x.count}</Fact></tr>
            ))}</tbody>
          </table>
        </div>
      </section>
      <section className="newspaper-card p-5 sm:p-6 mt-6">
        <div className="tag text-[var(--color-record)]">Record</div>
        <h2 className="font-display text-2xl font-bold mt-1 mb-3">Political committees that appear among the most members’ top givers</h2>
        <p className="text-[var(--color-muted)] mb-3">Built from each member’s five largest committee givers in 2025–26, as reported to the FEC by the paying committees (Schedule B). Committee-level data only.</p>
        <div className="grid gap-4 md:grid-cols-2">
          {pacs.slice(0, 16).map((x: any) => (
            <div key={x.committee_id} className="border border-[var(--color-rule)] p-4 bg-white/60">
              <h3 className="font-display text-lg font-bold"><a className="link" href={`https://www.fec.gov/data/committee/${x.committee_id}/`} rel="noopener noreferrer">{x.name}</a></h3>
              <p className="text-sm text-[var(--color-muted)]">{x.members.length} members</p>
              <ul className="text-sm mt-2 grid gap-1">{x.members.slice(0, 8).map((m: any) => <Fact key={m.claim} as="li" claim={m.claim}>{name(m.who)} — {fmtUSD(m.amount)}</Fact>)}</ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
