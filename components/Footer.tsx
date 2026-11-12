import Link from "next/link";
import { NAV, SITE } from "@/lib/site";
export default function Footer() {
  return (
    <footer className="mt-16 border-t-4 border-double border-[var(--color-ink)] bg-[var(--color-paper-2)]">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10 grid gap-8 sm:grid-cols-3">
        <div>
          <div className="font-display text-2xl font-black masthead-shadow">POLITIDEX</div>
          <p className="mt-2 text-[var(--color-muted)]">Open-source, non-profit, public-interest research. Every fact links to a public record. Code is licensed under AGPL-3.0; original data compilations under CC BY 4.0 where source terms allow.</p>
          <p className="mt-2"><a className="link" href="https://github.com/achillesrogan/politidex" rel="noopener noreferrer">Source code on GitHub</a></p>
        </div>
        <div>
          <h2 className="tag mb-2">Sections</h2>
          <ul className="grid grid-cols-2 gap-1">
            {NAV.map((n) => <li key={n.href}><Link className="hover:underline" href={n.href}>{n.label}</Link></li>)}
            <li><Link className="hover:underline" href="/privacy">Privacy</Link></li>
            <li><Link className="hover:underline" href="/terms">Terms</Link></li>
            <li><Link className="hover:underline" href="/definitions">Definitions</Link></li>
          </ul>
        </div>
        <div>
          <h2 className="tag mb-2">Contact</h2>
          <p>Editorial: <a className="link" href={`mailto:${SITE.editorEmail}`}>{SITE.editorEmail}</a></p>
          <p>Corrections: <a className="link" href={`mailto:${SITE.correctionsEmail}`}>{SITE.correctionsEmail}</a></p>
          <p className="mt-2 text-sm text-[var(--color-muted)]">No physical office. We do not accept tips containing private personal information about non-public individuals.</p>
        </div>
      </div>
      <div className="border-t border-[var(--color-rule)] text-center text-sm py-4 text-[var(--color-muted)]">
        © {new Date().getFullYear()} Politidex contributors · Code AGPL-3.0 · Original data compilations CC BY 4.0 where source terms allow
      </div>
    </footer>
  );
}
