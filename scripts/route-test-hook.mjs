/** Resolve @/ and extensionless Next imports so node:test can call route handlers. */
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    return nextResolve(pathToFileURL(path.join(root, specifier.slice(2))).href, context);
  }
  if (specifier === "next/server") {
    return nextResolve(pathToFileURL(path.join(root, "node_modules/next/server.js")).href, context);
  }
  return nextResolve(specifier, context);
}
