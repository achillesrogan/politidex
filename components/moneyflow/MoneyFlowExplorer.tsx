"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { fmtDate } from "@/lib/dates";
import {
  DEFAULT_DEPTH,
  FUNGIBILITY_NOTE,
  INDIVIDUALS_NOTE,
  MAX_DEPTH,
  OTHER_NOTE,
  applyFilters,
  buildVisible,
  createNestedList,
  formatMoney,
  dollarsToCents,
  layoutTree,
  linkPath,
  presentCommittees,
  purposeCodes,
  shardUrl,
  strokeWidth,
} from "@/lib/moneyflow-ui.mjs";

type Source = {
  source_name: string;
  source_url: string;
  retrieved_at?: string;
  excerpt: string;
  text?: string;
  check?: { image_number?: string | null; sample_image_number?: string | null; sub_id?: string | null; sample_sub_id?: string | null; sample_filing_id?: string | null; filing_id?: string | null };
};
type Committee = { committee_id: string; name: string; party?: string | null; official_total_out: string; coverage_end?: string | null; selection_rule?: string };
type Card = { source: Source; title: string; bucketNote: string | null } | null;

const KINDS = ["any", "party", "committee", "candidate_committee", "business", "residual"];

function filingBits(source: Source) {
  const check = source.check || {};
  const image = check.sample_image_number || check.image_number;
  const sub = check.sample_sub_id || check.sub_id;
  const filing = check.sample_filing_id || check.filing_id;
  return [
    image ? `Image ${image}` : "",
    sub ? `Record number ${sub}` : "",
    filing ? `Filing ${filing}` : "",
  ].filter(Boolean);
}

