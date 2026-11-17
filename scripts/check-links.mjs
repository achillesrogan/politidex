// Audit outbound links in rendered HTML. Not part of prebuild: it calls the network.
// Usage: node scripts/check-links.mjs --html <dir> [--rewrite] [--out report.json]
import dns from "node:dns/promises";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { publicSourceHref } from "../lib/source-href.mjs";

export const MAX_REDIRECTS = 5;
export const MAX_BODY = 256 * 1024;
const UA = "Politidex-civic-research/0.1 (+https://politidex.icu; open-source non-profit)";

const EXACT_HOSTS = new Set([
  "fec.gov",
  "www.fec.gov",
  "docquery.fec.gov",
  "www.congress.gov",
  "api.congress.gov",
  "lda.gov",
  "www.senate.gov",
  "clerk.house.gov",
  "www.politidex.icu",
]);

export function hostAllowed(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/\.$/, "");
  if (!host || host.includes("..")) return false;
  if (EXACT_HOSTS.has(host)) return true;
  if (host.endsWith(".senate.gov")) return true;
  if (host.endsWith(".house.gov")) return true;
  return false;
}

export function isBlockedAddress(ip) {
  const mapped = String(ip || "").toLowerCase().match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
  if (mapped) return isBlockedAddress(mapped[1]);
  if (net.isIP(ip) === 4) {
    const parts = ip.split(".").map((n) => Number(n));
    if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return true;
    const [a, b] = parts;
    if (a === 0 || a === 10 || a === 127) return true;
    if (a === 169 && b === 254) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    return false;
  }
  if (net.isIP(ip) === 6) {
    const lower = ip.toLowerCase();
    if (lower === "::1" || lower === "::") return true;
    const first = Number.parseInt(lower.split(":")[0] || "0", 16);
    if (first >= 0xfe80 && first <= 0xfebf) return true;
    if (first >= 0xfc00 && first <= 0xfdff) return true;
    return false;
  }
  return true;
}

export function clampConcurrency(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 4;
  return Math.min(8, Math.max(1, Math.floor(n)));
}

export function clampDelay(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 250;
  return Math.min(5000, Math.max(0, Math.floor(n)));
}

async function defaultLookup(hostname) {
  const records = await dns.lookup(hostname, { all: true, verbatim: true });
  return records.map((row) => row.address);
}

export async function assertPublicHttps(raw, lookup = defaultLookup) {
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new Error("bad url");
  }
  if (url.protocol !== "https:") throw new Error("https required");
  if (url.username || url.password) throw new Error("credentials");
  if (url.port && url.port !== "443") throw new Error("port");
  if (!hostAllowed(url.hostname)) throw new Error("host");
  const addresses = await lookup(url.hostname);
  if (!addresses.length) throw new Error("dns");
  for (const address of addresses) {
    if (isBlockedAddress(address)) throw new Error("private address");
  }
  return url;
}

async function cancel(res) {
  try {
    await res.body?.cancel?.();
  } catch {
    /* already closed */
  }
}

async function readCap(res) {
  const reader = res.body?.getReader?.();
  if (!reader) return "";
  const chunks = [];
  let size = 0;
  while (size < MAX_BODY) {
    const step = await reader.read();
    if (step.done) break;
    const slice = step.value.subarray(0, MAX_BODY - size);
    chunks.push(Buffer.from(slice));
    size += slice.length;
    if (size >= MAX_BODY) {
      await reader.cancel();
      break;
    }
  }
  return Buffer.concat(chunks).toString("utf8");
}

