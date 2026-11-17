import { verified } from "@/lib/data";
import { fmtDate } from "@/lib/dates";
import { badgeForClaim } from "@/lib/entity-registry.mjs";
import { publicSourceHref } from "@/lib/source-href.mjs";
import ConfidenceBadge from "@/components/ConfidenceBadge";
/** Renders children only when the claim passed verification. Every rendered fact carries data-claim for the CI check. */
export default function Fact({ claim, children, as = "span", className }: { claim?: string | null; children: React.ReactNode; as?: "span" | "div" | "li" | "td"; className?: string }) {
  const c = verified(claim);
  if (!c) return null;
  const Tag = as as any;
  const when = fmtDate(c.retrieved_at);
  return (
    <Tag data-fact="" data-claim={c.id} className={className}>
      {children}
      {publicSourceHref(c.source_url) ? <a className="cite" href={publicSourceHref(c.source_url) || undefined} rel="noopener noreferrer" title={`${c.source_name} — retrieved ${when} — “${c.excerpt}”`}>[source]</a> : null}
      {when ? <span className="cite"> retrieved {when}</span> : null}
      <ConfidenceBadge badge={badgeForClaim(c)} />
    </Tag>
  );
}
