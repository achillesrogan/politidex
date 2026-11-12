import PageHead from "@/components/PageHead";
export const metadata = { title: "Terms" };
export default function Terms() {
  return (
    <div className="max-w-3xl">
      <PageHead kicker="Policy" title="Terms of use" />
      <div className="prose-news">
        <p>Politidex is provided free, for public-interest, non-commercial research and education, as is and without warranty.</p>
        <p><strong>Records, not accusations.</strong> Record content restates official public records and links to them. Analysis content is computed by documented methods and is labeled as such. Nothing on this site is an allegation of wrongdoing or legal advice. Official records can be amended or delayed; always check the linked source.</p>
        <p><strong>Reuse.</strong> Our original compilations may be reused under CC BY 4.0 with attribution to Politidex, where the underlying sources allow. Individual contributor information from FEC reports may not be used for soliciting contributions or for commercial purposes (52 U.S.C. § 30111(a)(4)). Lobbying data, when added, is subject to LDA.gov terms.</p>
        <p><strong>Code.</strong> The source code is released under the GNU AGPL-3.0 or later.</p>
        <p>These terms are a draft pending legal review and may change. Last updated November 11, 2026.</p>
      </div>
    </div>
  );
}
