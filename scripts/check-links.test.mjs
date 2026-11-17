import assert from "node:assert/strict";
import test from "node:test";
import {
  MAX_BODY,
  assertPublicHttps,
  clampConcurrency,
  clampDelay,
  fetchChecked,
  hostAllowed,
  isBlockedAddress,
} from "./check-links.mjs";

const publicLookup = async () => ["8.8.8.8"];

test("only the official hosts are allowed", () => {
  assert.equal(hostAllowed("www.fec.gov"), true);
  assert.equal(hostAllowed("docquery.fec.gov"), true);
  assert.equal(hostAllowed("api.congress.gov"), true);
  assert.equal(hostAllowed("lda.gov"), true);
  assert.equal(hostAllowed("www.budget.senate.gov"), true);
  assert.equal(hostAllowed("clerk.house.gov"), true);
  assert.equal(hostAllowed("mace.house.gov"), true);
  assert.equal(hostAllowed("www.politidex.icu"), true);
  assert.equal(hostAllowed("example.com"), false);
  assert.equal(hostAllowed("fec.gov.evil.example"), false);
  assert.equal(hostAllowed("169.254.169.254"), false);
});

test("private, loopback, and link-local addresses are blocked", () => {
  for (const ip of ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.1.1", "169.254.169.254", "::1", "fe80::1", "fd00::1", "::ffff:127.0.0.1", "::ffff:169.254.169.254"]) {
    assert.equal(isBlockedAddress(ip), true, ip);
  }
  assert.equal(isBlockedAddress("8.8.8.8"), false);
  assert.equal(isBlockedAddress("2606:4700:4700::1111"), false);
});

test("concurrency stays between 1 and 8 and delay stays bounded", () => {
  assert.equal(clampConcurrency(0), 1);
  assert.equal(clampConcurrency(99), 8);
  assert.equal(clampConcurrency("nope"), 4);
  assert.equal(clampDelay(-5), 0);
  assert.equal(clampDelay(999999), 5000);
});

test("https on an official host is accepted only when DNS is public", async () => {
  await assertPublicHttps("https://www.fec.gov/data/candidate/S4VT00033/", publicLookup);
  await assert.rejects(() => assertPublicHttps("http://www.fec.gov/", publicLookup), /https/);
  await assert.rejects(() => assertPublicHttps("https://www.fec.gov/", async () => ["169.254.169.254"]), /private/);
  await assert.rejects(() => assertPublicHttps("https://example.com/", publicLookup), /host/);
});

test("a redirect onto a private or non-https host is not fetched", async () => {
  const seen = [];
  const fetchImpl = async (url) => {
    seen.push(url);
    return { status: 302, headers: { get: () => "http://169.254.169.254/latest/meta-data/" }, body: null };
  };
  const result = await fetchChecked("https://www.fec.gov/start", { fetchImpl, lookup: publicLookup });
  assert.deepEqual(seen, ["https://www.fec.gov/start"]);
  assert.equal(result.ok, false);
  assert.equal(result.blocked, true);
});

test("more than five redirects stops", async () => {
  let n = 0;
  const fetchImpl = async () => {
    n += 1;
    return { status: 302, headers: { get: () => "https://www.fec.gov/next" }, body: null };
  };
  const result = await fetchChecked("https://www.fec.gov/start", { fetchImpl, lookup: publicLookup });
  assert.equal(n, 6);
  assert.equal(result.error, "too many redirects");
});

test("the body read stops at 256 KB", async () => {
  const fetchImpl = async () => ({
    status: 200,
    headers: { get: () => null },
    body: {
      getReader() {
        let sent = false;
        return {
          async read() {
            if (sent) return { done: true, value: undefined };
            sent = true;
            return { done: false, value: new Uint8Array(MAX_BODY + 50000) };
          },
          async cancel() {},
        };
      },
    },
  });
  const result = await fetchChecked("https://www.senate.gov/committees/", { fetchImpl, lookup: publicLookup });
  assert.equal(result.ok, true);
});
