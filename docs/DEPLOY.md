# How production gets its data

`data/build/site` is gitignored. A deployment that only has the git tree has no profile snapshot, so the built site has no people pages. Production data is not created by the git build.

## Git-connected build

Vercel clones the repository. `.vercelignore` is not applied to that clone. `ingest/` is in git, so `npm run build` can run `python3 ingest/test_match_validation.py` and `python3 ingest/test_moneyflow.py`. `data/build/` and `deploy-bundle*.json.gz` are gitignored, so they are not in the clone. `scripts/unpack-data.mjs` unpacks a bundle only when `VERCEL` is set and one of those bundle files is present. On a git build it finds none and leaves the tree as it is. The result is an empty site.

## CLI deploy that carries the snapshot

The populated site is deployed from a checkout that already has `data/build/site` on disk. `.vercelignore` replaces `.gitignore` for a CLI upload. `data/build/site` is not listed there, so the unpacked snapshot is uploaded. The gzipped bundles are listed and are not uploaded; the build reads the snapshot already on disk. `data/build/connections-*.json` is excluded from the upload. Those connection intermediates are not read by the remote build or the runtime, and `data/build/site` stays included.

`ingest/` must be in that upload. Prebuild runs the Python tests under `ingest/`. Leaving `ingest/` in `.vercelignore` removes those files and `npm run build` fails before Next.js starts. The ignore file therefore excludes `ingest/__pycache__/` and not `ingest/` itself.

Nothing in this note deploys the site. A production deploy still waits for an explicit CLI deploy from a checkout that has the snapshot.

## Before a production promote

Re-run `python3 ingest/connections_build.py` after any LDA rematch or FEC refresh, before deploying.

Deploy with `vercel deploy --archive=tgz`. The free plan caps uploads at 5,000 files a day, and the archive counts as one upload.

Before that command, run `node scripts/check-upload.mjs --archive=tgz`. It reads `.vercelignore` and fails if any file the CLI would upload is over 100 MB. Without `--archive=tgz` it also fails when that set is over 5,000 files. `.git`, `.vercel`, `node_modules`, and `.next` are not part of the upload.

Remote builds do not load the OPSEC denylist. Run `node scripts/check-rendered.mjs` locally with the denylist (`.opsec-denylist` or `OPSEC_DENYLIST`) before every promote.

## Money-flow verification

`python3 ingest/moneyflow_verify.py --check` does not download the FEC bulk files. On Vercel and in CI those zips are not in the tree, so `--check` only confirms that each served fact already has `status` `verified` plus a source, a retrieval date, and an excerpt. That is not a new read of the filings.

The served totals follow four filing rules. Repeated SUB_IDs count once. Zero-dollar rows are excluded. Type 42 recount-account disbursements are included. Negative rows are netted. The money-flow page states those rules in public wording: a repeated FEC transaction ID (SUB_ID) counts once.

Before a deploy bundles `data/moneyflow/`, run `python3 ingest/moneyflow.py fetch --refresh` and then `python3 ingest/moneyflow_verify.py` against those freshly downloaded files. Plain `fetch` reuses a zip that is already on disk. `files_ready()` rejects a zip older than 7 days. The age is the FEC Last-Modified date when that was saved, otherwise the date stored in the zip, and only then the local timestamp. A local timestamp in the future is stale. A stale download is not treated as a fresh read. The full verify command rebuilds each pilot shard from the bulk files and compares every displayed field. That shows the shards are reproducible from those files. It does not prove the aggregation rules are the correct reading of the filings. A fact that does not match is held out of the served shard and listed in `data/moneyflow/review.json`.

FEC posts the any-transaction file (`oth`), the contributions-to-candidates file (`pas2`), and the operating-expenditures file (`oppexp`) weekly. If a post is late, those files fall outside the 7-day window and the full verify refuses to run. That refusal is safe by design: a late file is not treated as a current read. Wait for FEC to post, then run `python3 ingest/moneyflow.py fetch --refresh` and `python3 ingest/moneyflow_verify.py`. Do not bundle `data/moneyflow/` from the refused run, and do not bypass the age check. Until that fresh verify passes, `--check` without new files only confirms the verified flag.
