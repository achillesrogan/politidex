"use client";

import { useState } from "react";
import { fmtDate } from "@/lib/dates";
import RecordPopover from "@/components/RecordPopover";
import { officialGovHref, publicSourceHref, renderedSourceHref } from "@/lib/source-href.mjs";
import { confidenceBadge } from "@/lib/entity-registry.mjs";
import ConfidenceBadge from "@/components/ConfidenceBadge";

export type CommitteeFact = {
  id?: string;
  label: string;
  text: string;
  excerpt: string;
  source_name: string;
  source_url: string;
  retrieved_at?: string;
};

export default function CommitteeInfo({
  name,
  role,
  officialId,
  claimId,
  website,
  membershipUrl,
  facts,
  summary,
}: {
  name: string;
  role?: string | null;
  officialId?: string | null;
  claimId: string;
  website?: string | null;
  membershipUrl?: string | null;
  facts: CommitteeFact[];
  summary: CommitteeFact[];
}) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  const site = officialGovHref(website || "");
  const roster = publicSourceHref(membershipUrl || "") || null;
  const badge = confidenceBadge({ official_id: officialId, source_url: membershipUrl || site || "" });
  const shown = [...summary, ...facts].filter((f) => renderedSourceHref(f));
  return (
    <>
      <span data-fact="" data-claim={claimId} className="inline">
        <button
          type="button"
          className="committee-name"
          onClick={(event) => {
            setAnchor({ x: event.clientX, y: event.clientY });
            setOpen(true);
          }}
        >
          {name}
        </button>
        {role && role !== "Member" ? ` — ${role}` : ""}
        {roster ? (
          <a className="cite committee-roster" href={roster} rel="noopener noreferrer">
            Membership source
          </a>
        ) : null}
      </span>
      <RecordPopover open={open} anchor={anchor} onClose={() => setOpen(false)} label={`${name} committee record`}>
        <p className="tag text-[var(--color-record)]">Official committee record</p>
        <h3 className="font-display text-xl font-bold mt-1">{name}</h3>
        <ConfidenceBadge badge={badge} />
        {site ? (
          <p className="mt-3">
            <a className="link" href={site} rel="noopener noreferrer">
              Official website
            </a>
          </p>
        ) : null}
        {shown.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--color-muted)]">An editor-reviewed summary is not on this card yet.</p>
        ) : (
          shown.map((f) => {
            const href = renderedSourceHref(f);
            return (
              <section key={f.id || `${f.label}-${f.source_url}`} className="mt-4">
                <h4 className="font-sans text-xs uppercase tracking-wide font-bold text-[var(--color-record)]">{f.label}</h4>
                <p data-fact={f.id ? "" : undefined} data-claim={f.id || undefined} className="mt-1 leading-relaxed">
                  {f.text}
                </p>
                <p className="mt-1 text-sm">
                  Source: {f.source_name}
                  {f.retrieved_at ? ` · retrieved ${fmtDate(f.retrieved_at)}` : ""}
                  {href ? (
                    <>
                      {" · "}
                      <a className="link" href={href} rel="noopener noreferrer">
                        Official page
                      </a>
                    </>
                  ) : null}
                </p>
                {f.excerpt ? (
                  <details className="conn-check mt-2">
                    <summary>How this was checked</summary>
                    <blockquote className="mt-2 text-sm leading-relaxed border-l-2 border-[var(--color-rule)] pl-3 font-sans">
                      {f.excerpt}
                    </blockquote>
                  </details>
                ) : null}
              </section>
            );
          })
        )}
        {roster ? (
          <p className="mt-4 text-sm">
            <a className="link" href={roster} rel="noopener noreferrer">
              Membership source
            </a>
          </p>
        ) : null}
      </RecordPopover>
    </>
  );
}
