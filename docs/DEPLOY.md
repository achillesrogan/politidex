# How production gets its data

`data/build/site` is gitignored. A deployment that only has the git tree has no profile snapshot, so the built site has no people pages. Production data is not created by the git build.

## Git-connected build

Vercel clones the repository. `.vercelignore` is not applied to that clone. `ingest/` is in git, so `npm run build` can run `python3 ingest/test_match_validation.py` and `python3 ingest/test_moneyflow.py`. `data/build/` and `deploy-bundle*.json.gz` are gitignored, so they are not in the clone. `scripts/unpack-data.mjs` unpacks a bundle only when `VERCEL` is set and one of those bundle files is present. On a git build it finds none and leaves the tree as it is. The result is an empty site.

## CLI deploy that carries the snapshot

The populated site is deployed from a checkout that already has `data/build/site` on disk. `.vercelignore` replaces `.gitignore` for a CLI upload. `data/build/site` is not listed there, so the unpacked snapshot is uploaded. The gzipped bundles are listed and are not uploaded; the build reads the snapshot already on disk.

`ingest/` must be in that upload. Prebuild runs the Python tests under `ingest/`. Leaving `ingest/` in `.vercelignore` removes those files and `npm run build` fails before Next.js starts. The ignore file therefore excludes `ingest/__pycache__/` and not `ingest/` itself.

Nothing in this note deploys the site. A production deploy still waits for an explicit CLI deploy from a checkout that has the snapshot.

## Money-flow verification

`python3 ingest/moneyflow_verify.py --check` does not download the FEC bulk files. On Vercel and in CI those zips are not in the tree, so `--check` only confirms that each served fact already has `status` `verified` plus a source, a retrieval date, and an excerpt. That is not a new read of the filings.

The served totals follow four filing rules. Repeated SUB_IDs count once. Zero-dollar rows are excluded. Type 42 recount-account disbursements are included. Negative rows are netted. The same sentences are on the money-flow page.

Before a deploy bundles `data/moneyflow/`, run `python3 ingest/moneyflow.py fetch --refresh` and then `python3 ingest/moneyflow_verify.py` against those freshly downloaded files. Plain `fetch` reuses a zip that is already on disk. `files_ready()` rejects a zip older than 7 days. The age is the FEC Last-Modified date when that was saved, otherwise the date stored in the zip, and only then the local timestamp. A local timestamp in the future is stale. A stale download is not treated as a fresh read. The full verify command rebuilds each pilot shard from the bulk files and compares every displayed field. That shows the shards are reproducible from those files. It does not prove the aggregation rules are the correct reading of the filings. A fact that does not match is held out of the served shard and listed in `data/moneyflow/review.json`.
