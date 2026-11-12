export const SITE = {
  name: "Politidex",
  url: "https://www.politidex.icu",
  tagline: "An open-source public record of who holds power in the United States, and how they are connected.",
  editorEmail: "editor@politidex.icu",
  correctionsEmail: "corrections@politidex.icu",
  dataEnabled: process.env.POLITIDEX_DATA !== "0",
};
export const NAV = [
  { href: "/", label: "Home" },
  { href: "/people", label: "People" },
  { href: "/connections", label: "Connections" },
  { href: "/politi-matrix", label: "Politi-Matrix" },
  { href: "/methodology", label: "Methodology" },
  { href: "/data-sources", label: "Data Sources" },
  { href: "/corrections", label: "Corrections" },
  { href: "/about", label: "About" },
];
