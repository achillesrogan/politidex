"use client";

import { useState } from "react";
import Link from "next/link";
import RecordPopover from "@/components/RecordPopover";
import ConfidenceBadge from "@/components/ConfidenceBadge";
import { fmtDate } from "@/lib/dates";
import { renderedSourceHref } from "@/lib/source-href.mjs";
import type { EntityRecord } from "@/lib/entity-registry.mjs";

const KIND_LABEL: Record<string, string> = {
  member: "Member",
  committee: "Committee",
  pac: "Political committee",
  registrant: "Lobbying registrant",
  client: "Lobbying client",
  bill: "Bill",
  record: "Official record",
};

export default function EntityLink({ entity, children }: { entity: EntityRecord | null; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  if (!entity) return <>{children}</>;
  const source = renderedSourceHref(entity);
  if (!source) return <>{children || entity.name}</>;
  return (
    <>
      <button
        type="button"
        className="committee-name"
        onClick={(event) => {
          setAnchor({ x: event.clientX, y: event.clientY });
          setOpen(true);
        }}
      >
        {entity.name}
      </button>
      <ConfidenceBadge badge={entity.badge} />
      <RecordPopover open={open} anchor={anchor} onClose={() => setOpen(false)} label={`${entity.name} record`}>
        <p className="tag text-[var(--color-record)]">{KIND_LABEL[entity.kind] || "Official record"}</p>
        <h3 className="font-display text-xl font-bold mt-1">{entity.name}</h3>
        <ConfidenceBadge badge={entity.badge} />
        <p className="mt-3 text-sm">
          Source: {entity.source_name}
          {entity.retrieved_at ? ` · retrieved ${fmtDate(entity.retrieved_at)}` : ""}
        </p>
        <p className="mt-3 text-sm">
          <a className="link" href={source} rel="noopener noreferrer">Open the cited source</a>
        </p>
        {entity.href ? (
          <p className="mt-2 text-sm">
            <Link className="link" href={entity.href}>Open the Politidex page</Link>
          </p>
        ) : null}
      </RecordPopover>
    </>
  );
}
