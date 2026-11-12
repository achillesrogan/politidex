# Politidex — build plan

_Last updated: November 12, 2026. Status: Phase A + Phase B (federal profiles, the Connections panel, and organization pages) are in production at https://www.politidex.icu (the apex domain redirects to www); noindex is on. Election results are not part of the site. The maintainer approves every deploy._

## Current status (checkpoint)
- Phase A: complete and verified (`POLITIDEX_DATA=0 npm run build` → 18 pages, CI OK).
- Phase B: federal profiles and connections for current officeholders. 562 profiles (100 senators, 433 representatives,
  5 delegates + 1 resident commissioner, President, VP, 21 Cabinet-level officials per whitehouse.gov),
  1,600 roll calls. Connections panel (committee contributions, lobbying-disclosure matches,
  independent expenditures, covered-position records) and organization pages deployed
  November 12, 2026, about 08:15 UTC. **64,067 claims verified, 0 blocked** (connections-stage
  live re-check, November 12, 2026, 06:42 UTC).
- Independent spot-check (second source, 20 profiles, 2 random samples): 99/99 checks pass
  (`data/build/spotcheck-sample-seed*.txt`). Gap: senators' joint-committee seats are not yet ingested.
- Review queue: 562 template-drafted summaries `pending_review`, 0 approved, so none render.
- Verified-claims checkpoint copy: `data/build/claims-verified-checkpoint.json`.

## Mission
An open-source, non-profit public record of who holds power in the United States and how they are connected —
every claim backed by a credible, verifiable primary source. Long-term scope: all U.S. politicians and candidates,
federal, state, and local.

---

## Verification Standard (top QC priority: zero hallucinations)

No summary, fact, connection, or edge may exist without verifiable proof from a credible primary source.

1. **Claim objects.** Every fact is a claim object with: stable ID, plain-language text, value, **source URL**,
   **retrieved-at time (UTC)**, the **exact supporting excerpt or field value**, and a machine `check` spec
   describing how to re-confirm it. (`ingest/build.py` → `data/build/site/claims.json`)
2. **Automated verifier.** `ingest/verify.py` re-fetches every source live (not from the ingest cache) and checks
   the cited value is really there — numbers exactly, names, vote positions, dates, list membership. Derived
   metrics (missed votes, party-line rate, procedural/passage splits) are recomputed from a fresh download of
   every roll call. Anything that fails **or cannot be checked** is marked `blocked` and never renders.
3. **LLM drafts restate verified claims only.** Drafters receive only verified claim objects and must tag every
   sentence `[claim:ID]`. A second deterministic pass (`ingest/summaries.py::sentence_check`) rejects any
   sentence with no claim tag, an unverified claim, or a number, name, date, or quote that is not in the cited
   claims, and flags loaded characterizations (e.g. "corrupt", "influence", "controlled") unless the cited record
   itself contains them.
4. **Nothing auto-publishes.** Everything that passes lands in `data/review-queue/` as `pending_review`.
   Only items the editor moves to `approved` can render. Deploys require the maintainer's explicit approval.
5. **Public corrections log** at `/corrections` (`data/manual/corrections-log.json`), dated entries with source.
6. **CI gates.** `npm run build` runs:
   - `ingest/test_match_validation.py` (prebuild): lobbying name/bill match rules and IE notice dedupe.
   - `scripts/check-claims.mjs` (prebuild): every referenced claim exists and has source URL, retrieved-at,
     excerpt, check spec, status.
   - `scripts/check-rendered.mjs` (postbuild): scans every prerendered HTML page; **fails the build** if any
     rendered fact (`data-fact`) lacks a `verified` claim, if any page lacks `noindex`, if a source map ships,
     if a key/secret pattern appears in client JS, or if banned strings appear (politidex.com,
     555 numbers, fake addresses) or a private denylist term loaded from the gitignored
     `.opsec-denylist` file or the `OPSEC_DENYLIST` environment variable.
   - Templates only render through `<Fact claim=…>`, which returns nothing for unverified claims.

Known limits: the second pass catches unsupported names/numbers/quotes and loaded words, not every possible
unsupported nuance in phrasing — which is why human review (step 4) is mandatory, not optional.

---

## Phases

### Phase A — Cleanup (done locally, deployable on approval)
`POLITIDEX_DATA=0 npm run build` produces a site with no data pages:
- All mock pages removed or replaced by honest "in development" states (analytics, forecasts, trending,
  influence networks, investigate, politicians). Old URLs redirect to the new sections.
- Every politidex.com reference removed; canonical/OG point to https://www.politidex.icu.
- Contacts: editor@politidex.icu, corrections@politidex.icu. No personal name,
  no phone, no physical address. Third-party site-credit footers and generator tags are removed.
- `noindex, nofollow` meta on every page + `X-Robots-Tag` header + `robots.txt` disallow all. No sitemap.
- New favicon set and OG image. Real methodology (Verification Standard), corrections, data-sources,
  about (open-source/non-profit, AI double-edged sword framing), short honest privacy and terms.

