"""Prove the served shards are reproducible from the FEC bulk files.

A fresh read is compared with every displayed field. A match marks the fact
verified. A difference removes it from the served shard and lists it in
data/moneyflow/review.json. Reproducing the shard does not prove that the aggregation rules are the correct reading of the filings. Individual-contribution
files are not read.

Usage (from the repository root):
  python3 ingest/moneyflow_verify.py
  python3 ingest/moneyflow_verify.py --check

--check confirms the served shards are already verified and, when the bulk
files are on disk, that they still match those files.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import moneyflow as MF
from moneyflow_lib import FILE_URLS, ReconciliationError, build_shard

ROOT = Path(__file__).resolve().parents[1]
SHARD_DIR = ROOT / "data" / "moneyflow" / "pilot" / "shards"
MANIFEST = ROOT / "data" / "moneyflow" / "pilot" / "manifest.json"
REVIEW = ROOT / "data" / "moneyflow" / "review.json"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def walk_sources(shard):
    node = shard.get("node") or {}
    if node.get("source"):
        yield node["source"]
    profile = node.get("profile") or {}
    if profile.get("source"):
        yield profile["source"]
    for child in shard.get("children") or []:
        child_node = child.get("node") or {}
        if child_node.get("source"):
            yield child_node["source"]
        child_profile = child_node.get("profile") or {}
        if child_profile.get("source"):
            yield child_profile["source"]
        edge = child.get("edge") or {}
        if edge.get("source"):
            yield edge["source"]


ZIP_MAX_AGE = 7 * 24 * 60 * 60


def files_ready(now=None, root=None):
    """True when the five bulk zips exist, are non-trivial, and are 7 days old or newer."""
    root = Path(root) if root is not None else MF.RAW_DIR
    clock = time.time() if now is None else now
    for key in ("cm", "webk", "oth", "pas2", "oppexp"):
        path = root / Path(FILE_URLS[key]).name
        if not path.exists() or path.stat().st_size < 1000:
            return False
        if "indiv" in path.name.lower():
            return False
        if clock - path.stat().st_mtime > ZIP_MAX_AGE:
            return False
    return True


SKIP_FIELDS = {"status", "verified_at", "verify_note"}


def diff_paths(served, fresh, path="$"):
    """Displayed fields that differ. Status and verification dates are ignored."""
    if isinstance(served, dict) or isinstance(fresh, dict):
        served = served if isinstance(served, dict) else {}
        fresh = fresh if isinstance(fresh, dict) else {}
        out = []
        for key in sorted(set(served) | set(fresh)):
            if key in SKIP_FIELDS:
                continue
            out.extend(diff_paths(served.get(key), fresh.get(key), "%s.%s" % (path, key)))
        return out
    if isinstance(served, list) or isinstance(fresh, list):
        served = served if isinstance(served, list) else []
        fresh = fresh if isinstance(fresh, list) else []
        if len(served) != len(fresh):
            return [path + ".length"]
        out = []
        for i, (left, right) in enumerate(zip(served, fresh)):
            out.extend(diff_paths(left, right, "%s[%d]" % (path, i)))
        return out
    if served != fresh:
        return [path]
    return []


def fresh_shards(pilot_ids, retrieved_at):
    master = MF._load_master()
    summaries, _dupes, _missing = MF._load_summaries(master)
    agg, _stats = MF._scan(master, set(pilot_ids))
    built = {}
    for cid in pilot_ids:
        row = summaries.get(cid)
        if not row:
            continue
        records = [rec.as_dict() for rec in agg.get(cid, {}).values()]
        try:
            built[cid] = build_shard(row, records, retrieved_at, summaries, master=master)
        except ReconciliationError:
            built[cid] = None
    return built


def apply(write):
    manifest = json.loads(MANIFEST.read_text())
    pilot = [row["committee_id"] for row in manifest.get("pilot") or []]
    checked = verified = held = 0
    review = []
    rebuilt = None
    if files_ready():
        retrieved = "2000-01-01T00:00:00Z"
        sample = SHARD_DIR / (pilot[0] + ".json") if pilot else None
        if sample and sample.exists():
            retrieved = ((json.loads(sample.read_text()).get("node") or {}).get("source") or {}).get("retrieved_at") or retrieved
        rebuilt = fresh_shards(pilot, retrieved)
    kept_pilot = []
    for row in manifest.get("pilot") or []:
        cid = row["committee_id"]
        path = SHARD_DIR / (cid + ".json")
        if not path.exists():
            review.append({"committee_id": cid, "claim_id": None, "field": None, "reason": "shard file is missing"})
            held += 1
            continue
        shard = json.loads(path.read_text())
        sources = list(walk_sources(shard))
        checked += len(sources)
        if rebuilt is None:
            ok = all(source.get("status") == "verified" and source.get("source_url") and source.get("retrieved_at") and source.get("excerpt") for source in sources)
            if ok:
                verified += len(sources)
                kept_pilot.append(row)
            else:
                held += len(sources)
                review.append({"committee_id": cid, "claim_id": None, "field": "status", "reason": "status is not verified"})
            continue
        fresh = rebuilt.get(cid)
        fields = ["$"] if fresh is None else diff_paths(shard, fresh)
        if not fields:
            changed = False
            for source in sources:
                if source.get("status") != "verified" or not source.get("verified_at"):
                    source["status"] = "verified"
                    source["verified_at"] = now_iso()
                    changed = True
            verified += len(sources)
            kept_pilot.append(row)
            if write and changed:
                path.write_text(json.dumps(shard, indent=1, ensure_ascii=False) + "\n")
            continue
        held += len(sources)
        for field in fields:
            review.append({
                "committee_id": cid,
                "claim_id": None,
                "field": field,
                "reason": "The FEC bulk file did not reproduce %s." % field,
            })
        if write:
            path.unlink()
    manifest["pilot"] = kept_pilot
    if write:
        MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
        REVIEW.write_text(json.dumps({
            "schema": "politidex.moneyflow.review.v1",
            "retrieved_at": now_iso(),
            "checked": checked,
            "verified": verified,
            "held": held,
            "records": review,
        }, indent=1, ensure_ascii=False) + "\n")
    return checked, verified, held, review


def main(argv):
    check_only = "--check" in argv
    if not files_ready() and not check_only:
        raise SystemExit("FEC bulk files are not on disk or are older than 7 days. Run: python3 ingest/moneyflow.py fetch --refresh")
    checked, verified, held, _review = apply(write=not check_only)
    print("money-flow facts checked %d verified %d held %d" % (checked, verified, held))
    if check_only:
        served = 0
        manifest = json.loads(MANIFEST.read_text())
        if manifest.get("not_in_web_bundle") is True:
            print("money-flow pages are gated")
            return
        for row in manifest.get("pilot") or []:
            path = SHARD_DIR / (row["committee_id"] + ".json")
            shard = json.loads(path.read_text())
            for source in walk_sources(shard):
                served += 1
                if source.get("status") != "verified" or not source.get("source_url") or not source.get("retrieved_at") or not source.get("excerpt"):
                    raise SystemExit("served money-flow fact %s is not verified" % source.get("id"))
        if files_ready() and held:
            raise SystemExit("FEC files do not match %d served facts" % held)
    if held and not check_only:
        print("held facts are in", REVIEW.relative_to(ROOT))


if __name__ == "__main__":
    main(sys.argv)
