"""Automated verifier (Verification Standard step 2).
Re-fetches every claim's source live and checks the cited value is really there.
Claims that fail or cannot be checked are marked 'blocked' and will not render.
API keys are added at request time from env vars and never written to disk or logs."""
import sys, re, json, time, threading, collections, html as H
import concurrent.futures as cf
import xml.etree.ElementTree as ET
from common import *
import votes as V
from metrics import member_metrics

CLAIMS = BUILD / "site" / "claims.json"
CONG_KEY = api_key("CONGRESS_API_KEY"); FEC_KEY = api_key("FEC_API_KEY")
_cache, _lock = {}, threading.Lock()
_fec_lock = threading.Lock(); _fec_last = [0.0]

def live(url):
    with _lock:
        if url in _cache: return _cache[url]
    if "api.congress.gov" in url:
        st, b = fetch(url, headers={"X-Api-Key": CONG_KEY, "Accept": "application/json"}, timeout=60)
    elif "api.open.fec.gov" in url:
        with _fec_lock:  # FEC allows ~60 requests/minute per key
            wait = 1.05 - (time.time() - _fec_last[0])
            if wait > 0: time.sleep(wait)
            for attempt in range(40):  # FEC keys are limited per hour; wait patiently instead of blocking claims
                st, b = fetch(url + ("&" if "?" in url else "?") + "api_key=" + FEC_KEY, timeout=60, retries=1)
                if st not in (0, 429): break
                time.sleep(60)
            _fec_last[0] = time.time()
    else:
        st, b = fetch(url, timeout=60)
    res = (st, b)
    with _lock: _cache[url] = res
    return res

def jpath(obj, path):
    for part in path.split("."):
        m = re.match(r"^(\w+)(?:\[(-?\d+)\])?$", part)
        obj = obj[m.group(1)]
        if m.group(2) is not None: obj = obj[int(m.group(2))]
    return obj

