import assert from "node:assert/strict";
import test from "node:test";
import { reviewCareerPages } from "../scripts/check-rendered.mjs";

const bad = `<span data-career-fact="" data-source="https://api.congress.gov/v3/member/S000033" data-retrieved="2026-11-17T00:00:00Z"></span>`;
const good = `<div data-career-section=""><span data-career-fact="" data-source="https://www.congress.gov/member/S000033" data-retrieved="2026-11-17T00:00:00Z"></span></div>`;

test("a page with no bioguide id may omit the career section", () => {
  const people = new Map([["donald-j-trump", { slug: "donald-j-trump", bioguide: null }]]);
  const result = reviewCareerPages([{ slug: "donald-j-trump", html: "<article></article>" }], people);
  assert.deepEqual(result.errors, []);
});

test("a page with no bioguide id still rejects a bad career source", () => {
  const people = new Map([["donald-j-trump", { slug: "donald-j-trump", bioguide: null }]]);
  const result = reviewCareerPages([{ slug: "donald-j-trump", html: bad }], people);
  assert.equal(result.facts, 1);
  assert.ok(result.errors.some((error) => error.includes("source")));
});

test("a bioguide page must include the career section", () => {
  const people = new Map([["bernard-sanders", { slug: "bernard-sanders", bioguide: "S000033" }]]);
  const missing = reviewCareerPages([{ slug: "bernard-sanders", html: "<article></article>" }], people);
  assert.ok(missing.errors.some((error) => error.includes("missing the career record")));
  const present = reviewCareerPages([{ slug: "bernard-sanders", html: good }], people);
  assert.deepEqual(present.errors, []);
});
