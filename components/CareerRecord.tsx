import { RecordModule } from "@/components/Module";
import { fmtDate } from "@/lib/dates";
import type { Career } from "@/lib/career-record.mjs";

function Cited({
  text,
  href,
  retrieved,
  sourceName,
  children,
  as = "li",
}: {
  text: string;
  href: string;
  retrieved: string;
  sourceName: string;
  children?: React.ReactNode;
  as?: "li" | "span";
}) {
  const when = fmtDate(retrieved);
  const Tag = as;
  return (
    <Tag data-career-fact="" data-source={href} data-retrieved={retrieved}>
      {text}{" "}
      <a className="cite" href={href} rel="noopener noreferrer">{sourceName}</a>
      {when ? <span className="cite"> retrieved {when}</span> : null}
      {children}
    </Tag>
  );
}

export default function CareerRecord({ career }: { career: Career }) {
  return (
    <RecordModule title="Career">
      <div data-career-section="">
        <h3 className="font-display text-xl font-bold mt-1 mb-2">Terms</h3>
        <p className="text-sm text-[var(--color-muted)] mb-2">Congress.gov records a special-election or appointed start as that Congress&apos;s start year.</p>
        <ul className="grid gap-2 mb-4">
          {career.terms.map((term) => (
            <Cited key={term.text} text={term.text} href={term.href} retrieved={term.retrieved_at} sourceName={term.source_name} />
          ))}
        </ul>
        <h3 className="font-display text-xl font-bold mb-2">Sponsored bills and resolutions</h3>
        <p className="text-sm text-[var(--color-muted)] mb-2">{career.sponsoredBillCount} total. Amendments are not included.</p>
        <div className="grid gap-2 mb-4">
          {career.bills.map((group) => (
            <details key={group.congress}>
              <summary>
                <Cited as="span" text={group.text} href={group.href} retrieved={group.retrieved_at} sourceName={group.source_name} />
              </summary>
              <ul className="mt-1 grid gap-1 pl-4">
                {group.links.map((bill) => (
                  <li key={bill.href}>
                    <a className="link" href={bill.href} rel="noopener noreferrer">{bill.type} {bill.number}</a>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </div>
        {career.committees.length > 0 && (
          <>
            <h3 className="font-display text-xl font-bold mb-2">FEC committees</h3>
            <ul className="grid gap-2 mb-4">
              {career.committees.map((row) => (
                <Cited key={row.href} text={row.text} href={row.href} retrieved={row.retrieved_at} sourceName={row.source_name}>
                  {" "}
                  <a className="link text-sm" href={row.bulk} rel="noopener noreferrer">Bulk file</a>
                </Cited>
              ))}
            </ul>
          </>
        )}
      </div>
    </RecordModule>
  );
}
