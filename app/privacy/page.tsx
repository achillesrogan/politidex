import PageHead from "@/components/PageHead";
import { SITE } from "@/lib/site";
export const metadata = { title: "Privacy" };
export default function Privacy() {
  return (
    <div className="max-w-3xl">
      <PageHead kicker="Policy" title="Privacy" dek="Short version: we do not run accounts, newsletters, advertising, or tracking cookies." />
      <div className="prose-news">
        <p>Politidex is a read-only public website. There are no user accounts, sign-ups, comment forms, or advertising trackers.</p>
        <p>Our hosting provider processes standard server logs (such as IP address and requested page) to deliver and secure the site. We do not sell or share visitor data.</p>
        <p>If you email us, we use your message only to respond and to handle any correction you report.</p>
        <p>About the people we cover: we publish information about public officials drawn from official public records. We do not publish home addresses, personal contact details, or individual campaign-contributor information.</p>
        <p>Questions: <a href={`mailto:${SITE.editorEmail}`}>{SITE.editorEmail}</a>. Last updated November 11, 2026.</p>
      </div>
    </div>
  );
}
