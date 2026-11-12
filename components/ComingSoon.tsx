import Link from "next/link";
export default function ComingSoon({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <section className="newspaper-card paper-crease p-6 sm:p-10 max-w-3xl">
      <div className="tag text-[var(--color-analysis)]">In development</div>
      <h1 className="font-display text-3xl sm:text-4xl font-black mt-2">{title}</h1>
      <div className="prose-news mt-4">{children}</div>
      <p className="mt-6"><Link className="link" href="/methodology">Read how Politidex verifies every claim →</Link></p>
    </section>
  );
}
