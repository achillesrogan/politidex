"""OpenFEC: candidate financial totals (aggregate only) and principal campaign committees,
plus committee-level PAC contributors (no individual contributor data is requested or stored).
Key: FEC_API_KEY or DATA_GOV_API_KEY env var (never written to disk)."""
import sys, json, time, urllib.parse
from common import *

BASE = "https://api.open.fec.gov/v1"
KEY = api_key("FEC_API_KEY")

def get(path, params):
    q = list(params) + [("api_key", KEY)]
    url = f"{BASE}{path}?{urllib.parse.urlencode(q)}"
    st, b = fetch(url)
    time.sleep(0.25)
    if st != 200: return None, safe_url(url)
    return json.loads(b), safe_url(url)

def people():
    L = read_json(RAW / "legislators-current.json")
    E = read_json(RAW / "executive.json")
    out = []
    for p in L: out.append((p["id"]["bioguide"], p["id"].get("fec", [])))
    return out

def totals(cycle=2026):
    ids = [(b, f) for b, fs in people() for f in fs]
    by_cand, out = {}, {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        params = [("cycle", cycle), ("election_full", "false"), ("per_page", 100)] + [("candidate_id", f) for _, f in chunk]
        d, url = get("/candidates/totals/", params)
        for r in (d or {}).get("results", []):
            by_cand[r["candidate_id"]] = r
    for b, f in ids:
        r = by_cand.get(f)
        if not r: continue
        keep = {k: r.get(k) for k in ["candidate_id", "name", "office", "state", "district", "party", "cycle", "receipts",
                "disbursements", "cash_on_hand_end_period", "individual_itemized_contributions",
                "other_political_committee_contributions", "debts_owed_by_committee", "coverage_start_date", "coverage_end_date",
                "candidate_election_year"]}
        keep["source_url"] = f"https://www.fec.gov/data/candidate/{f}/?cycle={cycle}"
        keep["api_url"] = f"{BASE}/candidates/totals/?candidate_id={f}&cycle={cycle}&election_full=false"
        prev = out.get(b)
        if not prev or (keep.get("receipts") or 0) > (prev.get("receipts") or 0):
            out[b] = keep
    return out

def committees():
    ids = [(b, f) for b, fs in people() for f in fs]
    cand2bio = {f: b for b, f in ids}
    out = {}
    for i in range(0, len(ids), 40):
        params = [("designation", "P"), ("per_page", 100), ("cycle", 2026)] + [("candidate_id", f) for _, f in ids[i:i+40]]
        d, url = get("/committees/", params)
        for r in (d or {}).get("results", []):
            for cid in r.get("candidate_ids", []):
                if cid in cand2bio:
                    out.setdefault(cand2bio[cid], []).append({"committee_id": r["committee_id"], "name": r["name"],
                        "candidate_id": cid, "source_url": f"https://www.fec.gov/data/committee/{r['committee_id']}/"})
    return out

def pac_contributors(comms, cycle=2026, per=10):
    """Committee-level aggregates: political committees reporting disbursements to each member's principal
    campaign committee (FEC Schedule B aggregated by recipient). No individual contributor data."""
    out = {}
    done = BUILD / "fec-pac-partial.json"
    if done.exists(): out = read_json(done)
    for n, (bio, cl) in enumerate(comms.items()):
        if bio in out: continue
        rows = []
        for c in cl[:1]:
            params = [("recipient_id", c["committee_id"]), ("cycle", cycle), ("sort", "-total"), ("per_page", per)]
            d, url = get("/schedules/schedule_b/by_recipient_id/", params)
            if d is None: continue
            for r in d.get("results", []):
                rows.append({"giver_id": r["committee_id"], "giver_name": r["committee_name"], "total": r["total"], "count": r["count"],
                             "recipient_id": c["committee_id"], "recipient_name": r.get("recipient_name"), "api_url": url})
        out[bio] = rows
        if n % 25 == 0: write_json(done, out); print("pac", n, flush=True)
    write_json(done, out)
    return out

if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    meta = {"retrieved_at": now_iso(), "source": "Federal Election Commission, OpenFEC API (api.open.fec.gov)",
            "note": "Aggregate committee-level figures only. Individual contributor information from FEC reports may not be sold or used for soliciting contributions or for commercial purposes (52 U.S.C. 30111(a)(4))."}
    if step in ("all", "totals"):
        t = totals(); write_json(BUILD / "fec-totals.json", {**meta, "cycle": 2026, "totals": t}); print("totals", len(t))
    if step in ("all", "committees", "pac"):
        cpath = BUILD / "fec-committees.json"
        if step != "pac" or not cpath.exists():
            c = committees(); write_json(cpath, {**meta, "committees": c}); print("committees", len(c))
        c = read_json(cpath)["committees"]
        p = pac_contributors(c); write_json(BUILD / "fec-pac.json", {**meta, "cycle": 2026, "contributors": p}); print("pac", len(p))
