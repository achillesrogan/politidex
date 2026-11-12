import PageHead from "@/components/PageHead";
import Directory from "@/components/Directory";
import ComingSoon from "@/components/ComingSoon";
import { people, verified, profile } from "@/lib/data";
export const metadata = { title: "People" };
export default function PeoplePage() {
  // Only list people whose core office claim passed verification.
  const all = people().filter((p) => { const pr = profile(p.slug); return pr && verified(pr.facts?.[0]?.claim); });
  if (!all.length) return <ComingSoon title="Politician profiles"><p>The earlier sample profiles have been removed. Profiles for every current member of Congress, the President, Vice President, and Cabinet are being built from official records and will appear after verification and review.</p></ComingSoon>;
  const order = { executive: 0, senate: 1, house: 2 } as Record<string, number>;
  all.sort((a, b) => (order[a.chamber] - order[b.chamber]) || a.name.localeCompare(b.name));
  return (
    <div>
      <PageHead kicker="Directory" title="People" dek="Current federal officials: the President, Vice President, Cabinet, and every member of the 119th Congress." />
      <Directory people={all.map(({ slug, name, role, party, state, district, chamber }) => ({ slug, name, role, party, state, district, chamber }))} />
    </div>
  );
}
