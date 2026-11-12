// Headless fetch for official results sites that only work in a browser.
// usage: node browser_fetch.cjs <pageUrl> <dataUrl|"text"> [waitMs]
//  dataUrl: loads pageUrl, then fetches dataUrl from inside the page (same origin) and prints the body.
//  "text":  prints document.body.innerText after the page settles.
// Requires playwright-core, or set PW_CORE to its module path.
let pw;
try {
  pw = require(process.env.PW_CORE || "playwright-core");
} catch (err) {
  process.stderr.write("Install playwright-core (or set PW_CORE to its module path)\n");
  process.exit(3);
}
(async () => {
  const [pageUrl, what, waitMs] = process.argv.slice(2);
  const b = await pw.chromium.launch();
  try {
    const p = await b.newPage({ userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36" });
    try { await p.goto(pageUrl, { waitUntil: "networkidle", timeout: 60000 }); } catch (e) {}
    await p.waitForTimeout(Number(waitMs || 4000));
    let out;
    if (what === "text") out = await p.evaluate(() => document.body.innerText);
    else out = await p.evaluate(async (u) => { const r = await fetch(u, { credentials: "include" }); if (!r.ok) return ""; return await r.text(); }, what);
    if (!out) process.exit(2);
    process.stdout.write(out);
  } finally { await b.close(); }
})().catch((e) => { process.stderr.write(String(e).slice(0, 300)); process.exit(3); });
