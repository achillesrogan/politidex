import { verified } from "@/lib/data";
import { fmtDate } from "@/lib/dates";
/** Renders children only when the claim passed verification. Every rendered fact carries data-claim for the CI check. */
export default function Fact({ claim, children, as = "span", className }: { claim?: string | null; children: React.ReactNode; as?: "span" | "div" | "li" | "td"; className?: string }) {
  const c = verified(claim);
  if (!c) return null;
  const Tag = as as any;
  return (
    <Tag data-fact="" data-claim={c.id} className={className}>
      {children}
      <a className="cite" href={c.source_url} rel="noopener noreferrer" title={`${c.source_name} — retrieved ${fmtDate(c.retrieved_at)} — “${c.excerpt}”`}>[source]</a>
    </Tag>
  );
}