export default function MoneyFlowExplorer({ note, cycle }: { note: string; cycle: number }) {
  const fungibility = note || FUNGIBILITY_NOTE;
  const [committees, setCommittees] = useState<Committee[]>([]);
  const [shards, setShards] = useState<Record<string, any>>({});
  const [active, setActive] = useState("");
  const [expanded, setExpanded] = useState<string[]>([]);
  const [minDollars, setMinDollars] = useState("");
  const [kind, setKind] = useState("any");
  const [purpose, setPurpose] = useState("any");
  const [card, setCard] = useState<Card>(null);
  const [error, setError] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);
  const loaded = useMemo(() => new Map(Object.entries(shards)), [shards]);
  const shardIds = useMemo(() => new Set(committees.map((c) => c.committee_id)), [committees]);
  const ordered = useMemo(() => presentCommittees(committees), [committees]);

  useEffect(() => {
    let cancel = false;
    fetch("/api/moneyflow")
      .then((r) => r.json())
      .then((body) => {
        if (!cancel) setCommittees(body.committees || []);
      })
      .catch(() => {
        if (!cancel) setError("The committee list could not be loaded.");
      });
    return () => {
      cancel = true;
    };
  }, []);

  async function openCommittee(id: string) {
    setActive(id);
    setExpanded([]);
    setPurpose("any");
    setError("");
    if (shards[id]) return;
    const url = shardUrl(id);
    if (!url) return;
    const res = await fetch(url);
    if (!res.ok) {
      setError("This committee's reported outflows are not in the pilot set.");
      return;
    }
    const shard = await res.json();
    setShards((prev) => ({ ...prev, [id]: shard }));
  }

  async function toggle(row: any) {
    if (!row.expandable || !row.officialId) return;
    const open = expanded.includes(row.key);
    setExpanded(open ? expanded.filter((k) => k !== row.key) : expanded.concat(row.key));
    if (open || shards[row.officialId]) return;
    const url = shardUrl(row.officialId);
    if (!url) return;
    const res = await fetch(url);
    if (!res.ok) return;
    const shard = await res.json();
    setShards((prev) => ({ ...prev, [row.officialId]: shard }));
  }

  function showRecord(source: Source, title: string, bucketNote: string | null) {
    if (!source?.source_url || !source.excerpt) return;
    setCard({ source, title, bucketNote });
  }

  useEffect(() => {
    if (card && dialogRef.current && !dialogRef.current.open) dialogRef.current.showModal();
  }, [card]);

  const shard = active ? shards[active] : null;
  const filters = { minCents: dollarsToCents(minDollars), kind, purpose, cycle };
  const view = shard ? buildVisible(shard, { filters, expanded: new Set(expanded), loaded, shardIds }) : null;
  const layout = view ? layoutTree(view) : null;
  const codes = shard ? purposeCodes(shard.children || []) : [];
  const shown = view?.children?.length || 0;
  const available = shard
    ? applyFilters(shard.children || [], filters).filter((ch: any) => ch?.node?.source?.source_url && ch?.edge?.source?.source_url).length
    : 0;

  return (
    <div className="moneyflow">
      <aside className="moneyflow-note" role="note">{fungibility}</aside>
      <p className="moneyflow-depth">
        The first view is {DEFAULT_DEPTH} levels: the committee and its reported outflows. A recipient that has its own record can be opened, up to {MAX_DEPTH} levels. Businesses stop at Spent. Residual buckets stop at the bucket name.
      </p>
      <form className="moneyflow-filters" onSubmit={(e) => e.preventDefault()}>
        <label>Cycle
          <select value={String(cycle)} onChange={() => undefined} aria-label="Cycle">
            <option value={String(cycle)}>{cycle}</option>
          </select>
        </label>
        <label>Minimum amount
          <input inputMode="decimal" value={minDollars} placeholder="0" aria-label="Minimum amount" onChange={(e) => setMinDollars(e.target.value)} />
        </label>
        <label>Kind
          <select value={kind} aria-label="Kind" onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => <option key={k} value={k}>{k === "any" ? "Any kind" : k.replaceAll("_", " ")}</option>)}
          </select>
        </label>
        <label>Purpose code
          <select value={purpose} aria-label="Purpose code" onChange={(e) => setPurpose(e.target.value)}>
            <option value="any">Any purpose code</option>
            {codes.map((code: string) => <option key={code} value={code}>{code}</option>)}
          </select>
        </label>
      </form>
      <p className="moneyflow-filter-note">Filters hide rows at each level. Hidden rows are not a new total.</p>

      <div className="moneyflow-starts" role="group" aria-label="Starting committees">
        {ordered.map((c: Committee & { controlClass: string }) => (
          <button
            key={c.committee_id}
            type="button"
            className={c.controlClass + (active === c.committee_id ? " is-active" : "")}
            aria-pressed={active === c.committee_id}
            onClick={() => openCommittee(c.committee_id)}
          >
            <span className="moneyflow-start-name">{c.name}</span>
            <span className="moneyflow-start-meta">{c.party ? `Party code ${c.party}` : "No party code"} · {formatMoney(c.official_total_out)}</span>
          </button>
        ))}
      </div>
      {error ? <p className="moneyflow-error" role="status">{error}</p> : null}

      {view && layout ? (
        <section className="moneyflow-stage" aria-label="Reported money out">
          <p className="moneyflow-count">Showing {shown} of {available} reported outflows at this level. Official total out {formatMoney(view.amount)}.</p>
          <div className="moneyflow-legend">
            <p>{INDIVIDUALS_NOTE}</p>
            <p>{OTHER_NOTE}</p>
            <p>Line width follows the reported amount. The amount is also written as text.</p>
          </div>
          <div className="moneyflow-graph" role="group" aria-label="Reported money out tree">
            <svg width={layout.width} height={layout.height} className="moneyflow-svg">
              {layout.links.map((link: any) => (
                <path key={link.key} d={linkPath(link)} className="moneyflow-stroke" strokeWidth={strokeWidth(link.cents, layout.maxCents)} fill="none" />
              ))}
              {layout.nodes.map((node: any) => (
                <foreignObject key={node.key} x={node.x} y={node.y} width={248} height={72}>
                  <div className="moneyflow-node">
                    <button type="button" className="moneyflow-node-btn" aria-expanded={node.data.expandable ? (node.data.expanded ? "true" : "false") : undefined} onClick={() => (node.data.expandable ? toggle(node.data) : showRecord(node.data.nodeSource, node.data.name, node.data.bucketNote))}>
                      <span className="moneyflow-node-name">{node.data.name}</span>
                      <span className="moneyflow-node-amt">{formatMoney(node.data.amount)}{node.data.edgeKind && node.data.edgeKind.toLowerCase() !== String(node.data.terminalLabel || "").toLowerCase() ? ` · ${node.data.edgeKind}` : ""}{node.data.terminalLabel ? ` · ${node.data.terminalLabel}` : ""}</span>
                    </button>
                    <button type="button" className="moneyflow-record" onClick={() => showRecord(node.data.edgeSource || node.data.nodeSource, node.data.edgeKind || node.data.name, node.data.bucketNote)}>Record</button>
                  </div>
                </foreignObject>
              ))}
            </svg>
          </div>
          {createNestedList(view, { onToggle: toggle, onRecord: showRecord })}
        </section>
      ) : null}

      <dialog
        ref={dialogRef}
        className="moneyflow-dialog newspaper-card"
        onClick={(e) => {
          if (e.target === dialogRef.current) dialogRef.current?.close();
        }}
        onClose={() => setCard(null)}
      >
        {card ? (
          <div>
            <p className="tag text-[var(--color-record)]">Official record</p>
            <h3 className="font-display text-xl font-bold mt-1">{card.title}</h3>
            <p className="moneyflow-note mt-3" role="note">{fungibility}</p>
            {card.bucketNote ? <p className="mt-3">{card.bucketNote}</p> : null}
            <p className="mt-3">{card.source.text || card.source.excerpt}</p>
            <ul className="mt-3 text-sm text-[var(--color-muted)]">
              {filingBits(card.source).map((bit) => <li key={bit}>{bit}</li>)}
            </ul>
            <p className="mt-3 text-sm">Source: {card.source.source_name}{card.source.retrieved_at ? ` · retrieved ${fmtDate(card.source.retrieved_at)}` : ""}</p>
            <blockquote className="mt-2 text-sm border-l-2 border-[var(--color-rule)] pl-3">{card.source.excerpt}</blockquote>
            <p className="mt-2 text-sm"><a className="link" href={card.source.source_url} rel="noopener noreferrer">Open the cited source</a></p>
            <form method="dialog" className="mt-4"><button type="submit" className="moneyflow-text-btn">Close</button></form>
          </div>
        ) : null}
      </dialog>
    </div>
  );
}
