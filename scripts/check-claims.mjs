// Prebuild gate: every claim referenced by site data must exist and carry source URL, retrieval time, excerpt and a check spec.
import fs from "node:fs"; import path from "node:path";
const DIR = path.join(process.cwd(), "data", "build", "site");
if (process.env.POLITIDEX_DATA === "0" || !fs.existsSync(path.join(DIR, "claims.json"))) { console.log("check-claims: data disabled or absent; nothing to check"); process.exit(0); }
const claims = JSON.parse(fs.readFileSync(path.join(DIR, "claims.json"), "utf8")).claims;
const errors = []; let refs = 0;
const walk = (o, where) => {
  if (Array.isArray(o)) return o.forEach((x) => walk(x, where));
  if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) {
    if ((k === "claim" || k === "sponsor_claim") && typeof v === "string") {
      refs++; const c = claims[v];
      if (!c) errors.push(`${where}: missing claim ${v}`);
      else for (const f of ["source_url", "retrieved_at", "excerpt", "check", "status"]) if (!c[f]) errors.push(`${where}: claim ${v} lacks ${f}`);
    } else walk(v, where);
  }
};
for (const f of fs.readdirSync(path.join(DIR, "profiles"))) walk(JSON.parse(fs.readFileSync(path.join(DIR, "profiles", f), "utf8")), f);
walk(JSON.parse(fs.readFileSync(path.join(DIR, "connections.json"), "utf8")), "connections.json");
if (fs.existsSync(path.join(DIR, "elections.json"))) walk(JSON.parse(fs.readFileSync(path.join(DIR, "elections.json"), "utf8")), "elections.json");
if (fs.existsSync(path.join(DIR, "on-the-record.json"))) walk(JSON.parse(fs.readFileSync(path.join(DIR, "on-the-record.json"), "utf8")), "on-the-record.json");
const st = Object.values(claims).reduce((a, c) => ((a[c.status] = (a[c.status] || 0) + 1), a), {});
console.log(`check-claims: ${refs} references, claim status ${JSON.stringify(st)}`);
if (errors.length) { console.error(errors.slice(0, 50).join("\n")); console.error(`check-claims FAILED: ${errors.length} problems`); process.exit(1); }
