import Link from "next/link";
import { NAV } from "@/lib/site";
export default function Nav() {
  return (
    <header className="border-b border-[var(--color-rule)] bg-[var(--color-paper)]/95">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Link href="/" className="font-display text-2xl font-black tracking-tight masthead-shadow">POLITIDEX</Link>
        <nav aria-label="Main" className="flex flex-wrap gap-x-4 gap-y-1 text-[0.95rem]">
          {NAV.slice(1).map((n) => (
            <Link key={n.href} href={n.href} className="hover:underline underline-offset-4">{n.label}</Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
