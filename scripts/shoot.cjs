// Local screenshot helper for manual review.
// Usage: node scripts/shoot.cjs <baseUrl> <prefix> <path1> <path2> ...
// Requires playwright-core (or set PW_CORE to its module path) and a Chromium
// install Playwright can find, or set PLAYWRIGHT_CHROMIUM to the executable.
const { chromium } = require(process.env.PW_CORE || "playwright-core");
const fs = require("fs");
const path = require("path");
(async () => {
  const [base, prefix, ...paths] = process.argv.slice(2);
  const launch = process.env.PLAYWRIGHT_CHROMIUM
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM }
    : {};
  const browser = await chromium.launch(launch);
  const out = [];
  fs.mkdirSync("screenshots", { recursive: true });
  for (const w of [390, 1280]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: w === 390 ? 844 : 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    for (const p of paths) {
      const r = await page.goto(base + p, { waitUntil: "networkidle" });
      const ov = await page.evaluate(() => ({
        sw: document.documentElement.scrollWidth,
        cw: document.documentElement.clientWidth,
        wide: [...document.querySelectorAll("body *")].filter((e) => {
          const b = e.getBoundingClientRect();
          return b.right > document.documentElement.clientWidth + 1 && getComputedStyle(e).position !== "fixed" && !e.closest(".overflow-x-auto");
        }).slice(0, 3).map((e) => e.tagName + "." + (e.className || "").toString().slice(0, 40)),
      }));
      const name = `${prefix}-${(p.replace(/\//g, "_") || "_home").replace(/^_/, "") || "home"}-${w}.png`;
      await page.screenshot({ path: path.join("screenshots", name), fullPage: false });
      out.push({ path: p, width: w, status: r.status(), overflow: ov.sw > ov.cw || ov.wide.length > 0, wide: ov.wide, shot: "screenshots/" + name });
    }
    await ctx.close();
  }
  await browser.close();
  console.log(JSON.stringify(out, null, 1));
})();
