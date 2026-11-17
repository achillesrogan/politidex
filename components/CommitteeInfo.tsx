"use client";
import { useState } from "react";
import { fmtDate } from "@/lib/dates";
import RecordPopover from "@/components/RecordPopover";

export type CommitteeFact = {
  id: string;
  label: string;
  text: string;
  excerpt: string;
  source_name: string;
  source_url: string;
  retrieved_at?: string;
};

export default function CommitteeInfo({ name, facts }: { name: string; facts: CommitteeFact[] }) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  if (!facts.length) return null;
  return (
    <>
      <button
        type="button"
        className="conn-card-btn"
        onClick={(event) => {
          setAnchor({ x: event.clientX, y: event.clientY });
          setOpen(true);
        }}
      >
        About
      </button>
      <RecordPopover open={open} anchor={anchor} onClose={() => setOpen(false)} label="Official committee record">
        <p className="tag text-[var(--color-record)]">Official committee record</p>
        <h3 className="font-display text-xl font-bold mt-1">{name}</h3>
        {facts.map((f) => (
          <section key={f.id} className="mt-4">
            <h4 className="font-sans text-xs uppercase tracking-wide font-bold text-[var(--color-record)]">{f.label}</h4>
            <p data-fact="" data-claim={f.id} className="mt-1 leading-relaxed">
              {f.text}
            </p>
            <p className="mt-1 text-sm">
              Source: {f.source_name}
              {f.retrieved_at ? ` · retrieved ${fmtDate(f.retrieved_at)}` : ""}
              {" · "}
              <a className="link" href={f.source_url} rel="noopener noreferrer">
                Official page
              </a>
            </p>
            <details className="conn-check mt-2">
              <summary>How this was checked</summary>
              <blockquote className="mt-2 text-sm leading-relaxed border-l-2 border-[var(--color-rule)] pl-3 font-sans">
                {f.excerpt}
              </blockquote>
            </details>
          </section>
        ))}
      </RecordPopover>
    </>
  );
}
