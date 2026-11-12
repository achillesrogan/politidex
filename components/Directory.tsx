"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
type P = { slug: string; name: string; role: string; party: string | null; state: string | null; district: number | null; chamber: string };
export default function Directory({ people }: { people: P[] }) {
  const [q, setQ] = useState(""); const [ch, setCh] = useState("all"); const [party, setParty] = useState("all"); const [st, setSt] = useState("all");
  const states = useMemo(() => Array.from(new Set(people.map((p) => p.state).filter(Boolean))).sort() as string[], [people]);
  const parties = useMemo(() => Array.from(new Set(people.map((p) => p.party).filter(Boolean))).sort() as string[], [people]);
  const list = people.filter((p) =>
    (!q || p.name.toLowerCase().includes(q.toLowerCase())) && (ch === "all" || p.chamber === ch) && (party === "all" || p.party === party) && (st === "all" || p.state === st));
  const sel = "border border-[var(--color-rule)] bg-white px-2 py-2 font-sans text-sm w-full";
  return (
    <div>
      <div className="grid gap-2 grid-cols-2 md:grid-cols-4 mb-4" role="search">
        <label className="col-span-2 md:col-span-1"><span className="sr-only">Search by name</span>
          <input className={sel} placeholder="Search by name…" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <label><span className="sr-only">Branch</span><select className={sel} value={ch} onChange={(e) => setCh(e.target.value)}>
          <option value="all">All branches</option><option value="senate">Senate</option><option value="house">House</option><option value="executive">Executive</option></select></label>
        <label><span className="sr-only">Party</span><select className={sel} value={party} onChange={(e) => setParty(e.target.value)}>
          <option value="all">All parties</option>{parties.map((p) => <option key={p}>{p}</option>)}</select></label>
        <label className="col-span-2 md:col-span-1"><span className="sr-only">State</span><select className={sel} value={st} onChange={(e) => setSt(e.target.value)}>
          <option value="all">All states</option>{states.map((s) => <option key={s}>{s}</option>)}</select></label>
      </div>
      <p className="font-sans text-sm text-[var(--color-muted)] mb-3">{list.length} of {people.length} profiles</p>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {list.map((p) => (
          <li key={p.slug}>
            <Link href={`/p/${p.slug}`} className="block newspaper-card p-4 hover:shadow-md transition-shadow h-full">
              <div className="font-display text-lg font-bold leading-snug">{p.name}</div>
              <div className="text-[var(--color-muted)]">{p.role}{p.state ? ` · ${p.state}${p.chamber === "house" && p.district != null ? (p.district === 0 ? "-AL" : `-${p.district}`) : ""}` : ""}{p.party ? ` · ${p.party}` : ""}</div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
