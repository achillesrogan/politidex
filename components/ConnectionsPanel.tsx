import Link from "next/link";
import Fact from "@/components/Fact";
import SourceCard from "@/components/SourceCard";
import { verified, fmtUSD, claims as allClaims } from "@/lib/data";
import { orgCategoryLabel, designationLabel, committeeTypeLabel } from "@/lib/labels";
import type { SourceCardInfo, SourceLink } from "@/components/SourceCard";
import { fmtDate } from "@/lib/dates";

function cardFor(id: string | undefined, opts: { title?: string; summary?: string; extra?: string[]; links?: SourceLink[] }): SourceCardInfo | null {
  const c = verified(id);
  if (!c) return null;
  const links = [...(opts.links || [])];
  if (c.source_url && !links.some((l) => l.href === c.source_url)) {
    links.push({ label: "Open the cited source", href: c.source_url });
  }
  return {
    title: opts.title || String(c.text),
    summary: opts.summary || String(c.text),
    excerpt: c.excerpt,
    source_name: c.source_name,
    source_url: c.source_url,
    retrieved_at: c.retrieved_at,
    extra: opts.extra,
    links,
  };
}

function moneySummary(r: any, retrieved?: string) {
  const n = r.count;
  const noun = n === 1 ? "contribution" : "contributions";
  const dest = r.recipient_role === "leadership_pac"
    ? `${r.recipient_name} (leadership PAC)`
    : r.recipient_name;
  const rec = retrieved ? `, retrieved ${fmtDate(retrieved)}` : "";
  return `${n} ${noun} from ${r.giver_name} to ${dest} totaling ${fmtUSD(r.total)} in the 2026 cycle (FEC bulk data${rec}).`;
}

function ieSummary(r: any, personName: string, retrieved?: string) {
  const n = r.count;
  const noun = n === 1 ? "independent expenditure" : "independent expenditures";
  const verb = r.support_oppose === "S" || r.support_oppose_full === "Support" ? "support" : "oppose";
  const rec = retrieved ? `, retrieved ${fmtDate(retrieved)}` : "";
  return `${n} ${noun} by ${r.spender_name} to ${verb} ${personName} totaling ${fmtUSD(r.total)} in the 2026 cycle (FEC bulk data${rec}).`;
}

function fecLinks(r: any, c: any): SourceLink[] {
  const links: SourceLink[] = [];
  const seen = new Set<string>();
  const add = (label: string, href?: string | null) => {
    if (!href || seen.has(href)) return;
    seen.add(href);
    links.push({ label, href });
  };
  add("Itemized disbursements on FEC.gov (giver, recipient, and 2026 cycle)", r.disbursements_url || c?.source_url);
  add("Itemized receipts on FEC.gov (same committees and cycle)", r.receipts_url);
  for (const img of r.image_urls || []) add("Official FEC filing image", img);
  add("Official FEC bulk file", r.bulk_url || c?.check?.bulk_url);
  add("FEC description of the bulk file", r.bulk_description_url || c?.check?.description_url);
  return links;
}

function Bars({ items }: { items: { label: string; value: number; claim?: string }[] }) {
  const shown = items.filter((i) => verified(i.claim));
  const max = Math.max(...shown.map((i) => i.value), 1);
  if (!shown.length) return null;
  return (
    <ul className="conn-bars mb-4">
      {shown.map((i) => (
        <Fact key={i.claim} as="li" claim={i.claim} className="conn-bar-row">
          <span className="conn-bar-label">{i.label}</span>
          <span className="conn-bar-track">
            <span className="conn-bar-fill" style={{ width: `${Math.max(2, (i.value / max) * 100)}%` }} />
          </span>
          <span className="conn-bar-val tabular-nums">{fmtUSD(i.value)}</span>
        </Fact>
      ))}
    </ul>
  );
}

