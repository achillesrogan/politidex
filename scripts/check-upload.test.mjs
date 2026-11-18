import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { evaluateUpload, isIgnored, listUploadFiles, MAX_FILE_BYTES, MAX_FILES_WITHOUT_ARCHIVE, parseIgnore } from "./check-upload.mjs";

const repoIgnore = parseIgnore(readFileSync(new URL("../.vercelignore", import.meta.url), "utf8"));

test("the Vercel ignore list drops connection intermediates and keeps the site snapshot", () => {
  assert.equal(isIgnored("data/build/connections-fec.json", repoIgnore), true);
  assert.equal(isIgnored("data/build/fec-2026.json", repoIgnore), true);
  assert.equal(isIgnored("data/build/site/claims.json", repoIgnore), false);
  assert.equal(isIgnored("data/people/review.json", repoIgnore), false);
  assert.equal(isIgnored("data/people/other.json", repoIgnore), true);
  assert.equal(isIgnored("data/raw/fec/cm26.zip", repoIgnore), true);
});

test("a file over 100 MB fails even when the deploy is one archive", () => {
  const files = [{ path: "data/build/connections-fec.json", size: MAX_FILE_BYTES + 1 }];
  assert.ok(evaluateUpload(files, { archiveTgz: true }).some((error) => error.includes("100 MB")));
  assert.deepEqual(evaluateUpload([{ path: "ok.json", size: MAX_FILE_BYTES }], { archiveTgz: false }), []);
});

test("more than 5000 files requires vercel deploy --archive=tgz", () => {
  const files = Array.from({ length: MAX_FILES_WITHOUT_ARCHIVE + 1 }, (_, i) => ({ path: "f" + i, size: 1 }));
  assert.equal(evaluateUpload(files, { archiveTgz: false }).length, 1);
  assert.deepEqual(evaluateUpload(files, { archiveTgz: true }), []);
});

test("a fixture upload honors .vercelignore", () => {
  const root = mkdtempSync(path.join(tmpdir(), "upload-"));
  mkdirSync(path.join(root, "data/build/site"), { recursive: true });
  mkdirSync(path.join(root, "node_modules/pkg"), { recursive: true });
  writeFileSync(path.join(root, ".vercelignore"), "data/build/connections-*.json\n");
  writeFileSync(path.join(root, "data/build/site/claims.json"), "{}");
  writeFileSync(path.join(root, "data/build/connections-fec.json"), "{}");
  writeFileSync(path.join(root, "node_modules/pkg/index.js"), "module.exports = {}\n");
  const files = listUploadFiles(root, readFileSync(path.join(root, ".vercelignore"), "utf8"));
  assert.deepEqual(files.map((file) => file.path).sort(), [".vercelignore", "data/build/site/claims.json"]);
});
