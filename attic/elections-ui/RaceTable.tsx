import Fact from "@/components/Fact";
import { verified, fmtInt } from "@/lib/data";

export function statusBadge(r: any) {
  if (r.status === "certified") return <span className="tag px-2 py-0.5 bg-[var(--color-record)] text-white">Certified</span>;
  if (r.status === "projected") return <span className="tag px-2 py-0.5 border border-[var(--color-ink)]">Projected — uncertified</span>;
  return <span className="tag px-2 py-0.5 border border-dashed border-[var(--color-muted)] text-[var(--color-muted)]">Not projected</span>;
}
export function raceTitle(r: any) {
  if (r.office === "U.S. House") return `U.S. House · ${r.stateName} ${r.district ? `District ${r.district}` : "at-large"}`;
  return `${r.office}${r.special ? " (special)" : ""} · ${r.stateName}`;
}
/** Full official tally for one contest. Renders only if the race claim passed live re-verification. */
export default function RaceTable({ r }: { r: any }) {
  if (!verified(r.claim)) return null;
  return (
    <div className="min-w-0 overflow-x-auto">
      <table className="w-full text-sm font-sans">
        <thead><tr className="text-left border-b border-[var(--color-ink)]"><th className="py-1 pr-2">Candidate (as listed by the state)</th><th className="py-1 pr-2">Party</th><th className="py-1 pr-2 text-right">Votes</th><th className="py-1 text-right">Share</th></tr></thead>
        <tbody>
          {r.candidates.map((c: any, i: number) => (
            <tr key={i} className={"border-b border-[var(--color-rule,#ddd)] " + (r.winner && r.winner.ballot_name === c.name ? "font-bold" : "")}>
              <td className="py-1 pr-2 break-words">{c.name}</td>
              <td className="py-1 pr-2">{c.party}</td>
              <td className="py-1 pr-2 text-right"><Fact claim={r.claim}>{fmtInt(c.votes)}</Fact></td>
              <td className="py-1 text-right">{c.pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-[var(--color-muted)] mt-1">Reporting: {r.reporting}. Share is each candidate’s votes divided by all votes listed for the contest. Source: <a className="link" href={r.source_url} rel="noopener noreferrer">{r.source_name}</a>, retrieved {r.retrieved_at.slice(0, 10)}.</p>
    </div>
  );
}