export default function ConnectionsPanel({
  ties,
  personName,
  cosponsors,
}: {
  ties: any;
  personName: string;
  cosponsors?: any[];
}) {
  if (!ties) return null;
  const C = allClaims();
  const money = (ties.money?.rows || []).filter((r: any) => verified(r.claim));
  const cats = (ties.money?.categories || []).filter((r: any) => verified(r.claim));
  const ie = (ties.ie?.rows || []).filter((r: any) => verified(r.claim));
  const lobby = (ties.lobbying?.rows || []).filter((r: any) => verified(r.claim));
  const revolving = (ties.revolving?.rows || []).filter((r: any) => verified(r.claim));
  const people = (cosponsors || []).filter((c: any) => verified(c.claim));
  if (!money.length && !ie.length && !lobby.length && !revolving.length && !people.length && !cats.length) return null;

  return (
    <section className="newspaper-card min-w-0 p-5 sm:p-6 border-l-4 !border-l-[var(--color-record)]">
      <div className="tag text-[var(--color-record)]">Record</div>
      <h2 className="font-display text-2xl font-bold mt-1 mb-2">Connections</h2>
      <p className="text-sm text-[var(--color-muted)] mb-4">{ties.note}</p>

      <div className="conn-wrap">
        <input type="radio" name="conn-tabs" id="ctab-money" defaultChecked className="conn-radio" />
        <input type="radio" name="conn-tabs" id="ctab-lobby" className="conn-radio" />
        <input type="radio" name="conn-tabs" id="ctab-ie" className="conn-radio" />
        <input type="radio" name="conn-tabs" id="ctab-people" className="conn-radio" />
        <div className="conn-tablist" role="tablist">
          <label htmlFor="ctab-money">Money{money.length ? ` (${money.length})` : ""}</label>
          <label htmlFor="ctab-lobby">Lobbying{lobby.length ? ` (${lobby.length})` : ""}</label>
          <label htmlFor="ctab-ie">Outside spending{ie.length ? ` (${ie.length})` : ""}</label>
          <label htmlFor="ctab-people">People{(people.length + revolving.length) ? ` (${people.length + revolving.length})` : ""}</label>
        </div>

        <div className="conn-panel panel-money mt-4">
          <p className="text-sm text-[var(--color-muted)] mb-3">{ties.money?.source_note}</p>
          {verified(ties.scheme_claim) && (
            <p className="text-sm mb-3">
              <Fact claim={ties.scheme_claim}>Interest group categories are the FEC’s official ORG_TP values.</Fact>
            </p>
          )}
          {cats.length > 0 && <Bars items={cats.map((c: any) => ({ label: orgCategoryLabel(c.org_type_full), value: c.total, claim: c.claim }))} />}
          {money.length === 0 ? (
            <p className="text-[var(--color-muted)]">No verified committee contributions are listed for this member in the 2026-cycle files used here.</p>
          ) : (
            <ul className="grid gap-2">
              {money.map((r: any) => {
                const c = C[r.claim];
                const card = cardFor(r.claim, {
                  title: r.giver_name,
                  summary: moneySummary(r, c?.retrieved_at),
                  extra: [
                    r.connected_org ? `Connected organization (as listed with FEC): ${r.connected_org}` : "",
                    committeeTypeLabel(r.committee_type, r.committee_type_full) ? `Committee type: ${committeeTypeLabel(r.committee_type, r.committee_type_full)}` : "",
                    `Interest group category: ${orgCategoryLabel(r.org_type_full)}`,
                    designationLabel(r.designation, r.designation_full) ? `Designation: ${designationLabel(r.designation, r.designation_full)}` : "",
                    `Recipient: ${r.recipient_name} (${r.recipient_role === "leadership_pac" ? "leadership PAC" : "principal campaign committee"})`,
                  ].filter(Boolean),
                  links: fecLinks(r, c),
                });
                if (!card || !c) return null;
                return (
                  <li key={r.claim} className="border-b border-[var(--color-rule)]/60 pb-2">
                    <SourceCard card={card}>
                      <Fact claim={r.claim}>
                        {r.org_slug ? <Link className="link" href={`/org/${r.org_slug}`}>{r.giver_name}</Link> : r.giver_name}
                        {" — "}
                        {fmtUSD(r.total)}
                        <span className="text-[var(--color-muted)] text-sm">
                          {" "}({r.count} {r.count === 1 ? "receipt" : "receipts"}
                          {r.recipient_role === "leadership_pac" ? " · leadership PAC" : ""})
                        </span>
                      </Fact>
                    </SourceCard>
                  </li>
                );
              })}
            </ul>
          )}
          {ties.money?.all_givers > money.length && (
            <p className="text-sm text-[var(--color-muted)] mt-3">
              {ties.money.all_givers.toLocaleString("en-US")} giving committees appear in the official file for this member; the {money.length} largest are listed.
            </p>
          )}
        </div>

        <div className="conn-panel panel-lobby mt-4">
          <p className="text-sm text-[var(--color-muted)] mb-3">{ties.lobbying?.source_note}</p>
          <p className="text-sm text-[var(--color-muted)] mb-3">LDA filings do not say which congressional offices were contacted; this does not mean the member was lobbied.</p>
          <p className="text-sm text-[var(--color-muted)] mb-3">{ties.lda_disclaimer}</p>
          {lobby.length === 0 ? (
            <p className="text-[var(--color-muted)]">No verified lobbying-disclosure matches are listed for this member in the filings retrieved so far.</p>
          ) : (
            <ul className="grid gap-2">
              {lobby.map((r: any) => {
                const card = cardFor(r.claim, {
                  title: r.client_name,
                  summary: `This filing's issue text lists ${r.bill_label}. ${personName} ${r.role === "sponsor" ? "sponsored" : "cosponsored"} ${r.bill_label} (119th Congress).`,
                  extra: [
                    `Registrant: ${r.registrant_name}`,
                    r.general_issue_code_display ? `General issue: ${r.general_issue_code_display}` : "",
                    r.filing_type_display ? `${r.filing_year} ${r.filing_type_display}` : "",
                    r.bill_title ? `119th Congress title: ${r.bill_title}` : "",
                  ].filter(Boolean),
                  links: r.document_url ? [{ label: "Open the lobbying disclosure filing", href: r.document_url }] : [],
                });
                if (!card) return null;
                return (
                  <li key={r.claim} className="border-b border-[var(--color-rule)]/60 pb-2">
                    <SourceCard card={card}>
                      <Fact claim={r.claim}>
                        This filing&apos;s issue text lists {r.bill_label}. {personName} {r.role === "sponsor" ? "sponsored" : "cosponsored"} {r.bill_label} (119th Congress)
                        {" — "}
                        {r.client_slug ? <Link className="link" href={`/org/${r.client_slug}`}>{r.client_name}</Link> : r.client_name}
                        {r.bill_title ? <span className="text-[var(--color-muted)] text-sm"> ({r.bill_title})</span> : null}
                      </Fact>
                    </SourceCard>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="conn-panel panel-ie mt-4">
          <p className="text-sm text-[var(--color-muted)] mb-3">{ties.ie?.source_note}</p>
          {ie.length === 0 ? (
            <p className="text-[var(--color-muted)]">No verified independent expenditures for or against this member are listed in the 2026-cycle file used here.</p>
          ) : (
            <ul className="grid gap-2">
              {ie.map((r: any) => {
                const c = C[r.claim];
                const card = cardFor(r.claim, {
                  title: r.spender_name,
                  summary: ieSummary(r, personName, c?.retrieved_at),
                  extra: [
                    `Position reported: ${r.support_oppose_full}`,
                    `${r.count} ${r.count === 1 ? "expenditure" : "expenditures"}`,
                  ],
                  links: fecLinks(r, c),
                });
                if (!card) return null;
                return (
                  <li key={r.claim} className="border-b border-[var(--color-rule)]/60 pb-2">
                    <SourceCard card={card}>
                      <Fact claim={r.claim}>
                        {r.org_slug ? <Link className="link" href={`/org/${r.org_slug}`}>{r.spender_name}</Link> : r.spender_name}
                        {" — "}
                        {r.support_oppose_full}
                        {" "}
                        {fmtUSD(r.total)}
                      </Fact>
                    </SourceCard>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="conn-panel panel-people mt-4">
          {people.length > 0 && (
            <div className="mb-6">
              <h3 className="font-display text-lg font-bold mb-2">Cosponsors</h3>
              <p className="text-sm text-[var(--color-muted)] mb-2">Members whose bills {personName} cosponsored most often (119th Congress). These counts are the same verified Congress.gov figures shown elsewhere on this profile.</p>
              <ul className="grid gap-2">
                {people.map((c: any) => (
                  <li key={c.partner}>
                    <Fact claim={c.claim}>
                      {c.partner_slug ? <Link className="link" href={`/p/${c.partner_slug}`}>{c.partner_name}</Link> : c.partner_name}
                      {" — "}{c.count} bills
                    </Fact>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div>
          <h3 className="font-display text-lg font-bold mb-2">Lobbyists who list a past position with this member (LDA covered position)</h3>
          <p className="text-sm text-[var(--color-muted)] mb-2">A covered position is a government job the lobbyist reports having held. It does not mean the lobbyist works for or with this member now.</p>
          <p className="text-sm text-[var(--color-muted)] mb-2">{ties.revolving?.source_note}</p>
          <p className="text-sm text-[var(--color-muted)] mb-3">{ties.lda_disclaimer}</p>
          {revolving.length === 0 ? (
            <p className="text-[var(--color-muted)]">No verified covered-position listings that name {personName} are shown in the filings retrieved so far.</p>
          ) : (
            <ul className="grid gap-2">
              {revolving.map((r: any) => {
                const card = cardFor(r.claim, {
                  title: r.lobbyist_name || r.registrant_name,
                  extra: [
                    r.registrant_name ? `Registrant: ${r.registrant_name}` : "",
                    r.client_name ? `Client: ${r.client_name}` : "",
                  ].filter(Boolean),
                  links: r.document_url ? [{ label: "Open the lobbying disclosure filing", href: r.document_url }] : [],
                });
                if (!card) return null;
                const who = r.lobbyist_name || "A lobbyist";
                return (
                  <li key={r.claim} className="border-b border-[var(--color-rule)]/60 pb-2">
                    <SourceCard card={card}>
                      <Fact claim={r.claim}>
                        {who}, registered by{" "}
                        {r.registrant_slug ? <Link className="link" href={`/org/${r.registrant_slug}`}>{r.registrant_name}</Link> : r.registrant_name}
                        {", listed a covered position: “"}
                        {r.excerpt}
                        {"”"}
                      </Fact>
                    </SourceCard>
                  </li>
                );
              })}
            </ul>
          )}
          </div>
        </div>
      </div>
    </section>
  );
}
