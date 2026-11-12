"""Build On the record (side-by-side) site data and claims from a curated manual file.

An entry is emitted only when it has both Record A (official roll call, member
recorded as Not Voting) and Record B (a qualifying primary source that names
the member at a specific event on the same date). Claims are unverified until
`python ingest/verify.py --stage side-by-side` re-fetches each source.

Record B sources: the organizer's own event page or official release; the
member's official site, press release, or verified social post; or an official
public schedule. News reports alone do not qualify.

Usage: python ingest/side_by_side.py
"""
import hashlib, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
SITE = BUILD / "site"

MANUAL = ROOT / "data" / "manual" / "on-the-record.json"
OUT = SITE / "on-the-record.json"

def cid(prefix, *parts):
    h = hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]
    return f"{prefix}_{h}"

def upsert(claims, claim):
    prev = claims.get(claim["id"])
    if prev and prev.get("check") == claim["check"] and prev.get("status") == "verified":
        claim["status"] = "verified"
        if prev.get("verified_at"): claim["verified_at"] = prev["verified_at"]
        if prev.get("verify_note"): claim["verify_note"] = prev["verify_note"]
    claims[claim["id"]] = claim

def main():
    man = read_json(MANUAL) if MANUAL.exists() else {"entries": []}
    claims_path = SITE / "claims.json"
    claims_data = read_json(claims_path) if claims_path.exists() else {"claims": {}}
    claims = claims_data.setdefault("claims", {})
    out_entries = []
    for raw in man.get("entries") or []:
        a, b = raw.get("record_a") or {}, raw.get("record_b") or {}
        needed_a = ("source_url", "excerpt", "retrieved_at", "bioguide", "when", "vote_label")
        needed_b = ("source_url", "excerpt", "retrieved_at", "name", "event", "date")
        if any(not a.get(k) for k in needed_a) or any(not b.get(k) for k in needed_b):
            continue
        if b["name"] not in b["excerpt"]:
            raise SystemExit(f"Record B excerpt must include the member's name ({raw.get('id')})")
        name = raw.get("member_name") or b["name"]
        aid = cid("sbs", "a", a["source_url"], a["bioguide"], a["vote_label"])
        bid = cid("sbs", "b", b["source_url"], b["name"], b["event"], b["date"])
        upsert(claims, {
            "id": aid, "text": f"{name} is recorded as Not Voting on {a['vote_label']}, {a['when']}.",
            "value": "Not Voting", "excerpt": a["excerpt"],
            "source_name": a.get("source_name") or "Official roll call",
            "source_url": a["source_url"], "retrieved_at": a["retrieved_at"],
            "check": {"kind": "rollcall-xml", "url": a["source_url"], "chamber": a.get("chamber") or "house",
                      "bioguide": a["bioguide"], "expected": a.get("expected") or "Not Voting"},
            "status": "unverified",
        })
        upsert(claims, {
            "id": bid, "text": f"{b.get('source_name') or 'The source'} places {name} at {b['event']} on {b['date']}.",
            "value": b["name"], "excerpt": b["excerpt"],
            "source_name": b.get("source_name") or "Primary source",
            "source_url": b["source_url"], "retrieved_at": b["retrieved_at"],
            "check": {"kind": "primary-excerpt", "url": b["source_url"], "excerpt": b["excerpt"], "name": b["name"]},
            "status": "unverified",
        })
        out_entries.append({
            "id": raw.get("id") or cid("sbs", "e", aid, bid),
            "member_name": name, "member_slug": raw.get("member_slug"),
            "bioguide": a["bioguide"],
            "record_a": {"claim": aid, "vote_label": a["vote_label"], "when": a["when"],
                         "question": a.get("question"), "measure": a.get("measure")},
            "record_b": {"claim": bid, "source_name": b.get("source_name"), "event": b["event"], "date": b["date"]},
        })
    write_json(claims_path, claims_data)
    write_json(OUT, {
        "generated": now_iso(),
        "note": "Politidex presents these records side by side without drawing conclusions. Absences have many causes.",
        "entries": out_entries,
    })
    print(f"on-the-record entries {len(out_entries)}")

if __name__ == "__main__":
    main()
