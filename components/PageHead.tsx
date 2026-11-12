export default function PageHead({ kicker, title, dek }: { kicker?: string; title: string; dek?: string }) {
  return (
    <header className="mb-8 border-b-4 border-double border-[var(--color-ink)] pb-4">
      {kicker && <div className="tag text-[var(--color-muted)]">{kicker}</div>}
      <h1 className="font-display text-3xl sm:text-5xl font-black leading-tight mt-1 masthead-shadow">{title}</h1>
      {dek && <p className="mt-3 text-xl text-[var(--color-muted)] max-w-3xl">{dek}</p>}
    </header>
  );
}
