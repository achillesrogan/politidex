"use client";
import { useState } from "react";
import { fmtDate } from "@/lib/dates";
import RecordPopover from "@/components/RecordPopover";
import { publicSourceHref, renderedSourceHref } from "@/lib/source-href.mjs";

export type SourceLink = { label: string; href: string };
export type SourceCardInfo = {
  title: string;
  summary: string;
  excerpt: string;
  source_name: string;
  source_url: string;
  retrieved_at?: string;
  extra?: string[];
  links?: SourceLink[];
};

export default function SourceCard({ card, children }: { card: SourceCardInfo; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  const source = renderedSourceHref(card);
  return (
    <div className="conn-row">
      <div className="min-w-0 flex-1">{children}</div>
      <button
        type="button"
        className="conn-card-btn"
        onClick={(event) => {
          setAnchor({ x: event.clientX, y: event.clientY });
          setOpen(true);
        }}
      >
        Record
      </button>
      <RecordPopover open={open} anchor={anchor} onClose={() => setOpen(false)}>
        <p className="tag text-[var(--color-record)]">Official record</p>
        <h3 className="font-display text-xl font-bold mt-1">{card.title}</h3>
        <p className="mt-3 text-[1.05rem] leading-relaxed">{card.summary}</p>
        {card.extra && card.extra.length > 0 && (
          <ul className="mt-3 text-sm text-[var(--color-muted)] grid gap-1">
            {card.extra.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        )}
        {card.links && card.links.length > 0 && (
          <ul className="mt-3 text-sm grid gap-1">
            {card.links.map((l) => {
              const href = publicSourceHref(l.href);
              if (!href) return null;
              return (
              <li key={href + l.label}>
                <a className="link" href={href} rel="noopener noreferrer">
                  {l.label}
                </a>
              </li>
              );
            })}
          </ul>
        )}
        <p className="mt-3 text-sm">
          Source: {card.source_name}
          {card.retrieved_at ? ` · retrieved ${fmtDate(card.retrieved_at)}` : ""}
        </p>
        <details className="conn-check mt-3">
          <summary>How this was checked</summary>
          <p className="mt-2 text-sm text-[var(--color-muted)]">
            Politidex re-fetches the official source and compares it with this machine check stored on the claim:
          </p>
          <blockquote className="mt-2 text-sm leading-relaxed border-l-2 border-[var(--color-rule)] pl-3 font-sans">
            {card.excerpt}
          </blockquote>
          <p className="mt-2 text-sm">
            {source ? <a className="link" href={source} rel="noopener noreferrer">Open the cited source</a> : null}
          </p>
        </details>
      </RecordPopover>
    </div>
  );
}
