"""Re-check money-flow facts against the FEC bulk files they cite.

Facts whose amounts and identifiers match a fresh read are marked verified.
Facts that do not match are removed from the served shards and listed in
data/moneyflow/review.json. Individual-contribution files are not read.

Usage (from the repository root):
  python3 ingest/moneyflow_verify.py
  python3 ingest/moneyflow_verify.py --check

--check confirms the served shards are already verified and, when the bulk
files are on disk, that they still match those files.
"""
from __future__ import annotations

import json
import sys
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


def files_ready():
    for key in ("cm", "webk", "oth", "pas2", "oppexp"):
        path = MF.RAW_DIR / Path(FILE_URLS[key]).name
        if not path.exists() or path.stat().st_size < 1000:
            return False
        if "indiv" in path.name.lower():
            return False
    return True


def fresh_ids(pilot_ids):
    master = MF._load_master()
    summaries, _dupes, _missing = MF._load_summaries(master)
    agg, _stats = MF._scan(master, set(pilot_ids))
    found = {}
    for cid in pilot_ids:
        row = summaries.get(cid)
        if not row:
            continue
        records = [rec.as_dict() for rec in agg.get(cid, {}).values()]
        try:
            shard = build_shard(row, records, "2000-01-01T00:00:00Z", summaries, master=master)
        except ReconciliationError:
            continue
        for source in walk_sources(shard):
            found[source["id"]] = source["check"]
    return found


def apply(write):
    manifest = json.loads(MANIFEST.read_text())
    pilot = [row["committee_id"] for row in manifest.get("pilot") or []]
    checked = verified = held = 0
    review = []
    fresh = fresh_ids(pilot) if files_ready() else None
    kept_pilot = []
    for row in manifest.get("pilot") or []:
        cid = row["committee_id"]
        path = SHARD_DIR / (cid + ".json")
        if not path.exists():
            review.append({"committee_id": cid, "claim_id": None, "reason": "shard file is missing"})
            held += 1
            continue
        shard = json.loads(path.read_text())
        root = (shard.get("node") or {}).get("source") or {}
        root_ok = mark(root, fresh, cid, review)
        checked += 1
        if root_ok:
            verified += 1
        else:
            held += 1
        profile = (shard.get("node") or {}).get("profile") or {}
        if profile.get("source"):
            checked += 1
            if mark(profile["source"], fresh, cid, review):
                verified += 1
            else:
                held += 1
                profile.pop("source", None)
        children = []
        for child in shard.get("children") or []:
            node_src = (child.get("node") or {}).get("source")
            edge_src = (child.get("edge") or {}).get("source")
            node_ok = True
            edge_ok = True
            if node_src:
                checked += 1
                node_ok = mark(node_src, fresh, cid, review)
                verified += 1 if node_ok else 0
                held += 0 if node_ok else 1
            child_profile = (child.get("node") or {}).get("profile") or {}
            if child_profile.get("source"):
                checked += 1
                if mark(child_profile["source"], fresh, cid, review):
                    verified += 1
                else:
                    held += 1
                    child_profile.pop("source", None)
            if edge_src:
                checked += 1
                edge_ok = mark(edge_src, fresh, cid, review)
                verified += 1 if edge_ok else 0
                held += 0 if edge_ok else 1
            if node_ok and edge_ok:
                children.append(child)
        shard["children"] = children
        if root_ok:
            kept_pilot.append(row)
            if write:
                path.write_text(json.dumps(shard, indent=1, ensure_ascii=False) + "\n")
        elif write:
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


def mark(source, fresh, cid, review):
    """True when this fact matches the FEC files, or was already verified offline."""
    if fresh is None:
        return source.get("status") == "verified" and source.get("source_url") and source.get("retrieved_at") and source.get("excerpt")
    check = source.get("check") or {}
    expected = fresh.get(source.get("id"))
    if expected is not None and expected == check:
        source["status"] = "verified"
        source["verified_at"] = now_iso()
        return True
    source["status"] = "held"
    review.append({
        "committee_id": cid,
        "claim_id": source.get("id"),
        "kind": check.get("kind"),
        "source_url": source.get("source_url"),
        "reason": "The FEC bulk file did not reproduce this fact.",
    })
    return False


def main(argv):
    check_only = "--check" in argv
    if not files_ready() and not check_only:
        raise SystemExit("FEC bulk files are not on disk. Run: python3 ingest/moneyflow.py fetch")
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
