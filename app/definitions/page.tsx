import PageHead from "@/components/PageHead";
export const metadata = { title: "Definitions" };
const TERMS: [string, string, string][] = [
  ["Roll-call vote", "A vote in which each member’s position is recorded by name. Voice votes and unanimous consent are not recorded by name.", "https://www.senate.gov/legislative/votes_new.htm"],
  ["Cloture", "The Senate procedure for ending debate on a pending matter; it generally requires three-fifths of senators duly chosen and sworn.", "https://www.senate.gov/about/powers-procedures/filibusters-cloture.htm"],
  ["Not Voting", "Recorded on an official tally when a member does not cast Yea, Nay, or Present on a roll call.", "https://clerk.house.gov/Votes"],
  ["Political action committee (PAC)", "A committee that raises and spends money to elect or defeat candidates, registered with and reporting to the FEC.", "https://www.fec.gov/help-candidates-and-committees/registering-pac/types-nonconnected-pacs/"],
  ["Principal campaign committee", "The committee a federal candidate designates to receive contributions and make expenditures for their campaign.", "https://www.fec.gov/help-candidates-and-committees/registering-candidate/"],
  ["Cosponsor", "A member who formally adds their name in support of a bill introduced by another member (the sponsor).", "https://www.congress.gov/help/legislative-glossary"],
];
export default function Definitions() {
  return (
    <div className="max-w-3xl">
      <PageHead kicker="Reference" title="Definitions" dek="Plain-language definitions of terms used on Politidex, each with an official reference." />
      <dl className="grid gap-4">
        {TERMS.map(([t, d, u]) => (
          <div key={t} className="newspaper-card p-5"><dt className="font-display text-xl font-bold">{t}</dt><dd className="mt-1">{d} <a className="link text-sm" href={u} rel="noopener noreferrer">Official reference</a></dd></div>
        ))}
      </dl>
    </div>
  );
}
