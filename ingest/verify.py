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
        st, b = 0, b""
        for attempt in range(20):
            st, b = fetch(url, headers={"X-Api-Key": CONG_KEY, "Accept": "application/json"}, timeout=60, retries=1)
            if st not in (0, 429):
                break
            time.sleep(60 if st == 429 else 15)
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
    # Cache successful (and definitive HTTP) responses only; let 429/timeouts be retried.
    if st not in (0, 429):
        with _lock:
            _cache[url] = res
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
    if kind == "fec-bulk-24k":
        CONN_DONE.wait()
        if not CONN_OK:
            return False, "official FEC bulk file could not be re-fetched"
        key = (k["recipient_id"], k["giver_id"], k.get("source_file") or "pas2")
        got = CONN_BULK["24k"].get(key)
        if not got:
            return False, "pair not present in re-fetched file"
        total, count = got
        ok = abs(total - float(k["expected_total"])) < 0.005 and count == int(k["expected_count"])
        return ok, f"re-summed {total} count {count}"
    if kind == "fec-bulk-24k-category":
        CONN_DONE.wait()
        if not CONN_OK:
            return False, "official FEC bulk file could not be re-fetched"
        want = set(k["recipient_ids"])
        code = k.get("org_type") or ""
        total = 0.0
        for (rid, gid, src), (amt, _n) in CONN_BULK["24k"].items():
            if rid not in want:
                continue
            ot = CONN_BULK["org_type"].get(gid, "")
            if ot == code:
                total += amt
        total = round(total, 2)
        ok = abs(total - float(k["expected_total"])) < 0.005
        return ok, f"re-summed {total}"
    if kind == "fec-bulk-ie":
        CONN_DONE.wait()
        if not CONN_OK:
            return False, "official FEC independent expenditure file could not be re-fetched"
        key = (k["spender_id"], k["candidate_id"], k["support_oppose"])
        got = CONN_BULK["ie"].get(key)
        if not got:
            return False, "spender-candidate-position not present in re-fetched file"
        total, count = got
        ok = abs(total - float(k["expected_total"])) < 0.005 and count == int(k["expected_count"])
        return ok, f"re-summed {total} count {count}"
    if kind == "lda-excerpt":
        st, b = live(k["url"])
        if st != 200 or not b:
            return False, f"source HTTP {st}"
        try:
            j = json.loads(b)
        except json.JSONDecodeError:
            return False, "LDA filing was not JSON"
        field = k.get("field") or "description"
        blobs = []
        for act in j.get("lobbying_activities") or []:
            if field == "covered_position":
                for lb in act.get("lobbyists") or []:
                    blobs.append(lb.get("covered_position") or "")
            else:
                blobs.append(act.get("description") or "")
        text = re.sub(r"\s+", " ", " ".join(blobs))
        excerpt = re.sub(r"\s+", " ", (k.get("excerpt") or "")).strip()
        excerpt = excerpt.strip(".…").strip()  # display ellipses are not part of the source
        if not excerpt:
            return False, "missing excerpt"
        if excerpt not in text:
            return False, "excerpt not found"
        if k.get("name") and k["name"] not in text:
            return False, "name not found in filing"
        return True, "excerpt present"
    if kind == "source-excerpt":
        st, b = live(k["url"])
        if st != 200 or not b:
            return False, f"source HTTP {st}"
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b.decode("utf-8", "ignore"), flags=re.S | re.I)
        text = H.unescape(re.sub(r"<[^>]+>", " ", text))
        text = re.sub(r"\s+", " ", text)
        missing = [n for n in (k.get("needles") or [k.get("excerpt")]) if n and n not in text]
        if missing:
            return False, "label not found on official description page"
        return True, "official labels present"
    return False, f"unknown check kind {kind}"


FEC_BATCH = {}
FEC_DONE = threading.Event()
CONN_BULK = {"24k": {}, "ie": {}, "org_type": {}}
CONN_DONE = threading.Event()
CONN_OK = False

def _download(url, dest):
    dest = Path(dest) if not isinstance(dest, type(Path("."))) else dest
    st, b = live(url)
    if st != 200 or not b:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b)
    return True

