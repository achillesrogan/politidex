"""Independent spot-check of N profiles against a SECOND source (not the one cited), as a QC cross-check.
- party/state: unitedstates/congress-legislators current terms (independent compilation)
- most recent House vote: Congress.gov house-vote members endpoint (vs. Clerk XML cited)
- most recent Senate vote: senate.gov human-readable .htm page (vs. XML cited)
- committees: congress-legislators committee-membership-current.json
- FEC receipts: OpenFEC /candidate/{id}/totals/ endpoint (vs. /candidates/totals/ cited)"""
import json, random, re, sys, html as H
from common import *
import verify as V
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
site = BUILD / "site"
claims = read_json(site / "claims.json")["claims"]
people = [p for p in read_json(site / "people.json")["people"] if p["kind"] == "congress"]
leg = {p["id"]["bioguide"]: p for p in read_json(RAW / "legislators-current.json")}
cm = read_json(RAW / "committee-membership-current.json")
pmap = {"Democrat": "Democratic", "Republican": "Republican", "Independent": "Independent"}
sample = random.sample([p for p in people if p["chamber"] == "senate"], N // 2) + random.sample([p for p in people if p["chamber"] == "house"], N - N // 2)
report = []
for p in sample:
    pr = read_json(site / "profiles" / f"{p['slug']}.json"); b = p["bioguide"]; row = {"name": p["name"], "slug": p["slug"], "checks": []}
    t = leg[b]["terms"][-1]
    row["checks"].append(("party (vs congress-legislators)", pmap.get(t["party"], t["party"]) == p["party"], f"{p['party']} vs {t['party']}"))
    row["checks"].append(("state (vs congress-legislators)", t["state"] == p["state"], f"{p['state']} vs {t['state']}"))
    norm = lambda c: ("HS" + c[:2]) if re.match(r"^[A-Z]{2}00$", c) else c
    mine = {norm(c["code"]) for c in pr["committees"] if "Joint" not in c["name"]}
    theirs = {code for code, mem in cm.items() if len(code) == 4 and not code.startswith("J") and any(m.get("bioguide") == b for m in mem)}
    joint = sorted(code for code, mem in cm.items() if len(code) == 4 and code.startswith("J") and any(m.get("bioguide") == b for m in mem))
    row["checks"].append(("standing/select committees (vs congress-legislators)", mine == theirs, f"site {sorted(mine)} vs dataset {sorted(theirs)}" + (f"; joint committees not yet covered for senators: {joint}" if joint and p["chamber"] == "senate" else "")))
    if pr.get("recent_votes"):
        v = pr["recent_votes"][0]; code = {"Yea": "Y", "Nay": "N", "Present": "P", "Not Voting": "NV"}[v["position"]]
        if v["chamber"] == "house":
            sess = 1 if v["date"].startswith("2025") else 2
            st, raw = V.live(f"https://api.congress.gov/v3/house-vote/119/{sess}/{v['roll']}/members?format=json&limit=500")
            res = json.loads(raw)["houseRollCallVoteMemberVotes"]["results"] if st == 200 else []
            got = next((r["voteCast"] for r in res if r["bioguideID"] == b), None)
            m = {"Yea": "Y", "Aye": "Y", "Nay": "N", "No": "N", "Present": "P", "Not Voting": "NV"}
            row["checks"].append((f"latest vote roll {v['roll']} (vs Congress.gov API)", m.get(got) == code, f"site {v['position']} vs Congress.gov {got}"))
        else:
            st, raw = V.live(v["url"])
            txt = H.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "ignore")))
            last = leg[b]["name"]["last"]
            mm = re.search(rf"{re.escape(last)} \(\w-{p['state']}\),?\s*(Yea|Nay|Not Voting|Present)", txt)
            row["checks"].append((f"latest vote roll {v['roll']} (vs senate.gov .htm)", bool(mm) and mm.group(1) == v["position"], f"site {v['position']} vs htm {mm.group(1) if mm else 'not parsed'}"))
    if pr.get("money"):
        cand = re.search(r"candidate_id=(\w+)", claims[pr["money"][0]["claim"]]["check"]["url"]).group(1)
        st, raw = V.live(f"https://api.open.fec.gov/v1/candidate/{cand}/totals/?cycle=2026&election_full=false")
        rs = json.loads(raw).get("results", []) if st == 200 else []
        got = rs[0].get("receipts") if rs else None
        row["checks"].append(("FEC receipts (vs /candidate/{id}/totals)", got is not None and abs(float(got) - pr["money"][0]["value"]) < 0.01, f"site {pr['money'][0]['value']} vs {got}"))
    report.append(row)
write_json(BUILD / "spotcheck-report.json", {"run_at": now_iso(), "profiles": report})
for r in report:
    print(r["name"])
    for c in r["checks"]: print("   ", "PASS" if c[1] else "FAIL", c[0], "|", c[2])
