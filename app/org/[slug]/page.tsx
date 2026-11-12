import { notFound } from "next/navigation";
import Link from "next/link";
import Fact from "@/components/Fact";
import SourceCard from "@/components/SourceCard";
import { org, orgIndex, verified, fmtUSD, claims as allClaims } from "@/lib/data";
import { orgCategoryLabel, designationLabel, committeeTypeLabel } from "@/lib/labels";
import type { SourceCardInfo, SourceLink } from "@/components/SourceCard";

export const dynamicParams = false;
export function generateStaticParams() {
  const orgs = orgIndex().orgs;
  return orgs.length ? orgs.map((o) => ({ slug: o.slug })) : [{ slug: "_none" }];
}
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const o = org(slug);
  return { title: o ? o.name : "Organization", alternates: { canonical: `/org/${slug}` } };
}

function cardFor(id: string | undefined, opts: { title?: string; summary?: string; extra?: string[]; links?: SourceLink[] }): SourceCardInfo | null {
  const c = verified(id);
  if (!c) return null;
  const links: SourceLink[] = [...(opts.links || [])];
  if (c.source_url && !links.some((l) => l.href === c.source_url)) links.push({ label: "Open the cited source", href: c.source_url });
  const bulk = c.check && (c.check as any).bulk_url;
  const desc = c.check && (c.check as any).description_url;
  if (bulk) links.push({ label: "Official FEC bulk file", href: String(bulk) });
  if (desc) links.push({ label: "FEC description of the bulk file", href: String(desc) });
  return { title: opts.title || String(c.text), summary: opts.summary || String(c.text), excerpt: c.excerpt, source_name: c.source_name, source_url: c.source_url, retrieved_at: c.retrieved_at, extra: opts.extra, links };
}

export default async function OrgPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const o = org(slug);
  if (!o) notFound();
  const members = (o.members || []).filter((m: any) => verified(m.claim));
  if (!members.length) notFound();
  const C = allClaims();
  const kindLabel = o.kind === "fec-committee" ? "Political committee (FEC)" : o.kind === "lda-client" && o.client_individual ? "LDA client (individual)" : o.kind === "lda-client" ? "LDA client" : o.kind === "lda-registrant" && o.registrant_individual ? "LDA registrant (individual)" : o.kind === "lda-registrant" ? "LDA registrant" : "Organization";
  return (
    <article>
      <header className="mb-6 border-b-4 border-double border-[var(--color-ink)] pb-4">
        <div className="tag text-[var(--color-muted)]">{kindLabel}</div>
        <h1 className="font-display text-4xl sm:text-5xl font-black masthead-shadow mt-1">{o.name}</h1>
        {o.connected_org && <p className="text-lg text-[var(--color-muted)] mt-1">Connected organization (as listed with FEC): {o.connected_org}</p>}
      </header>
      <section className="newspaper-card p-5 sm:p-6 border-l-4 !border-l-[var(--color-record)]">
        <div className="tag text-[var(--color-record)]">Record</div>
        <h2 className="font-display text-2xl font-bold mt-1 mb-3">Documented connections to current members</h2>
        <p className="text-sm text-[var(--color-muted)] mb-4">{o.note}</p>
        {o.lda_disclaimer && <p className="text-sm text-[var(--color-muted)] mb-4">{o.lda_disclaimer}</p>}
        <dl className="grid gap-1 sm:grid-cols-[12rem_1fr] mb-4 text-sm">
          {o.committee_id && <><dt className="font-semibold">FEC committee ID</dt><dd><a className="link" href={o.url} rel="noopener noreferrer">{o.committee_id}</a></dd></>}
          {(committeeTypeLabel(o.committee_type, o.committee_type_full) || o.committee_type_full) && <><dt className="font-semibold">Committee type</dt><dd>{committeeTypeLabel(o.committee_type, o.committee_type_full) || o.committee_type_full}</dd></>}
          {o.kind === "fec-committee" && <><dt className="font-semibold">Interest group category</dt><dd>{orgCategoryLabel(o.org_type_full)}</dd></>}
          {(designationLabel(o.designation, o.designation_full) || o.designation_full) && <><dt className="font-semibold">Designation</dt><dd>{designationLabel(o.designation, o.designation_full) || o.designation_full}</dd></>}
        </dl>
        <p className="text-sm text-[var(--color-muted)] mb-3">
          This page lists current members whose published Connections panel includes this organization. It is not a complete list of every appearance in the official file.
        </p>
        <ul className="grid gap-2">
          {members.map((m: any, i: number) => {
            const c = C[m.claim];
            const card = cardFor(m.claim, { title: o.name, extra: [m.relationship, m.total != null ? fmtUSD(m.total) : ""].filter(Boolean),
              links: (m.image_urls || []).map((href: string) => ({ label: "Official FEC filing image", href })) });
            if (!card || !c) return null;
            return (
              <li key={`${m.claim}-${i}`} className="border-b border-[var(--color-rule)]/60 pb-2">
                <SourceCard card={card}>
                  <Fact claim={m.claim}>
                    <Link className="link" href={`/p/${m.slug}`}>{m.name}</Link>
                    {" — "}
                    {m.relationship}
                    {m.total != null ? ` — ${fmtUSD(m.total)}` : ""}
                  </Fact>
                </SourceCard>
              </li>
            );
          })}
        </ul>
      </section>
    </article>
  );
}