### Phase B — Federal data (in production)
Coverage target: President, VP, Cabinet, and all 539 current members of the 119th Congress.
- Ingest: Congress.gov v3, House Clerk + Senate roll-call XML, House MemberData.xml and Senate committee XML,
  OpenFEC totals + committee-level receipts, official FEC bulk committee contributions (24K) and
  Schedule E independent expenditures, LDA.gov quarterly filings, whitehouse.gov Cabinet page;
  IDs joined via unitedstates/congress-legislators (CC0).
- Profiles `/p/[slug]`: office, party, state/district, first year served, website, committees, 8 most recent
  roll-call positions, recent sponsored bills, FEC 2025–26 totals (aggregate), largest committee contributors,
  a Connections panel (committee contributions, lobbying-disclosure matches, independent expenditures,
  covered-position records), cosponsorship partners, Politi-Matrix v1 analysis. Every item cited with
  retrieval date.
- `/people` search/filter; `/connections` (record-based edges); `/org/[slug]` organization pages;
  `/politi-matrix` (Analysis).
- **Election results are out of scope for the site.** Official results data is not included in this
  repository. The `/elections-2026` and `/elect/*` routes redirect to `/`.

### Phase C — Money and lobbying depth (partially shipped)
Shipped in the Connections panel: LDA.gov LD-2 lobbying-disclosure matches, covered-position records,
leadership PAC receipts, and Schedule E independent expenditures, plus organization pages. Still open:
joint fundraising committee mapping and further LDA depth (lobbyist ↔ client ↔ issue ↔ member
contributions). Required LDA statement on every LDA-derived page.

### Phase D — States (rolling, 3–12 months)
Pilot one state end-to-end, then expand. Sources per level below.

### Phase E — Local (long-term)
Mayors, county officials, school boards in large jurisdictions first, from official municipal/county records.

---

## Data sources by level

| Level | Officeholders | Votes / actions | Money | Notes |
|---|---|---|---|---|
| Federal | Congress.gov API, House Clerk MemberData, Senate rosters, whitehouse.gov | Clerk & Senate roll-call XML, Congress.gov bills | OpenFEC (committee-level only), LDA.gov | All free; keys via api.data.gov |
| State | Legislature websites, Secretaries of State | Legislature journals/APIs (vary); Open States API (data under CC0/CC-BY — verify per state) as an index | State campaign-finance portals; FollowTheMoney (check terms) | Verify each state's reuse terms |
| Local | City/county clerk sites, election boards | Council minutes/agendas (often PDF) | Local campaign-finance filings (often PDF) | Highest manual effort; OCR + human review |
| Election results | State election offices (official canvass) | — | — | Mark uncertified until certified |

Never primary: unsourced social media, leaks, paywalled opposition research, scraped news text, LLM output.

---

## LLM-assisted pipeline (with review queue)

```
official sources ──ingest──▶ raw snapshots (data/raw, gitignored)
                   build.py ─▶ claim objects (unverified)
                  verify.py ─▶ verified | blocked   (live re-fetch of every source)
             summaries.py   ─▶ draft (LLM or template) using ONLY verified claims, each sentence [claim:ID]
                            ─▶ second pass sentence_check ─▶ rejected | pending_review
                 editor     ─▶ approved  ─▶ next build renders it
                 build CI   ─▶ check-claims (pre) + check-rendered (post) ─▶ fail on any unverified fact
```
LLM use is optional and narrow: short source summaries and *suggested* connections (which become claims only
after a primary record is found and verified). Cost is controlled by drafting once per change, not per view.
"Use an LLM with web search instead of APIs" is rejected as a fact source: model output cannot be re-verified
and can hallucinate; official APIs are free and verifiable.

---

## Costs per stage (estimates, not quotes)

| Stage | Hosting | Data | LLM | Tier |
|---|---|---|---|---|
| A. Cleanup | Existing static hosting + DNS: $0 | none | none | **Free** |
| B. Federal data | Static hosting free tier (about 600 pages): $0; a paid plan only if build minutes or traffic need it | Free APIs (Congress.gov 5,000/hr; FEC ~1,000/hr) | $0 with template drafter; ~$5–30/mo if an LLM drafts summaries | **Free / Low** |
| C. Money + lobbying | Same; possibly hosted Postgres free tier | Free (LDA.gov) | ~$10–50/mo | **Low** |
| D. States | Paid static hosting + Postgres $0–25/mo | Mostly free; some states need scraping of PDFs | ~$20–100/mo (OCR/summaries) | **Low–Medium** |
| E. Local | $25–100/mo | Mostly free but labor-intensive | ~$50–200/mo | **Medium** |

Refresh cadence: nightly ingest + verify via a scheduled job (for example GitHub Actions on the free tier),
rebuild only after the maintainer approves the diff once launched.

---

## Open items
- Stated-position ("mask") sources for Politi-Matrix: official press releases/floor statements, each quoted
  with link; not started.
- Legal review of terms/privacy before public launch.
- Search indexing stays off until the maintainer approves launch.

- `scripts/unpack-data.mjs` runs only when the `VERCEL` environment variable is set, so a stale local deploy bundle cannot overwrite source files.
