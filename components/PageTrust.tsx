import { SITE } from "@/lib/site";
import { fmtDate } from "@/lib/dates";

export default function PageTrust({ retrieved }: { retrieved?: string | null }) {
  const when = fmtDate(retrieved);
  const subject = encodeURIComponent("Report an error");
  return (
    <p className="text-sm text-[var(--color-muted)]">
      {when ? <>Data as of {when}. </> : null}
      <a className="link" href={`mailto:${SITE.correctionsEmail}?subject=${subject}`}>Report an error</a>
    </p>
  );
}
