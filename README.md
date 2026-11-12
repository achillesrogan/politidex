# Politidex

Politidex is a non-profit, open-source public record of who holds power in the
United States and how they are connected. It uses AI for the public good:
making official public records — votes, filings, disclosures, and campaign
finance totals that are already free to read, but hard to work through —
easier to explore, with every published fact tied to a source anyone can open
and check.

The current site covers **profiles of current federal officeholders** and the
**documented connections** between them, plus an **On the record** section
that can place two independently verified records side by side without adding
a conclusion. **Election results are not part of the site.**

The live site is [https://www.politidex.icu](https://www.politidex.icu).
Search indexing is off (`noindex`) until a public launch is approved.

## Verification standard

No unverified claim reaches the site. Every rendered fact is a claim object
with a source URL, a retrieval time, a supporting excerpt, and a machine check
that can re-confirm it. The build re-checks each claim against its official
source and **fails** if a rendered fact is missing a verified source.

AI may help find, organize, and draft plain-language restatements, but it
never publishes on its own. A draft may only restate already-verified claims,
a second automated pass rejects unsupported sentences, and a human editor
reviews every item before it can render. See `PLAN.md` and `/methodology`.

CI gates:

- `scripts/check-claims.mjs` (prebuild): every referenced claim exists and has
  a source URL, retrieval time, excerpt, check spec, and status.
- `scripts/check-rendered.mjs` (postbuild): every prerendered page is scanned;
  the build fails if a rendered fact lacks a verified claim, if a page is
  missing `noindex`, if a source map would ship, if a key pattern appears in
  client JavaScript, or if a banned or private denylist term appears. On the
  record pages also reject causal wording.

Templates render facts only through `<Fact claim=…>`, which returns nothing
for unverified claims.

## Setup

You need Node.js 20+ and Python 3.11+ (the ingest scripts use the Python
standard library only). Optional headless fetching uses `playwright-core`.

```bash
git clone <this-repository>
cd politidex
npm install
```

API keys are read **only** from environment variables. Use `DATA_GOV_API_KEY`
for a single [api.data.gov](https://api.data.gov/signup/) key (free), or set
`CONGRESS_API_KEY` / `FEC_API_KEY` if you keep them separate. Keys are never
written to files, logs, claim objects, or the client bundle; stored URLs have
`api_key` stripped. `.env*` is gitignored.

`scripts/unpack-data.mjs` runs only in a hosted build when the `VERCEL`
environment variable is set, so a local deploy bundle cannot overwrite files
on disk.

### Site without data pages

```bash
POLITIDEX_DATA=0 npm run build && npm start
```

### Regenerate federal data

Raw snapshots land in `data/raw/` and the verified site snapshot in
`data/build/`. Neither directory is in git; they are large and can be
rebuilt from official sources:

```bash
# export DATA_GOV_API_KEY=   # set in your environment; do not commit it
cd ingest
python3 votes.py            # House Clerk + Senate roll calls (no key needed)
python3 fec.py              # OpenFEC totals (needs DATA_GOV_API_KEY)
python3 congress.py         # Congress.gov members and bills (needs DATA_GOV_API_KEY)
# Committee rosters and the Cabinet page are fetched from clerk.house.gov,
# senate.gov, and whitehouse.gov (see PLAN.md).
python3 build.py            # claim objects
python3 verify.py           # live re-check of every claim (blocks failures)
python3 side_by_side.py     # On the record entries from data/manual/on-the-record.json
python3 verify.py --stage side-by-side
python3 summaries.py        # optional drafts -> data/review-queue (pending_review)
cd ..
npm run build               # fails if any rendered fact lacks a verified claim
```

`data/manual/` in this repository holds the public corrections log and the
On the record catalog (currently no published entries). Editor-approved
summaries live in `data/review-queue/` (gitignored) and render only when
their status is `approved`.

Election ingest scripts under `ingest/` and the former results UI under
`attic/elections-ui/` are unused by the Next.js build. Official election
results data is not included. The `/elections-2026` and `/elect/*` routes
redirect to `/`.

## Contributing

Bug reports, source corrections, and code improvements are welcome.

- **Factual corrections** about something published on the site: email
  [corrections@politidex.icu](mailto:corrections@politidex.icu) with the page
  URL, what is wrong, and a link to the official record. The public log is
  at `/corrections`.
- **Code and documentation:** open an issue or pull request. Please do not
  commit API keys, `.env` files, `data/raw/`, `data/build/`, election results
  files, unpublished investigation notes, or a real `.opsec-denylist`. Copy
  `.opsec-denylist.example` to `.opsec-denylist` for local OPSEC checks, or
  set `OPSEC_DENYLIST`.
- Do not submit unsourced claims, scraped news text, or model output as a
  fact source. Official records only.

## Security

Please report vulnerabilities privately to
[editor@politidex.icu](mailto:editor@politidex.icu). See `SECURITY.md`.

## License

- **Code** in this repository is licensed under the GNU Affero General Public
  License v3.0 or later. See `LICENSE`.
- **Politidex-produced data** (verified claim objects, compilations, and
  derived analysis) is licensed under CC BY 4.0, with attribution to
  Politidex. Upstream sources keep their own terms: congress-legislators is
  CC0 1.0, and U.S. government works are generally public domain
  (17 U.S.C. § 105). See `DATA-LICENSE.md`.
