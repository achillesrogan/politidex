// Deploy helper: the source tree and the verified data snapshot ship as one gzipped bundle
// (deploy-bundle.json.gz: {relative path: utf-8 text or {b64}}) that is unpacked before the claim checks and build.
import fs from "node:fs"; import path from "node:path"; import zlib from "node:zlib";
const root = process.cwd();
const bundle = path.join(root, "deploy-bundle.json.gz");
if (!process.env.VERCEL) { console.log("unpack-data: not on Vercel; using files on disk"); process.exit(0); }
if (!fs.existsSync(bundle)) { console.log("unpack-data: no bundle; using files on disk"); process.exit(0); }
const files = JSON.parse(zlib.gunzipSync(fs.readFileSync(bundle)).toString("utf8"));
let n = 0;
for (const [rel, v] of Object.entries(files)) {
  const p = path.resolve(root, rel);
  if (!p.startsWith(root + path.sep)) throw new Error("bad path in bundle");
  fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, typeof v === "string" ? v : Buffer.from(v.b64, "base64")); n++;
}
console.log(`unpack-data: ${n} files unpacked`);
