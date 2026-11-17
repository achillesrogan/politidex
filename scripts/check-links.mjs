// Audit outbound http(s) links in rendered HTML. Not part of prebuild: it calls the network.
// Usage: node scripts/check-links.mjs --html <dir> [--rewrite] [--out report.json]
import fs from "node:fs";
import path from "node:path";
import { publicSourceHref } from "../lib/source-href.mjs";

const args = process.argv.slice(2);
const htmlDir = arg("--html") || path.join(process.cwd(), ".next");
const outPath = arg("--out") || "";
const rewrite = args.includes("--rewrite");
const delayMs = Number(arg("--delay") || 250);
const concurrency = Number(arg("--concurrency") || 4);
const UA = "Politidex-civic-research/0.1 (+https://politidex.icu; open-source non-profit)";

function arg(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : "";
}

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p, acc);
    else if (ent.name.endsWith(".html")) acc.push(p);
  }
  return acc;
}

function decode(href) {
  return href.replace(/&amp;/g, "&").replace(/&#x27;/g, "'").replace(/&quot;/g, '"');
}

function patternOf(raw) {
  let url;
  try { url = new URL(raw); } catch { return "unparsed"; }
  const pathName = url.pathname
    .replace(/\/[A-Z][0-9A-Z]{7,8}(?=\/|$)/gi, "/:id")
    .replace(/committee_memberships_[A-Z0-9]+\.(xml|htm)/gi, "committee_memberships_:code.$1")
    .replace(/\/\d{2,}/g, "/:n");
  const keys = [...url.searchParams.keys()].sort();
  const query = keys.length ? "?" + keys.join("&") : "";
  return `${url.host}${pathName}${query}`;
}

const SOFT = /page not found|404 error|the page you (?:requested|are looking for)|we can(?:not|’t|') find that page/i;

function looksSoft404(status, html) {
  if (status === 404 || status === 410) return true;
  const title = (html.match(/<title>([^<]{0,180})/i) || [])[1] || "";
  const h1 = (html.match(/<h1[^>]*>([\s\S]{0,240})<\/h1>/i) || [])[1] || "";
  const head = `${title} ${h1.replace(/<[^>]+>/g, " ")}`;
  return SOFT.test(head);
}

async function checkOne(raw) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const res = await fetch(raw, {
      redirect: "follow",
      signal: controller.signal,
      headers: { "User-Agent": UA, Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" },
    });
    const buf = await res.arrayBuffer();
    const html = Buffer.from(buf.slice(0, 20000)).toString("utf8");
    const soft = looksSoft404(res.status, html);
    const blocked = res.status === 403 || res.status === 429;
    const ok = res.status >= 200 && res.status < 400 && !soft;
    return { url: raw, status: res.status, final: res.url, soft, blocked, ok };
  } catch (err) {
    return { url: raw, status: 0, final: raw, soft: false, blocked: false, ok: false, error: err.name || "Error" };
  } finally {
    clearTimeout(timer);
  }
}

const files = walk(htmlDir);
const found = new Map();
for (const file of files) {
  const html = fs.readFileSync(file, "utf8");
  for (const m of html.matchAll(/href="(https?:\/\/[^"]+)"/g)) {
    let href = decode(m[1]);
    if (rewrite) href = publicSourceHref(href) || href;
    if (!found.has(href)) found.set(href, { count: 0, pages: 0 });
    const row = found.get(href);
    row.count += 1;
  }
}

const urls = [...found.keys()];
const hostNext = new Map();
async function limited(url) {
  const host = new URL(url).host;
  const wait = Math.max(0, (hostNext.get(host) || 0) - Date.now());
  hostNext.set(host, Date.now() + wait + delayMs);
  if (wait) await new Promise((r) => setTimeout(r, wait));
  return checkOne(url);
}

const results = [];
let cursor = 0;
async function worker() {
  while (cursor < urls.length) {
    const url = urls[cursor++];
    const row = await limited(url);
    results.push({ ...row, pattern: patternOf(row.url), occurrences: found.get(url).count });
    if (results.length % 100 === 0) console.error(`checked ${results.length}/${urls.length}`);
  }
}
await Promise.all(Array.from({ length: concurrency }, () => worker()));

function tally(rows) {
  const by = new Map();
  for (const row of rows) {
    const key = `${new URL(row.url).host} ${row.pattern.replace(/^[^/]+/, "")}`;
    if (!by.has(key)) by.set(key, { host: new URL(row.url).host, pattern: row.pattern, urls: 0, occurrences: 0, ok: 0, broken: 0, blocked: 0 });
    const t = by.get(key);
    t.urls += 1;
    t.occurrences += row.occurrences;
    if (row.ok) t.ok += 1;
    else if (row.blocked) t.blocked += 1;
    else t.broken += 1;
  }
  return [...by.values()].sort((a, b) => b.broken - a.broken || b.urls - a.urls);
}

const summary = {
  pages: files.length,
  unique_urls: urls.length,
  ok: results.filter((r) => r.ok).length,
  broken: results.filter((r) => !r.ok && !r.blocked).length,
  blocked: results.filter((r) => r.blocked).length,
  rewrite,
  by_pattern: tally(results),
};
const broken = results.filter((r) => !r.ok && !r.blocked).map((r) => ({ url: r.url, status: r.status, soft: r.soft, error: r.error || "", pattern: r.pattern, occurrences: r.occurrences }));
const report = { summary, broken };
const text = JSON.stringify(report, null, 1);
if (outPath) fs.writeFileSync(outPath, text);
console.log(JSON.stringify(summary, null, 1));
