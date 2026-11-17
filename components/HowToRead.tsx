import { HOW_TO_READ, READING_TERMS, type ReadingTerm } from "@/lib/reading-terms.mjs";

export function Term({ id }: { id: string }) {
  const term = READING_TERMS.find((item) => item.id === id);
  if (!term) return null;
  return (
    <abbr className="cursor-help underline decoration-dotted underline-offset-2" title={term.plain} tabIndex={0}>
      {term.short}
    </abbr>
  );
}

export default function HowToRead() {
  return (
    <section className="newspaper-card p-5 mb-6">
      <h2 className="font-display text-2xl font-bold">How to read this</h2>
      <p className="mt-2">{HOW_TO_READ}</p>
      <dl className="mt-4 grid gap-3">
        {READING_TERMS.map((term: ReadingTerm) => (
          <div key={term.id}>
            <dt className="font-semibold">{term.title}</dt>
            <dd className="text-[var(--color-muted)]">
              {term.plain}{" "}
              <a className="link text-sm" href={term.source_url} rel="noopener noreferrer">{term.source_name}</a>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