def prefetch_connection_files():
    """Live re-fetch of official FEC bulk files used by Connections claims; parse once."""
    import zipfile, io, csv, tempfile
    from pathlib import Path as P
    global CONN_OK
    tmp = P(tempfile.mkdtemp(prefix="politidex-conn-"))
    ok = True
    files = {
        "pas2": "https://www.fec.gov/files/bulk-downloads/2026/pas226.zip",
        "oth": "https://www.fec.gov/files/bulk-downloads/2026/oth26.zip",
        "cm": "https://www.fec.gov/files/bulk-downloads/2026/cm26.zip",
        "ie": "https://www.fec.gov/files/bulk-downloads/2026/independent_expenditure_2026.csv",
    }
    need_24k = CONN_BULK.get("need_24k", True)
    need_ie = CONN_BULK.get("need_ie", True)
    blobs = {}
    for key, url in files.items():
        if key == "oth":
            continue  # streamed to disk below
        if key in ("pas2", "cm") and not need_24k:
            continue
        if key == "ie" and not need_ie:
            continue
        print("re-fetching", url, flush=True)
        st, b = live(url)
        if st != 200 or not b:
            print("failed", url, "HTTP", st, flush=True)
            ok = False
            continue
        blobs[key] = b
        print("fetched", key, "bytes", len(b), flush=True)
    if not ok:
        CONN_OK = False
        CONN_DONE.set()
        return

    def unzip_txt(blob, prefer):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = z.namelist()
            name = next((n for n in names if n.lower().endswith(prefer)), names[0])
            return z.read(name)

    def add_24k(text, source_file, only_lp=None):
        n = 0
        for line in text.splitlines():
            c = line.split(b"|" if isinstance(line, bytes) else "|")
            if isinstance(c[0], bytes):
                c = [x.decode("utf-8", "replace") for x in c]
            if len(c) < 20 or c[5].strip() != "24K":
                continue
            rid, gid = c[15].strip(), c[0].strip()
            if only_lp is not None and rid not in only_lp:
                continue
            if c[19].strip() == "X":
                continue
            try:
                amt = float(c[14] or 0)
            except ValueError:
                continue
            key = (rid, gid, source_file)
            tot, cnt = CONN_BULK["24k"].get(key, (0.0, 0))
            CONN_BULK["24k"][key] = (round(tot + amt, 2), cnt + 1)
            n += 1
        return n

    def add_24k_path(path, source_file, only_lp=None):
        n = 0
        with open(path, errors="replace") as fh:
            for line in fh:
                c = line.split("|")
                if len(c) < 20 or c[5].strip() != "24K":
                    continue
                rid, gid = c[15].strip(), c[0].strip()
                if only_lp is not None and rid not in only_lp:
                    continue
                if c[19].strip() == "X":
                    continue
                try:
                    amt = float(c[14] or 0)
                except ValueError:
                    continue
                key = (rid, gid, source_file)
                tot, cnt = CONN_BULK["24k"].get(key, (0.0, 0))
                CONN_BULK["24k"][key] = (round(tot + amt, 2), cnt + 1)
                n += 1
        return n

    if need_24k:
        pas2 = unzip_txt(blobs["pas2"], "itpas2.txt")
        print("pas2 24K rows", add_24k(pas2.decode("utf-8", "replace"), "pas2"), flush=True)
        cm_txt = unzip_txt(blobs["cm"], "cm.txt").decode("utf-8", "replace")
        lp = set()
        for line in cm_txt.splitlines():
            c = line.split("|")
            if len(c) < 13:
                continue
            cid = c[0].strip()
            CONN_BULK["org_type"][cid] = c[12].strip()
            if c[8].strip() == "D":
                lp.add(cid)
        lp |= CONN_BULK.get("oth_recipients") or set()
        # Stream the large OTH file to disk; do not keep the unzipped text in memory.
        import urllib.request
        oth_zip = tmp / "oth26.zip"
        oth_txt = tmp / "itoth.txt"
        print("re-fetching OTH to disk", files["oth"], flush=True)
        req = urllib.request.Request(files["oth"], headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=600) as r, open(oth_zip, "wb") as fh:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
                st_oth = r.status
        except Exception as e:
            print("OTH download failed", type(e).__name__, flush=True)
            CONN_OK = False
            CONN_DONE.set()
            return
        if st_oth != 200:
            print("OTH HTTP", st_oth, flush=True)
            CONN_OK = False
            CONN_DONE.set()
            return
        with zipfile.ZipFile(oth_zip) as z:
            name = next((n for n in z.namelist() if n.lower().endswith("itoth.txt")), z.namelist()[0])
            with z.open(name) as src, open(oth_txt, "wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
        oth_zip.unlink(missing_ok=True)
        print("oth 24K to LPs", add_24k_path(oth_txt, "oth", only_lp=lp), flush=True)
        oth_txt.unlink(missing_ok=True)

    if need_ie:
        # Same notice/report dedupe as ingest/connections_fec.dedupe_ie_rows.
        import csv as _csv
        from connections_fec import dedupe_ie_rows
        rdr = _csv.DictReader(io.StringIO(blobs["ie"].decode("utf-8", "replace")))
        kept, _stats = dedupe_ie_rows(list(rdr))
        for row in kept:
            so = (row.get("sup_opp") or "").strip().upper()
            if so not in ("S", "O"):
                continue
            try:
                amt = float(row.get("exp_amo") or 0)
            except ValueError:
                continue
            key = ((row.get("spe_id") or "").strip(), (row.get("cand_id") or "").strip(), so)
            tot, cnt = CONN_BULK["ie"].get(key, (0.0, 0))
            CONN_BULK["ie"][key] = (round(tot + amt, 2), cnt + 1)
        print("ie pairs", len(CONN_BULK["ie"]), flush=True)
    CONN_OK = True
    CONN_DONE.set()

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
    global CONN_OK
    """Stages (each checkpoints claims.json):
       --stage records : everything except FEC (Congress.gov, Clerk/Senate XML, rosters, White House)
       --stage elections : 2026 official state election results claims (ids e_*)
       --stage side-by-side : On the record Record A/B claims (rollcall-xml, primary-excerpt)
       --stage fec     : FEC claims (rate-limited key; resumable, checkpoints every 50 URLs)
       --stage connections : FEC bulk 24K / IE re-sums and LDA excerpt checks
       --only-blocked  : re-check only claims not yet verified."""
    data = read_json(CLAIMS); claims = data["claims"]; t0 = now_iso()
    stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "records"
    only_pending = "--only-blocked" in sys.argv
    CONN_KINDS = {"fec-bulk-24k", "fec-bulk-24k-category", "fec-bulk-ie", "lda-excerpt", "source-excerpt"}
    is_conn = lambda c: c["check"]["kind"] in CONN_KINDS
    is_fec = lambda c: c["check"]["kind"].startswith("fec") and c["check"]["kind"] not in CONN_KINDS
    is_el = lambda c: c["id"].startswith("e_")
    is_sbs = lambda c: c["check"]["kind"] in ("rollcall-xml", "primary-excerpt") or c["id"].startswith("sbs_")
    sel = {"fec": lambda c: is_fec(c), "elections": lambda c: is_el(c), "side-by-side": lambda c: is_sbs(c),
           "connections": lambda c: is_conn(c),
           "records": lambda c: not is_fec(c) and not is_el(c) and not is_sbs(c) and not is_conn(c)}[stage]
    pend = {i: c for i, c in claims.items() if sel(c) and not (only_pending and c.get("status") == "verified")}
    print("stage", stage, "claims to check", len(pend), flush=True)
    vote_sets = {}
    if stage == "fec":
        prefetch_fec_totals(pend)
    elif stage == "connections":
        need_24k = any(c["check"]["kind"].startswith("fec-bulk-24k") for c in pend.values())
        need_ie = any(c["check"]["kind"] == "fec-bulk-ie" for c in pend.values())
        need_bulk = need_24k or need_ie
        if need_bulk:
            # Include every leadership-PAC recipient cited in oth claims so the
            # OTH scan is not limited to designation-D in the committee master.
            oth_recs = {c["check"]["recipient_id"] for c in pend.values()
                        if c["check"]["kind"] == "fec-bulk-24k" and c["check"].get("source_file") == "oth"}
            CONN_BULK["oth_recipients"] = oth_recs
            CONN_BULK["need_24k"] = need_24k
            CONN_BULK["need_ie"] = need_ie
            prefetch_connection_files()
        else:
            CONN_OK = True
            CONN_DONE.set()
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
            if done % 500 == 0:
                save(data, claims, t0, f"{stage} checkpoint {done}/{len(items)}")
                print(stage, done, flush=True)
    save(data, claims, t0, f"stage {stage} complete")
    print(json.dumps(data["verification"], indent=1))

if __name__ == "__main__":
    main()
