// Deploy helper: the source tree and the verified data snapshot ship as gzipped bundles
// (deploy-bundle.json.gz and deploy-bundle-*.json.gz: {relative path: utf-8 text or {b64}})
// that are unpacked before the claim checks and build. Split parts are used so each file
// stays within upload limits; all parts are merged on Vercel.
import fs from "node:fs"; import path from "node:path"; import zlib from "node:zlib";
const root = process.cwd();
if (!process.env.VERCEL) { console.log("unpack-data: not on Vercel; using files on disk"); process.exit(0); }
const bundles = fs.readdirSync(root)
  .filter((f) => f === "deploy-bundle.json.gz" || /^deploy-bundle-.*\.json\.gz$/.test(f))
  .map((f) => path.join(root, f));
if (!bundles.length) { console.log("unpack-data: no bundle; using files on disk"); process.exit(0); }
let n = 0;
for (const bundle of bundles) {
  const files = JSON.parse(zlib.gunzipSync(fs.readFileSync(bundle)).toString("utf8"));
  for (const [rel, v] of Object.entries(files)) {
    const p = path.resolve(root, rel);
    if (!p.startsWith(root + path.sep)) throw new Error("bad path in bundle");
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, typeof v === "string" ? v : Buffer.from(v.b64, "base64"));
    n++;
  }
}
console.log(`unpack-data: ${n} files unpacked from ${bundles.length} bundles`);
