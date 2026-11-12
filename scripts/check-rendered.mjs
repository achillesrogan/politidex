// Postbuild gate (CI): scan every prerendered HTML page. Fails if any rendered fact lacks a verified claim,
// or if OPSEC / launch-safety rules are violated.
import fs from "node:fs"; import path from "node:path";
const root = path.join(process.cwd(), ".next");
const claimsPath = process.env.CLAIMS_PATH || path.join(process.cwd(), "data", "build", "site", "claims.json");
const claims = fs.existsSync(claimsPath) ? JSON.parse(fs.readFileSync(claimsPath, "utf8")).claims : {};
const files = []; const walk = (d) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); e.isDirectory() ? walk(p) : files.push(p); } };
walk(root);
const html = files.filter((f) => f.endsWith(".html"));
const errors = []; let facts = 0;
const BANNED = [/politidex\.com/i, /\(?\d{3}\)?[ -]555-\d{4}/, /123 Soon/i, /Political Intelligence Ave/i, /example\.com/i, /DEMO_KEY/, /api_key=/i];
// Private identifiers (maintainer's personal names/handles) are kept OUT of the repo: one regex-safe term per line in
// .opsec-denylist (gitignored) and/or comma-separated in env OPSEC_DENYLIST. Values are never printed.
const privateTerms = [
  ...(fs.existsSync(path.join(process.cwd(), ".opsec-denylist")) ? fs.readFileSync(path.join(process.cwd(), ".opsec-denylist"), "utf8").split("\n") : []),
  ...(process.env.OPSEC_DENYLIST || "").split(","),
].map((t) => t.trim()).filter(Boolean);
const PRIVATE = privateTerms.map((t) => new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"));
if (!PRIVATE.length) console.warn("check-rendered: WARNING no private denylist loaded (.opsec-denylist or OPSEC_DENYLIST)");

// On the record / side-by-side pages: ban causal or loaded wording in this section only.
const SBS_BANNED = /\b(instead|skipped|chose|because|ditched|snubbed)\b/i;
const isSbs = (f) => /(?:^|[\/\\])on-the-record(?:[\/\\.]|$)/i.test(f);
for (const f of html) {
  const t = fs.readFileSync(f, "utf8");
  for (const m of t.matchAll(/<[a-z]+[^>]*data-fact=""[^>]*>/g)) {
    facts++;
    const id = (m[0].match(/data-claim="([^"]+)"/) || [])[1];
    const c = id && claims[id];
    if (!c) errors.push(`${path.relative(root, f)}: fact without claim (${m[0].slice(0, 80)})`);
    else if (c.status !== "verified" || !c.source_url || !c.retrieved_at || !c.excerpt) errors.push(`${path.relative(root, f)}: claim ${id} not verified`);
  }
  const builtin = /server[\/]pages[\/](500|404)\.html$/.test(f); // Next built-in error pages; covered by X-Robots-Tag header
  if (!builtin && !/<meta name="robots" content="noindex, nofollow/.test(t)) errors.push(`${path.relative(root, f)}: missing noindex`);
  for (const b of BANNED) if (b.test(t)) errors.push(`${path.relative(root, f)}: banned pattern ${b}`);
  // The official public repo URL is printed in the footer / About by design; do not treat it as an OPSEC hit.
  const scanned = t.replace(/https:\/\/github\.com\/achillesrogan\/politidex/gi, "[official-source-repo]");
  PRIVATE.forEach((b, i) => { if (b.test(scanned)) errors.push(`${path.relative(root, f)}: private denylist term #${i + 1} found`); });
  if (isSbs(f)) {
    const text = t.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " ");
    const m = text.match(SBS_BANNED);
    if (m) errors.push(`${path.relative(root, f)}: on-the-record banned wording "${m[0]}"`);
  }
}
for (const f of files) if (f.endsWith(".map") && f.includes(`${path.sep}static${path.sep}`)) errors.push(`source map shipped: ${path.relative(root, f)}`);
for (const f of files.filter((f) => f.includes(`${path.sep}static${path.sep}`) && f.endsWith(".js"))) {
  const t = fs.readFileSync(f, "utf8"); if (/api_key=|X-Api-Key|DATA_GOV_API_KEY/.test(t)) errors.push(`possible secret reference in client bundle: ${path.relative(root, f)}`);
}
console.log(`check-rendered: ${html.length} HTML pages, ${facts} rendered facts checked, ${PRIVATE.length} private denylist terms`);
if (errors.length) { console.error(errors.slice(0, 60).join("\n")); console.error(`check-rendered FAILED: ${errors.length} problems`); process.exit(1); }
console.log("check-rendered: OK — every rendered fact has a verified source; OPSEC patterns clean; noindex present");
