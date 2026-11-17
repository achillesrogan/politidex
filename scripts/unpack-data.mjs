// A git build has no data/build/site and no deploy bundle, so this script leaves the
// tree unchanged and the site is empty. A CLI deploy uploads the already unpacked
// data/build/site snapshot. The gzipped bundles are not uploaded. See docs/DEPLOY.md.
// If a bundle is present and VERCEL is set, unpack it before the claim checks.
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
