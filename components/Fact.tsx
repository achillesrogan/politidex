import { verified } from "@/lib/data";
import { fmtDate } from "@/lib/dates";
import { badgeForClaim } from "@/lib/entity-registry.mjs";
import { renderedSourceHref } from "@/lib/source-href.mjs";
import ConfidenceBadge from "@/components/ConfidenceBadge";
/** Renders children only when the claim passed verification. Every rendered fact carries data-claim for the CI check. */
export default function Fact({ claim, children, as = "span", className }: { claim?: string | null; children: React.ReactNode; as?: "span" | "div" | "li" | "td"; className?: string }) {
  const c = verified(claim);
  const href = renderedSourceHref(c);
  if (!c || !href) return null;
  const Tag = as as any;
  const when = fmtDate(c.retrieved_at);
  return (
    <Tag data-fact="" data-claim={c.id} className={className}>
      {children}
      <a className="cite" href={href} rel="noopener noreferrer" title={`${c.source_name} — retrieved ${when} — “${c.excerpt}”`}>[source]</a>
      {when ? <span className="cite"> retrieved {when}</span> : null}
      <ConfidenceBadge badge={badgeForClaim(c)} />
    </Tag>
  );
}