def check(c, vote_sets):
    k = c["check"]; kind = k["kind"]
    if kind == "congress-member":
        st, b = live(k["url"])
        if st != 200: return False, f"source HTTP {st}"
        m = json.loads(b)["member"]
        for path, exp in k["fields"].items():
            got = jpath(m, path)
            if got != exp: return False, f"{path}: expected {exp!r}, source has {got!r}"
        return True, "fields match"
    if kind == "house-committee":
        st, b = live(k["url"])
        if st != 200: return False, f"source HTTP {st}"
        r = ET.fromstring(b)
        for m in r.iter("member"):
            if m.findtext("member-info/bioguideID") == k["bioguide"]:
                ok = any(x.get("comcode") == k["comcode"] for x in m.findall("committee-assignments/committee"))
                return ok, "assignment present" if ok else "assignment not found"
        return False, "member not in roster"
    if kind == "senate-committee":
        st, b = live(k["url"])
        if st != 200 or b"<committee_membership" not in b: return False, f"source HTTP {st}"
        r = ET.fromstring(b)
        ok = any((m.findtext("name/last") or "").strip() == k["last"] and (m.findtext("state") or "").strip() == k["state"] for m in r.findall("committees/members/member"))
        return ok, "member present" if ok else "member not on roster"
    if kind == "congress-list":
        st, b = live(k["url"])
        if st != 200: return False, f"source HTTP {st}"
        items = json.loads(b).get(k["list"], [])
        ok = any(all(str(it.get(f)) == str(v) for f, v in k["match"].items()) for it in items)
        return ok, "item present" if ok else "item not found in source list"
    if kind == "cosponsor-count":
        sa, ba = live(k["a"]); sb, bb = live(k["b"])
        if sa != 200 or sb != 200: return False, "source unavailable"
        A = {(i["type"], i["number"]) for i in json.loads(ba).get("cosponsoredLegislation", []) if i.get("congress") == 119 and i.get("type")}
        B = {(i["type"], i["number"]) for i in json.loads(bb).get("sponsoredLegislation", []) if i.get("congress") == 119 and i.get("type")}
        n = len(A & B)
        return n == k["expected"], f"recomputed {n}"
    if kind == "fec-totals":
        FEC_DONE.wait()
        cand = re.search(r"candidate_id=(\w+)", k["url"]).group(1)
        r = FEC_BATCH.get(cand)
        if r is None:
            st, b = live(k["url"])
            if st != 200: return False, f"source HTTP {st}"
            rs = json.loads(b).get("results", [])
            r = rs[0] if rs else {}
        got = r.get(k["field"])
        return (got is not None and abs(float(got) - float(k["expected"])) < 0.005), f"source has {got}"
    if kind == "fec-schedule-a":
        st, b = live(k["url"])
        if st != 200: return False, f"source HTTP {st}"
        rows = json.loads(b).get("results", [])
        mt = k["match"]
        ok = any(r.get("contributor_id") == mt["contributor_id"] and abs((r.get("contribution_receipt_amount") or 0) - mt["contribution_receipt_amount"]) < 0.005
                 and (r.get("contribution_receipt_date") or "")[:10] == (mt["contribution_receipt_date"] or "")[:10] for r in rows)
        return ok, "receipt present" if ok else "receipt not found"
    if kind == "fec-agg":
        st, b = live(k["url"])
        if st != 200: return False, f"source HTTP {st}"
        mt = k["match"]
        ok = any(r.get("committee_id") == mt["committee_id"] and abs(float(r.get("total") or 0) - float(mt["total"])) < 0.005 for r in json.loads(b).get("results", []))
        return ok, "aggregate present" if ok else "aggregate not found or changed"
    if kind in ("house-vote", "senate-vote"):
        vs = vote_sets.get(k["url"])
        if vs is None: return False, "roll call unavailable"
        got = vs["positions"].get(k["bioguide"])
        return got == k["expected"], f"source position {got}"
    if kind == "derived-votes":
        vl = vote_sets.get("__" + k["chamber"])
        if not vl: return False, "vote set unavailable"
        mm = member_metrics(k["bioguide"], vl)
        got = mm["missed"] if k["metric"] == "missed" else mm[k["metric"]]
        return got == k["expected"], f"recomputed {got}"
    if kind == "text-lines":
        st, b = live(k["url"])
        if st != 200: return False, f"source HTTP {st}"
        t = re.sub(r"<script.*?</script>|<style.*?</style>", "", b.decode("utf-8", "ignore"), flags=re.S)
        L = [re.sub(r"\s+", " ", l).strip() for l in H.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if l.strip()]
        want = k["lines"]
        ok = any(L[i:i + len(want)] == want for i in range(len(L)))
        return ok, "excerpt present" if ok else "excerpt not found"
    if kind == "state-results":
        import elections as E
        key = ("state-results", k["state"], k["url"])
        with _lock: hit = _cache.get(key)
        if hit is None:
            st, b = E.fetch_one(k["state"], k["url"])
            hit = (st, E.parse_one(k["state"], k["url"], b) if st == 200 and b else None)
            with _lock: _cache[key] = hit
        st, races = hit
        if st != 200 or races is None: return False, f"official source HTTP {st}"
        r = next((r for r in races if r["cls"][0] == k["office"] and r["cls"][1] == k["district"]), None)
        if not r: return False, "contest not found on official source"
        got = [[c["name"], c["votes"]] for c in r["candidates"]]
        return got == k["candidates"], "candidates and vote counts match the official source" if got == k["candidates"] else "official counts have changed; rebuild needed"
    if kind == "rollcall-xml":
        st, b = live(k["url"])
        if st != 200 or not b: return False, f"source HTTP {st}"
        try:
            r = ET.fromstring(b)
        except ET.ParseError:
            return False, "roll call XML could not be parsed"
        pos = {}
        if k.get("chamber") == "senate":
            for mem in r.iter("member"):
                bid = V.LIS2BIO.get((mem.findtext("lis_member_id") or "").strip())
                x = (mem.findtext("vote_cast") or "").strip()
                if bid: pos[bid] = V.MAP.get(x, x)
        else:
            for rv in r.iter("recorded-vote"):
                leg = rv.find("legislator")
                if leg is None: continue
                x = (rv.findtext("vote") or "").strip()
                pos[leg.get("name-id")] = V.MAP.get(x, x)
        got = pos.get(k["bioguide"])
        want = k["expected"]
        ok = got == want or got == V.MAP.get(want, want)
        return ok, f"source position {got}"
    if kind == "primary-excerpt":
        st, b = live(k["url"])
        if st != 200: return False, f"source HTTP {st}"
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b.decode("utf-8", "ignore"), flags=re.S | re.I)
        text = H.unescape(re.sub(r"<[^>]+>", " ", text))
        text = re.sub(r"\s+", " ", text)
        excerpt = re.sub(r"\s+", " ", (k.get("excerpt") or "")).strip()
        name = (k.get("name") or "").strip()
        if not excerpt: return False, "missing excerpt"
        if not name: return False, "missing member name"
        if name not in excerpt: return False, "excerpt does not include the member's name"
        if excerpt not in text: return False, "excerpt not found"
        if name not in text: return False, "member name not found on source page"
        return True, "excerpt and name present"
    return False, f"unknown check kind {kind}"