export async function fetchChecked(raw, opts = {}) {
  const fetchImpl = opts.fetchImpl || fetch;
  const lookup = opts.lookup || defaultLookup;
  let current = raw;
  let hops = 0;
  while (true) {
    try {
      await assertPublicHttps(current, lookup);
    } catch (err) {
      return { url: raw, status: 0, final: current, soft: false, blocked: true, ok: false, error: err.message || "blocked" };
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25000);
    let res;
    try {
      res = await fetchImpl(current, {
        redirect: "manual",
        signal: controller.signal,
        headers: { "User-Agent": UA, Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" },
      });
    } catch (err) {
      return { url: raw, status: 0, final: current, soft: false, blocked: false, ok: false, error: err.name || "Error" };
    } finally {
      clearTimeout(timer);
    }
    if (res.status >= 300 && res.status < 400) {
      hops += 1;
      const loc = res.headers.get("location");
      await cancel(res);
      if (hops > MAX_REDIRECTS) {
        return { url: raw, status: res.status, final: current, soft: false, blocked: false, ok: false, error: "too many redirects" };
      }
      if (!loc) {
        return { url: raw, status: res.status, final: current, soft: false, blocked: false, ok: false, error: "redirect without location" };
      }
      current = new URL(loc, current).toString();
      continue;
    }
    const html = await readCap(res);
    const soft = looksSoft404(res.status, html);
    const blocked = res.status === 403 || res.status === 429;
    const ok = res.status >= 200 && res.status < 400 && !soft;
    return { url: raw, status: res.status, final: current, soft, blocked, ok };
  }
}

const SOFT = /page not found|404 error|the page you (?:requested|are looking for)|we can(?:not|’t|') find that page/i;

function looksSoft404(status, html) {
  if (status === 404 || status === 410) return true;
  const title = (html.match(/<title>([^<]{0,180})/i) || [])[1] || "";
  const h1 = (html.match(/<h1[^>]*>([\s\S]{0,240})<\/h1>/i) || [])[1] || "";
  const head = `${title} ${h1.replace(/<[^>]+>/g, " ")}`;
  return SOFT.test(head);
}

function arg(args, name) {
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

function tally(rows) {
  const by = new Map();
  for (const row of rows) {
    let host = "unparsed";
    try { host = new URL(row.url).host; } catch { /* keep */ }
    const key = `${host} ${row.pattern.replace(/^[^/]+/, "")}`;
    if (!by.has(key)) by.set(key, { host, pattern: row.pattern, urls: 0, occurrences: 0, ok: 0, broken: 0, blocked: 0 });
    const t = by.get(key);
    t.urls += 1;
    t.occurrences += row.occurrences;
    if (row.ok) t.ok += 1;
    else if (row.blocked) t.blocked += 1;
    else t.broken += 1;
  }
  return [...by.values()].sort((a, b) => b.broken - a.broken || b.urls - a.urls);
}

async function main() {
  const args = process.argv.slice(2);
  const htmlDir = arg(args, "--html") || path.join(process.cwd(), ".next");
  const outPath = arg(args, "--out") || "";
  const rewrite = args.includes("--rewrite");
  const delayMs = clampDelay(arg(args, "--delay") || 250);
  const concurrency = clampConcurrency(arg(args, "--concurrency") || 4);
  const files = walk(htmlDir);
  const found = new Map();
  for (const file of files) {
    const html = fs.readFileSync(file, "utf8");
    for (const m of html.matchAll(/href="(https?:\/\/[^"]+)"/g)) {
      let href = decode(m[1]);
      if (rewrite) href = publicSourceHref(href) || href;
      if (!found.has(href)) found.set(href, { count: 0 });
      found.get(href).count += 1;
    }
  }
  const urls = [...found.keys()];
  const hostNext = new Map();
  async function limited(url) {
    let host = "unknown";
    try { host = new URL(url).host; } catch { /* keep */ }
    const wait = Math.max(0, (hostNext.get(host) || 0) - Date.now());
    hostNext.set(host, Date.now() + wait + delayMs);
    if (wait) await new Promise((r) => setTimeout(r, wait));
    return fetchChecked(url);
  }
  const results = [];
  let cursor = 0;
  async function worker() {
    while (cursor < urls.length) {
      const url = urls[cursor++];
      const row = await limited(url);
      results.push({ ...row, pattern: patternOf(row.final || url), occurrences: found.get(url).count });
      if (results.length % 100 === 0) console.error(`checked ${results.length}/${urls.length}`);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, () => worker()));
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
  const text = JSON.stringify({ summary, broken }, null, 1);
  if (outPath) fs.writeFileSync(outPath, text);
  console.log(JSON.stringify(summary, null, 1));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
