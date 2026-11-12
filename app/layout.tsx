import type { Metadata, Viewport } from "next";
import { Playfair_Display, Crimson_Text } from "next/font/google";
import "./globals.css";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { SITE } from "@/lib/site";

const playfair = Playfair_Display({ subsets: ["latin"], variable: "--font-playfair", display: "swap" });
const crimson = Crimson_Text({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-crimson", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: { default: "Politidex — The public record of power", template: "%s · Politidex" },
  description: SITE.tagline,
  applicationName: "Politidex",
  robots: { index: false, follow: false, nocache: true, googleBot: { index: false, follow: false } },
  alternates: { canonical: "/" },
  openGraph: { type: "website", siteName: "Politidex", url: SITE.url, title: "Politidex — The public record of power",
    description: SITE.tagline, images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Politidex" }] },
  twitter: { card: "summary_large_image", title: "Politidex — The public record of power", description: SITE.tagline, images: ["/og-image.png"] },
  icons: { icon: [{ url: "/favicon.ico" }, { url: "/icon.svg", type: "image/svg+xml" }], apple: "/apple-touch-icon.png" },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f8f6f0" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${playfair.variable} ${crimson.variable}`}>
      <body className="min-h-screen antialiased">
        <Nav />
        <div className="border-b border-[var(--color-rule)] bg-[#fff8e1] text-center px-4 py-2 text-sm font-sans text-[#5c4400]">
          <strong>In development.</strong> Politidex is an early, unlaunched build. Coverage is incomplete, and every fact shown links to its public source.
        </div>
        <main className="mx-auto w-full max-w-6xl px-4 sm:px-6 py-8">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