FEC_BATCH = {}
FEC_DONE = threading.Event()
def prefetch_fec_totals(claims):
    """Live re-fetch of candidate totals in batches of 50 IDs (same endpoint and filters as each claim's check URL)."""
    import urllib.parse
    ids = sorted({re.search(r"candidate_id=(\w+)", c["check"]["url"]).group(1) for c in claims.values() if c["check"]["kind"] == "fec-totals"})
    for i in range(0, len(ids), 50):
        q = [("cycle", 2026), ("election_full", "false"), ("per_page", 100)] + [("candidate_id", x) for x in ids[i:i+50]]
        st, b = live("https://api.open.fec.gov/v1/candidates/totals/?" + urllib.parse.urlencode(q))
        if st == 200:
            for r in json.loads(b).get("results", []): FEC_BATCH[r["candidate_id"]] = r
    FEC_DONE.set()
    print("fec totals prefetched", len(FEC_BATCH), "of", len(ids), flush=True)

def refetch_votes(chambers):
    """Re-download every roll call fresh (not from the ingest cache) for vote and derived claims."""
    out = {}
    def h(year, n):
        url = f"https://clerk.house.gov/evs/{year}/roll{n:03d}.xml"; st, b = live(url)
        if st != 200 or b"vote-metadata" not in b: return None
        p = RAW / "verify-tmp.xml"
        return url, b
    jobs = []
    src = {}
    for ch in chambers:
        d = read_json(BUILD / f"votes-{ch}.json")
        for v in d["votes"]:
            src[v.get("source_xml") or v["source_url"]] = (ch, v)
    def one(item):
        url, (ch, v) = item
        st, b = live(url)
        if st != 200 or not b: return url, ch, None
        try:
            r = ET.fromstring(b)
        except ET.ParseError:
            return url, ch, None
        pos, party = {}, {}
        if ch == "house":
            for rv in r.iter("recorded-vote"):
                leg = rv.find("legislator"); x = (rv.findtext("vote") or "").strip()
                pos[leg.get("name-id")] = V.MAP.get(x, x); party[leg.get("name-id")] = leg.get("party")
        else:
            for mem in r.iter("member"):
                bid = V.LIS2BIO.get((mem.findtext("lis_member_id") or "").strip()); x = (mem.findtext("vote_cast") or "").strip()
                if bid: pos[bid] = V.MAP.get(x, x); party[bid] = (mem.findtext("party") or "").strip()
        return url, ch, {**v, "positions": pos, "party": party}
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, src.items()))
    for attempt in range(4):  # retry transient failures before declaring a roll call unavailable
        bad = [r[0] for r in res if r[2] is None]
        if not bad: break
        time.sleep(20 * (attempt + 1))
        with _lock:
            for u in bad: _cache.pop(u, None)
        fixed = {r[0]: r for r in map(one, [(u, src[u]) for u in bad])}
        res = [fixed.get(r[0], r) for r in res]
    by_ch = collections.defaultdict(list); missing = 0; miss_ch = collections.Counter()
    order = {u: i for i, u in enumerate(src)}
    for url, ch, v in sorted(res, key=lambda r: order[r[0]]):
        if v is None: missing += 1; miss_ch[ch] += 1; continue
        out[url] = v; by_ch["__" + ch].append(v)
    # derived metrics require the complete vote set: if any roll call could not be re-fetched, derived claims are blocked
    for ch in chambers:
        if miss_ch[ch]: out["__" + ch] = None
        else: out["__" + ch] = by_ch["__" + ch]
    print("refetched roll calls", len(src) - missing, "missing", dict(miss_ch), flush=True)
    return out

