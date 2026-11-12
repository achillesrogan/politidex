"""Download official roll-call XML: House Clerk (clerk.house.gov) and Senate LIS (senate.gov).
Writes data/build/votes-{chamber}.json with one record per roll call, member positions keyed by bioguide id."""
import sys, re, time, concurrent.futures as cf
import xml.etree.ElementTree as ET
from common import *

LEG = read_json(RAW / "legislators-current.json")
LIS2BIO = {p["id"].get("lis"): p["id"]["bioguide"] for p in LEG if p["id"].get("lis")}
MAP = {"Yea": "Y", "Aye": "Y", "Yes": "Y", "Nay": "N", "No": "N", "Present": "P", "Not Voting": "NV", "Guilty": "Y", "Not Guilty": "N"}

def cache_get(url, path):
    if path.exists() and path.stat().st_size > 0:
        return 200, path.read_bytes()
    st, b = fetch(url)
    if st == 200 and b.lstrip().startswith(b"<?xml") or (st == 200 and b"<" in b[:50]):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b)
    return st, b

def house(year, n):
    url = f"https://clerk.house.gov/evs/{year}/roll{n:03d}.xml"
    st, b = cache_get(url, RAW / "votes" / "house" / str(year) / f"{n:03d}.xml")
    if st != 200 or not b: return None
    p = RAW / "votes" / "house" / str(year) / f"{n:03d}.xml"
    if b"vote-metadata" not in b:
        p.unlink(missing_ok=True); time.sleep(2); st, b = cache_get(url, p)
        if b"vote-metadata" not in b:
            p.unlink(missing_ok=True); pass
            return {"id": f"h{year}-{n}", "unreadable": True, "source_url": url}
    r = ET.fromstring(b); m = r.find("vote-metadata")
    g = lambda k: (m.findtext(k) or "").strip()
    pos, party = {}, {}
    for rv in r.iter("recorded-vote"):
        leg = rv.find("legislator"); bid = leg.get("name-id")
        v = (rv.findtext("vote") or "").strip()
        pos[bid] = MAP.get(v, v); party[bid] = leg.get("party")
    return {"id": f"h{year}-{n}", "chamber": "house", "congress": int(g("congress") or 0), "session": g("session"),
            "roll": n, "date": g("action-date"), "question": g("vote-question"), "type": g("vote-type"),
            "result": g("vote-result"), "legis": g("legis-num"), "desc": g("vote-desc"),
            "source_url": url, "positions": pos, "party": party}

def senate(session, n):
    url = f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote119{session}/vote_119_{session}_{n:05d}.xml"
    st, b = cache_get(url, RAW / "votes" / "senate" / str(session) / f"{n:05d}.xml")
    if st != 200 or not b or b"<roll_call_vote" not in b: return None
    r = ET.fromstring(b)
    g = lambda k: (r.findtext(k) or "").strip()
    pos, party = {}, {}
    for mem in r.iter("member"):
        bid = LIS2BIO.get((mem.findtext("lis_member_id") or "").strip())
        v = (mem.findtext("vote_cast") or "").strip()
        if bid: pos[bid] = MAP.get(v, v); party[bid] = (mem.findtext("party") or "").strip()
    doc = r.find("document")
    legis = ""
    if doc is not None:
        legis = f"{(doc.findtext('document_type') or '').strip()} {(doc.findtext('document_number') or '').strip()}".strip()
    return {"id": f"s119-{session}-{n}", "chamber": "senate", "congress": 119, "session": str(session), "roll": n,
            "date": g("vote_date"), "question": g("vote_question_text") or g("question"), "type": g("majority_requirement"),
            "result": g("vote_result"), "legis": legis, "desc": g("vote_title") or g("vote_document_text"),
            "source_url": url.replace(".xml", ".htm"), "source_xml": url, "positions": pos, "party": party}

def run(fn, args_iter, stop_after_misses=8):
    out, misses, n = [], 0, 1
    with cf.ThreadPoolExecutor(4) as ex:
        while misses < stop_after_misses:
            batch = list(range(n, n + 20)); n += 20
            res = list(ex.map(lambda k: fn(*args_iter, k), batch))
            for x in res:
                if x and x.get("unreadable"): misses += 1; continue
                if x: out.append(x); misses = 0
                else: misses += 1
            time.sleep(0.5)
    return out

if __name__ == "__main__":
    which = sys.argv[1:] or ["house", "senate"]
    if "house" in which:
        hv = run(house, (2025,)) + run(house, (2026,))
        write_json(BUILD / "votes-house.json", {"retrieved_at": now_iso(), "source": "Office of the Clerk, U.S. House of Representatives (clerk.house.gov/evs)", "votes": hv})
        print("house votes", len(hv))
    if "senate" in which:
        sv = run(senate, (1,)) + run(senate, (2,))
        write_json(BUILD / "votes-senate.json", {"retrieved_at": now_iso(), "source": "U.S. Senate Legislative Information System (senate.gov roll call votes)", "votes": sv})
        print("senate votes", len(sv))
