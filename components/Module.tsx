export function RecordModule({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="newspaper-card min-w-0 p-5 sm:p-6 border-l-4 !border-l-[var(--color-record)]">
      <div className="tag text-[var(--color-record)]">Record</div>
      <h2 className="font-display text-2xl font-bold mt-1 mb-3">{title}</h2>
      {children}
    </section>
  );
}
export function AnalysisModule({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="min-w-0 p-5 sm:p-6 border border-dashed border-[var(--color-analysis)] bg-[#fdf6ec]">
      <div className="tag text-[var(--color-analysis)]">Analysis · computed from the record</div>
      <h2 className="font-display text-2xl font-bold mt-1 mb-3">{title}</h2>
      {children}
      <p className="mt-4 text-sm font-sans text-[var(--color-muted)]">Analysis is calculated from official roll-call records using the <a className="link" href="/methodology#politi-matrix-version-1">published method</a>. It is not an allegation of wrongdoing; absences and vote patterns can have ordinary explanations.</p>
    </section>
  );
}
