import { readFileSync } from "node:fs";
import path from "node:path";
import HowToRead from "@/components/HowToRead";
import PageHead from "@/components/PageHead";
import MoneyFlowExplorer from "@/components/moneyflow/MoneyFlowExplorer";

export const metadata = { title: "Reported money out" };

function wording() {
  const file = path.join(process.cwd(), "data", "moneyflow", "wording.json");
  return JSON.parse(readFileSync(file, "utf8")) as { fungibility_note: string; cycle: number };
}

export default function MoneyFlowPage() {
  const words = wording();
  return (
    <div>
      <PageHead
        kicker="Campaign money"
        title="Reported money out"
        dek="Reported disbursements from a committee account for the current FEC cycle. Open a recipient when that account has its own record."
      />
      <HowToRead />
      <MoneyFlowExplorer note={words.fungibility_note} cycle={words.cycle} />
    </div>
  );
}
