import Link from "next/link";
import PageHead from "@/components/PageHead";
import ComingSoon from "@/components/ComingSoon";
import Fact from "@/components/Fact";
import { people, profile, verified } from "@/lib/data";
export const metadata = { title: "Politi-Matrix" };
export default function Matrix() {
  const rows = people().filter((p) => p.kind === "congress").map((p) => ({ p, a: profile(p.slug)?.analysis })).filter((r) => r.a && verified(r.a.missed.claim));
  if (!rows.length) return <ComingSoon title="Politi-Matrix"><p>The Politi-Matrix compares how officials present themselves with what the record shows. Version 1 will use record data only: missed votes, party-line voting, and procedural-versus-final-passage splits, with a published method.</p></ComingSoon>;
  // Rankings include only full voting members (not delegates/resident commissioner) with at least 100 listed roll calls.
  const top = (ch: string) => rows.filter((r) => r.p.chamber === ch && (r.p.role === "Senator" || r.p.role === "Representative") && r.a.total >= 100).sort((x, y) => y.a.missed.rate - x.a.missed.rate).slice(0, 15);
  return (
    <div>
      <PageHead kicker="Analysis" title="Politi-Matrix v1" dek="The public “mask” versus the record. Version 1 measures only what the official record shows; stated positions will be added only with sourced quotes." />
      <div className="p-4 border border-dashed border-[var(--color-analysis)] bg-[#fdf6ec] mb-6 text-[0.98rem]">This page is <strong>Analysis</strong>: figures are computed from official roll-call records using the <Link className="link" href="/methodology#politi-matrix-version-1">published method</Link>. Absences can reflect illness, family leave, or official duties. Nothing here is an allegation of wrongdoing. Rankings include only voting members with at least 100 recorded roll calls; delegates and the resident commissioner, who vote only in limited circumstances, are excluded.</div>
      <div className="grid gap-6 lg:grid-cols-2">
        {["senate", "house"].map((ch) => (
          <section key={ch} className="newspaper-card p-5">
            <h2 className="font-display text-2xl font-bold mb-3">Highest missed-vote rates — {ch === "senate" ? "Senate" : "House"}</h2>
            <table className="w-full text-left">
              <thead><tr className="border-b border-[var(--color-rule)] font-sans text-xs uppercase"><th className="py-2">Member</th><th>Missed</th></tr></thead>
              <tbody>{top(ch).map(({ p, a }) => (
                <tr key={p.slug} className="border-b border-[var(--color-rule)]/60"><td className="py-2 pr-2"><Link className="link" href={`/p/${p.slug}`}>{p.name}</Link> <span className="text-sm text-[var(--color-muted)]">{p.state}</span></td>
                  <Fact as="td" className="whitespace-nowrap" claim={a.missed.claim}>{(a.missed.rate * 100).toFixed(1)}% ({a.missed.count}/{a.total})</Fact></tr>
              ))}</tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  );
}
