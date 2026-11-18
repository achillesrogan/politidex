// Pre-deploy guard. Fails when a file the Vercel CLI would upload is over 100 MB,
// or when that set is over 5,000 files and the deploy is not `vercel deploy --archive=tgz`.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const MAX_FILE_BYTES = 100_000_000;
export const MAX_FILES_WITHOUT_ARCHIVE = 5000;
const SKIP_DIRS = new Set([".git", ".vercel", "node_modules", ".next", "__pycache__"]);

export function parseIgnore(text) {
  const rules = [];
  for (const raw of String(text || "").split(/\n/)) {
    let line = raw.replace(/\r$/, "");
    if (!line || line.startsWith("#")) continue;
    let negate = false;
    if (line.startsWith("!")) {
      negate = true;
      line = line.slice(1);
    }
    if (line.startsWith("\\#") || line.startsWith("\\!")) line = line.slice(1);
    const dirOnly = line.endsWith("/");
    if (dirOnly) line = line.slice(0, -1);
    const anchored = line.startsWith("/");
    if (anchored) line = line.slice(1);
    rules.push({ negate, dirOnly, anchored: anchored || line.includes("/"), pattern: line });
  }
  return rules;
}

function globToRegExp(pattern) {
  let body = "";
  for (let i = 0; i < pattern.length; i++) {
    const char = pattern[i];
    if (char === "*") {
      if (pattern[i + 1] === "*") {
        body += ".*";
        i += 1;
        if (pattern[i + 1] === "/") i += 1;
      } else body += "[^/]*";
    } else if (char === "?") body += "[^/]";
    else if (".+^${}()|[]\\".includes(char)) body += "\\" + char;
    else body += char;
  }
  return body;
}

function ruleMatches(rule, relPath) {
  if (rule.dirOnly) return relPath === rule.pattern || relPath.startsWith(rule.pattern + "/");
  const body = globToRegExp(rule.pattern);
  const re = rule.anchored ? new RegExp("^" + body + "$") : new RegExp("(^|/)" + body + "$");
  if (re.test(relPath)) return true;
  if (!rule.anchored) {
    const parts = relPath.split("/");
    for (let i = 0; i < parts.length - 1; i++) {
      if (new RegExp("^" + body + "$").test(parts[i])) return true;
    }
  }
  return false;
}

export function isIgnored(relPath, rules) {
  let ignored = false;
  for (const rule of rules) {
    if (ruleMatches(rule, relPath)) ignored = !rule.negate;
  }
  return ignored;
}

export function listUploadFiles(root, ignoreText) {
  const rules = parseIgnore(ignoreText);
  const files = [];
  function walk(dir, rel) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const relPath = rel ? rel + "/" + entry.name : entry.name;
      if (entry.isSymbolicLink()) throw new Error(relPath + " is a symlink");
      if (SKIP_DIRS.has(entry.name) || entry.name === ".DS_Store") continue;
      if (entry.isDirectory()) {
        if (!isIgnored(relPath, rules)) walk(path.join(dir, entry.name), relPath);
        else if (rules.some((rule) => rule.negate && (rule.pattern === relPath || rule.pattern.startsWith(relPath + "/")))) {
          walk(path.join(dir, entry.name), relPath);
        }
        continue;
      }
      if (!entry.isFile() || isIgnored(relPath, rules)) continue;
      files.push({ path: relPath, size: fs.statSync(path.join(dir, entry.name)).size });
    }
  }
  walk(root, "");
  return files;
}

export function evaluateUpload(files, { archiveTgz = false } = {}) {
  const errors = [];
  for (const file of files) {
    if (file.size > MAX_FILE_BYTES) errors.push(file.path + " is over 100 MB (" + file.size + " bytes)");
  }
  if (!archiveTgz && files.length > MAX_FILES_WITHOUT_ARCHIVE) {
    errors.push(files.length + " files would be uploaded; use vercel deploy --archive=tgz when the set is over " + MAX_FILES_WITHOUT_ARCHIVE);
  }
  return errors;
}

function main() {
  const archiveTgz = process.argv.includes("--archive=tgz");
  const root = process.cwd();
  const ignorePath = path.join(root, ".vercelignore");
  const ignoreText = fs.existsSync(ignorePath) ? fs.readFileSync(ignorePath, "utf8") : "";
  const files = listUploadFiles(root, ignoreText);
  const errors = evaluateUpload(files, { archiveTgz });
  const largest = files.reduce((best, file) => file.size > best.size ? file : best, { path: "", size: 0 });
  console.log("check-upload: " + files.length + " files, largest " + largest.size + " bytes" + (largest.path ? " (" + largest.path + ")" : ""));
  if (errors.length) {
    console.error(errors.slice(0, 20).join("\n"));
    console.error("check-upload FAILED: " + errors.length + " problems");
    process.exit(1);
  }
  console.log("check-upload: OK");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