def save(data, claims, t0, note=""):
    stats = collections.Counter((c["check"]["kind"], c.get("status")) for c in claims.values())
    data["verification"] = {"started": t0, "checkpoint": now_iso(), "note": note,
                            "counts": {f"{k}:{s}": n for (k, s), n in sorted(stats.items())}}
    write_json(CLAIMS, data)
    fails = [{"id": c["id"], "kind": c["check"]["kind"], "text": c["text"], "note": c.get("verify_note")} for c in claims.values() if c.get("status") == "blocked"]
    write_json(BUILD / "site" / "verification-report.json", {**data["verification"], "blocked": fails})

def main():
    """Stages (each checkpoints claims.json):
       --stage records : everything except FEC (Congress.gov, Clerk/Senate XML, rosters, White House)
       --stage elections : 2026 official state election results claims (ids e_*)
       --stage side-by-side : On the record Record A/B claims (rollcall-xml, primary-excerpt)
       --stage fec     : FEC claims (rate-limited key; resumable, checkpoints every 50 URLs)
       --only-blocked  : re-check only claims not yet verified."""
    data = read_json(CLAIMS); claims = data["claims"]; t0 = now_iso()
    stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "records"
    only_pending = "--only-blocked" in sys.argv
    is_fec = lambda c: c["check"]["kind"].startswith("fec")
    is_el = lambda c: c["id"].startswith("e_")
    is_sbs = lambda c: c["check"]["kind"] in ("rollcall-xml", "primary-excerpt") or c["id"].startswith("sbs_")
    sel = {"fec": lambda c: is_fec(c), "elections": lambda c: is_el(c), "side-by-side": lambda c: is_sbs(c),
           "records": lambda c: not is_fec(c) and not is_el(c) and not is_sbs(c)}[stage]
    pend = {i: c for i, c in claims.items() if sel(c) and not (only_pending and c.get("status") == "verified")}
    print("stage", stage, "claims to check", len(pend), flush=True)
    vote_sets = {}
    if stage == "fec":
        prefetch_fec_totals(pend)
    elif any(c["check"]["kind"] in ("house-vote", "senate-vote", "derived-votes") for c in pend.values()):
        vote_sets = refetch_votes(["house", "senate"])
    def run(c):
        try: ok, note = check(c, vote_sets)
        except Exception as e: ok, note = False, f"check error: {type(e).__name__}"
        return c["id"], ok, note
    items = list(pend.values())
    if stage == "fec":
        items.sort(key=lambda c: c["check"]["url"])
    workers = 1 if stage == "fec" else 8
    done = 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for i, ok, note in ex.map(run, items):
            c = claims[i]; c["status"] = "verified" if ok else "blocked"; c["verified_at"] = now_iso(); c["verify_note"] = note
            done += 1
            if stage == "fec" and done % 500 == 0: save(data, claims, t0, f"fec checkpoint {done}/{len(items)}"); print("fec", done, flush=True)
    save(data, claims, t0, f"stage {stage} complete")
    print(json.dumps(data["verification"], indent=1))

if __name__ == "__main__":
    main()
