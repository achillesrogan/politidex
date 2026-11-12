"""2026 general election (Nov 3, 2026) results from OFFICIAL state election offices only.

Each state has an adapter: parse(bytes) -> list of races. The same parser is used by verify.py
(check kind 'state-results') so a claim is only verified if a fresh fetch of the official source,
parsed the same way, still shows exactly the same candidates and vote counts.

Inclusion rule (documented on /methodology and /elections-2026). We never call races; state offices
publish unofficial counts, and we only show who leads them when the fixed rule in status_for() is met:
  * certified: the official source itself says the results are official/certified.
  * leading (unofficial, not certified): reporting is 100% (every unit in, none partial), the margin is
    at least 1 point AND at least MARGIN_PTS (LATE_MARGIN_PTS in late-count states), and majority rules hold.
  * too_close: margin under 1 point, under the state's margin rule, or majority rule not met.
  * skipped: reporting under 100% (or not published), no votes, or write-ins lead.
"""
import re, sys, json, html as H, hashlib, subprocess, pathlib
from common import *

OUT = BUILD / "elections-2026.json"
RAWDIR = RAW / "elections-2026"
MARGIN_PTS = 3.0
LATE_MARGIN_PTS = 10.0
# States where large shares of ballots are routinely counted after election night (all-mail or
# late-arriving mail accepted); a "100% of precincts" figure does not mean the count is complete.
LATE_COUNT = {"CA", "WA", "OR", "AK", "NV", "UT", "CO", "AZ", "HI", "NY", "NJ", "IL", "MD", "VT"}
# Majority required: runoff (GA, LA, MS gov/...) or ranked-choice (AK, ME federal).
MAJORITY = {"GA", "LA", "AK", "ME"}

STATE_NAMES = {"AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"}

BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

def get(url, browser=None):
    """Fetch an official results URL. Some state sites reject non-browser clients; for those we
    send a browser user agent, or (browser='page:URL') load the state's own page in headless
    Chromium and read the data URL from inside it."""
    if browser == "text":  # render the official page in headless Chromium and read its visible text
        for attempt in range(3):
            try:
                r = subprocess.run(["node", str(ROOT / "ingest" / "browser_fetch.cjs"), url, "text", "6000"], capture_output=True, timeout=200)
                if r.returncode == 0 and len(r.stdout) > 500: return 200, r.stdout
            except subprocess.TimeoutExpired: pass
        return 0, b""
    if browser and browser.startswith("page:"):
        r = subprocess.run(["node", str(ROOT / "ingest" / "browser_fetch.cjs"), browser[5:], url], capture_output=True, timeout=180)
        return (200, r.stdout) if r.returncode == 0 and r.stdout else (0, b"")
    if url.startswith("clarity:"):  # Clarity ENR: resolve the current published version first
        base = url[8:].rstrip("/") + "/"
        st, v = fetch(base + "current_ver.txt", headers={"User-Agent": BROWSER_UA}, timeout=60)
        if st != 200: return st, b""
        url = base + _gunzip(v).decode().strip() + "/json/en/summary.json"
    if url.startswith("la:"):  # Louisiana: race/candidate list + vote totals are two official files
        base = url[3:]
        s1, a = fetch(base + "RacesCandidates_Multiparish.htm", headers={"User-Agent": BROWSER_UA}, timeout=90)
        s2, v = fetch(base + "Votes_Multiparish.htm", headers={"User-Agent": BROWSER_UA}, timeout=90)
        if s1 != 200 or s2 != 200: return (s1 if s1 != 200 else s2), b""
        return 200, json.dumps({"races": json.loads(_gunzip(a)), "votes": json.loads(_gunzip(v))}).encode()
    st, b = fetch(url, headers={"User-Agent": BROWSER_UA, "Accept": "*/*"}, timeout=90)
    return st, _gunzip(b)

def _gunzip(b):
    import gzip
    return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b

def lines_of_html(b):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", b.decode("utf-8", "ignore"), flags=re.S | re.I)
    return [re.sub(r"\s+", " ", l).strip() for l in H.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if l.strip()]

def num(s): return int(re.sub(r"[^\d]", "", str(s)) or 0)

ORD = {w: i for i, w in enumerate("ZERO FIRST SECOND THIRD FOURTH FIFTH SIXTH SEVENTH EIGHTH NINTH TENTH ELEVENTH TWELFTH THIRTEENTH FOURTEENTH FIFTEENTH SIXTEENTH SEVENTEENTH EIGHTEENTH NINETEENTH TWENTIETH".split())}

def classify(label):
    """Map an official contest label to (office, district, special). None if not a federal/governor race."""
    u = re.sub(r"\bU S\b", "US", re.sub(r"\s+", " ", label.upper().replace(".", " ").replace(",", " ")).strip())
    special = "SPECIAL" in u or "UNEXPIRED" in u
    if re.search(r"^(FOR )?(LIEUTENANT|LT) ?GOV", u) or ("GOVERNOR" in u and not re.search(r"(^|FOR |\b)GOVERNOR( AND| /|$| -| \()", u)): return None
    if re.search(r"\bGOVERNOR\b", u) and not re.search(r"BOARD OF GOVERNORS", u): return ("Governor", 0, special)
    if re.search(r"(US|UNITED STATES) SENAT", u): return ("U.S. Senate", 0, special)
    if re.search(r"(US|UNITED STATES) (HOUSE|REPRESENTATIVE|CONGRESS)|REPRESENTATIVE IN CONGRESS|CONGRESSIONAL|HOUSE OF REPRESENTATIVES", u) and not re.search(r"STATE (HOUSE|REP)|\b(?!US\b)[A-Z]{2} HOUSE OF REP|GENERAL ASSEMBLY|LEGISLAT|DELEGATES|BOARD|REGENT|EDUCATION|COMMISSION|JUDGE|COURT", u):
        w = re.search(r"\b(" + "|".join(ORD) + r") DISTRICT", u)
        if w: return ("U.S. House", ORD[w.group(1)], special)
        m = re.search(r"DISTRICT (?:NO )?0*(\d+)", u) or re.search(r"0*(\d+)(?:ST|ND|RD|TH)? (?:CONGRESSIONAL )?(?:DISTRICT|CONGRESSIONAL)", u) or re.search(r"(?<!VOTE FOR )\b0*(\d+)\b(?! YEAR)", u)
        if "AT LARGE" in u or "AT-LARGE" in u: return ("U.S. House", 0, special)
        return ("U.S. House", int(m.group(1)), special) if m else ("U.S. House", 0, special)
    return None

# ------------------------------------------------------------------ adapters
def parse_tx(b, cfg):
    L = lines_of_html(b); races = []
    for i, l in enumerate(L):
        c = classify(l) if l.isupper() and len(l) < 80 else None
        if not c or not L[i + 1].startswith("Polling Locations Reporting"): continue
        j = i + 5; cands = []
        while j + 2 < len(L) and not L[j + 1].startswith("Polling Locations Reporting") and re.match(r"^[\d,]+$", L[j + 2]):
            cands.append({"party": L[j].title(), "name": L[j + 1], "votes": num(L[j + 2])}); j += 3
        races.append({"label": l, "cls": c, "reporting": L[i + 1], "complete": L[i + 1].endswith("100%"),
                      "official": False, "candidates": cands, "excerpt": L[i:j]})
    return races

def _t(v):
    return v[0]["text"] if isinstance(v, list) and v else (v or "")

def parse_ev(b, cfg):
    d = json.loads(b); races = []
    official = bool(d.get("election", {}).get("isOfficialResults"))
    for it in d.get("ballotItems", []):
        label = _t(it.get("name")); c = classify(label)
        if not c or it.get("contestType") != "Candidate": continue
        rs = it.get("reportingStatus") or {}
        ru, tu = rs.get("reportingUnits"), rs.get("totalUnits")
        cands = []
        for o in (it.get("summaryResults") or {}).get("ballotOptions", []):
            nm = _t(o.get("name")); pty = _t((o.get("party") or {}).get("name"))
            cands.append({"name": nm, "party": pty, "votes": int(o.get("voteCount") or 0)})
        ex = [json.dumps(label)] + [f'{json.dumps(x["name"])}: "voteCount": {x["votes"]}' for x in cands] + [f'"reportingUnits": {ru}, "totalUnits": {tu}']
        races.append({"label": label, "cls": c, "reporting": f"{ru} of {tu} reporting units", "complete": bool(tu) and ru == tu,
                      "official": official, "candidates": cands, "excerpt": ex})
    return races

def parse_nc(b, cfg):
    rows = json.loads(b); by = {}
    for r in rows:
        by.setdefault(r["cnm"], []).append(r)
    races = []
    for label, rs in by.items():
        c = classify(label) if rs[0].get("ogl") == "FED" else None
        if not c: continue
        prt, ptl = num(rs[0]["prt"]), num(rs[0]["ptl"])
        cands = [{"name": r["bnm"], "party": r["pty"], "votes": num(r["vct"])} for r in rs]
        ex = [f'"cnm":"{label}"'] + [f'"bnm":"{r["bnm"]}" "pty":"{r["pty"]}" "vct":"{r["vct"]}"' for r in rs] + [f'"prt":"{rs[0]["prt"]}","ptl":"{rs[0]["ptl"]}"']
        races.append({"label": label, "cls": c, "reporting": f"{prt} of {ptl} precincts", "complete": prt == ptl and ptl > 0,
                      "official": False, "candidates": cands, "excerpt": ex})
    return races

def _official_flag(L):
    head = " ".join(L[:60]).upper()
    return ("UNOFFICIAL" not in head) and bool(re.search(r"\bOFFICIAL\b|CERTIFIED", head))

def parse_sw(b, cfg):
    """Civix-style 'resultsSW.aspx' pages (NE, NM, OR, ...): contest, precinct line, name|party|votes, 'total votes'."""
    L = lines_of_html(b); races = []
    official = _official_flag(L)
    for i, l in enumerate(L):
        if i + 1 >= len(L) or not L[i + 1].lower().startswith("follow this contest"): continue
        c = classify(l)
        if not c: continue
        k = next((k for k in range(i + 1, min(i + 8, len(L))) if re.search(r"Precincts Fully:|Precincts Reported", L[k])), None)
        if k is None: continue
        rep = L[k]
        m = re.search(r"Precincts Fully:\s*([\d,]+)\s*/\s*([\d,]+)", rep) or re.search(r"([\d,]+) out of ([\d,]+) Precincts Reported", rep)
        a, t = num(m.group(1)), num(m.group(2))
        j = k + 1; cands = []
        while j < len(L) and (L[j] in ("", "|") or L[j].startswith("Partially:")): j += 1
        while j < len(L) and L[j].lower() != "total votes":
            if re.match(r"^[\d,]+$", L[j + 1]):
                cands.append({"name": L[j], "party": "", "votes": num(L[j + 1])}); j += 2
            elif j + 2 < len(L) and re.match(r"^[\d,]+$", L[j + 2]):
                cands.append({"name": L[j], "party": L[j + 1], "votes": num(L[j + 2])}); j += 3
            else: break
        if j >= len(L) or L[j].lower() != "total votes" or not cands: continue
        complete = (a == t and t > 0) or (cfg.get("no_precinct_reporting") and a == 0)
        races.append({"label": l, "cls": c, "reporting": rep, "complete": bool(complete), "official": official,
                      "candidates": cands, "excerpt": [l, rep] + [x for cc in cands for x in ([cc["name"]] + ([cc["party"]] if cc["party"] else []) + [f'{cc["votes"]:,}'])] + ["total votes", L[j + 1]]})
    return races

def parse_md(b, cfg):
    L = lines_of_html(b); races = []
    official = not any("unofficial" in l.lower() and "results" in l.lower() for l in L) and any(re.search(r"^Official .*Results", l) for l in L)
    for i, l in enumerate(L):
        if l not in ("Governor / Lt. Governor", "Representative in Congress", "U.S. Senator"): continue
        if i + 1 >= len(L): continue
        label = l + (" " + L[i + 1] if L[i + 1].startswith("District") else "")
        c = classify(label.replace("Representative in Congress", "Representative in Congress"))
        if not c: continue
        k = next((k for k in range(i, min(i + 8, len(L))) if re.search(r"precincts reported", L[k])), None)
        if k is None: continue
        m = re.search(r"\((\d[\d,]*) of (\d[\d,]*) election day precincts reported\)", L[k])
        try: h = L.index("Percentage", k)
        except ValueError: continue
        j = h + 1; cands = []
        while j + 7 < len(L) and re.match(r"^[\d.]+%$", L[j + 7] or ""):
            cands.append({"name": L[j], "party": L[j + 1], "votes": num(L[j + 6])}); j += 8
        if not cands: continue
        races.append({"label": label, "cls": c, "reporting": L[k], "complete": bool(m) and num(m.group(1)) == num(m.group(2)),
                      "official": official, "candidates": cands, "excerpt": [l] + ([L[i + 1]] if L[i + 1].startswith("District") else []) + [L[k]] + L[h - 7:j]})
    return races

def parse_fl(b, cfg):
    L = lines_of_html(b); races = []
    head = " ".join(L[:40])
    official = "Official Results" in head and "Unofficial" not in head
    complete = official  # 100% reporting is confirmed separately from the County Reporting Status page (see main)
    rep = next((l for l in L[:40] if "Set of Unofficial Returns" in l or "Official" in l), "")
    for i, l in enumerate(L):
        if i + 6 >= len(L) or L[i + 1] != "General" or L[i + 2] != "Contest Results by County": continue
        c = classify(l)
        if not c: continue
        try: h = L.index("Votes Received", i)
        except ValueError: continue
        j = h + 1; cands = []
        while j + 3 < len(L) and re.match(r"^[\d,]+$", L[j + 2]) and re.match(r"^[\d.]+%$", L[j + 3]):
            cands.append({"name": L[j], "party": L[j + 1], "votes": num(L[j + 2])}); j += 4
        if not cands or not L[j].startswith("Total"): continue
        races.append({"label": l, "cls": c, "reporting": rep, "complete": complete, "official": official,
                      "candidates": cands, "excerpt": L[i:j + 1]})
    return races

def parse_clarity(b, cfg):
    d = json.loads(b); races = []
    for x in d:
        c = classify(x["C"])
        if not c: continue
        cands = [{"name": n, "party": p or "", "votes": int(v)} for n, p, v in zip(x["CH"], x["P"], x["V"])]
        ex = [f'"C": {json.dumps(x["C"])}', f'"CH": {json.dumps(x["CH"])}', f'"P": {json.dumps(x["P"])}', f'"V": {json.dumps(x["V"])}', f'"TP": {x["TP"]}, "PR": {x["PR"]}']
        races.append({"label": x["C"], "cls": c, "reporting": f'{x["PR"]} of {x["TP"]} precincts reporting', "complete": x["TP"] > 0 and x["PR"] == x["TP"],
                      "official": False, "candidates": cands, "excerpt": ex})
    return races

def parse_la(b, cfg):
    d = json.loads(b); races = []
    votes = {r["ID"]: r for r in d["votes"]["Races"]["Race"]}
    for r in d["races"]["Races"]["Race"]:
        c = classify(r["SpecificTitle"])
        if not c or r["ID"] not in votes: continue
        v = votes[r["ID"]]; vc = {x["ID"]: x for x in v["Choice"]}
        cands = []
        for ch in r["Choice"]:
            m = re.match(r"^(.*?)\s*\(([A-Z]+)\)$", ch["Desc"])
            cands.append({"name": m.group(1) if m else ch["Desc"], "party": m.group(2) if m else "", "votes": num(vc.get(ch["ID"], {}).get("VoteTotal", 0)),
                          "outcome": vc.get(ch["ID"], {}).get("Outcome", "")})
        pr, pe = num(v["PrecinctsReporting"]), num(v["PrecinctsExpected"])
        ex = [f'"SpecificTitle":"{r["SpecificTitle"]}"'] + [f'"Desc":"{ch["Desc"]}" "VoteTotal":"{vc.get(ch["ID"], {}).get("VoteTotal")}" "Outcome":"{vc.get(ch["ID"], {}).get("Outcome")}"' for ch in r["Choice"]] + [f'"PrecinctsReporting":"{v["PrecinctsReporting"]}","PrecinctsExpected":"{v["PrecinctsExpected"]}"']
        races.append({"label": r["SpecificTitle"], "cls": c, "reporting": f"{pr} of {pe} precincts", "complete": pe > 0 and pr == pe,
                      "official": False, "candidates": cands, "excerpt": ex})
    return races

def text_lines(b):
    return [re.sub(r"\s+", " ", l).strip() for l in b.decode("utf-8", "ignore").split("\n") if l.strip()]

def parse_ca(b, cfg):
    L = text_lines(b); races = []
    t = next((i for i, l in enumerate(L) if re.search(r" - (Districtwide|Statewide) Results$", l)), None)
    if t is None: return races
    label = re.sub(r" - (Districtwide|Statewide) Results$", "", L[t]); c = classify(label)
    if not c: return races
    k = next(i for i in range(t, len(L)) if re.match(r"^\( [\d,]+ of [\d,]+ \) precincts", L[i]))
    m = re.match(r"^\( ([\d,]+) of ([\d,]+) \) precincts", L[k])
    h = next(i for i in range(k, len(L)) if L[i].startswith("Candidate Votes Percent"))
    j = h + 1; cands = []
    while j + 3 < len(L) and L[j + 1].startswith("(Party Preference:") and re.match(r"^[\d,]+$", L[j + 2]):
        cands.append({"name": L[j], "party": L[j + 1][len("(Party Preference: "):-1], "votes": num(L[j + 2])}); j += 4
    official = "Unofficial Election Results" not in L[:12] and "Official" in " ".join(L[:12])
    races.append({"label": label, "cls": c, "reporting": L[k] + " " + L[k + 1], "complete": num(m.group(1)) == num(m.group(2)),
                  "official": official, "candidates": cands, "excerpt": [L[t], L[k], L[k + 1]] + L[h + 1:j]})
    return races

def parse_tn(b, cfg):
    L = text_lines(b); races = []
    for i, l in enumerate(L):
        if i + 3 >= len(L) or not L[i + 2].endswith("Counties Completed") or not L[i + 3].startswith("View County Breakdown"): continue
        c = classify(l)
        if not c: continue
        m = re.match(r"^([\d,]+) of ([\d,]+) Counties Completed$", L[i + 2])
        j = i + 5; cands = []
        while j < len(L):
            mm = re.match(r"^(.*) \(([A-Z]+)\) - ([\d,]+)$", L[j])
            if not mm: break
            cands.append({"name": mm.group(1), "party": mm.group(2), "votes": num(mm.group(3))}); j += 1
            if j < len(L) and L[j] == "\u2714": j += 1
            if j < len(L) and re.match(r"^[\d.]+%$", L[j]): j += 1
        if not cands: continue
        races.append({"label": l, "cls": c, "reporting": L[i + 1] + "; " + L[i + 2], "complete": bool(m) and m.group(1) == m.group(2),
                      "official": L[i + 1].lower().startswith("official") or L[i + 1].lower().startswith("certified"),
                      "candidates": cands, "excerpt": L[i:j]})
    return races

def parse_in(b, cfg):
    d = json.loads(b); races = []
    for r in d["Root"]["StatewideSummary"]["Race"]:
        c = classify(r["OFFICE_TITLE"])
        if not c: continue
        cs = r["Candidates"]["Candidate"]; cs = cs if isinstance(cs, list) else [cs]
        cands = [{"name": x["NAME_ON_BALLOT"], "party": x["PARTY"], "votes": int(x["TOTAL"]), "state_winner": x.get("isWinner") == "T"} for x in cs]
        ex = [f'"OFFICE_TITLE": "{r["OFFICE_TITLE"]}"'] + [f'"NAME_ON_BALLOT": "{x["NAME_ON_BALLOT"]}", "isWinner": "{x.get("isWinner")}", ... "TOTAL": {x["TOTAL"]}' for x in cs]
        races.append({"label": r["OFFICE_TITLE"], "cls": c, "reporting": "per-contest reporting not published in this file", "complete": False,
                      "official": False, "candidates": cands, "excerpt": ex})
    return races

ADAPTERS = {"in": parse_in, "tn": parse_tn, "ca": parse_ca, "la": parse_la, "clarity": parse_clarity, "fl": parse_fl, "tx": parse_tx, "ev": parse_ev, "nc": parse_nc, "sw": parse_sw, "md": parse_md}

# ------------------------------------------------------------------ state sources
SOURCES = {
    "TX": {"adapter": "tx", "source_name": "Texas Secretary of State — Election Results",
           "page": "https://electionresults.sos.state.tx.us/results.html", "data": "https://electionresults.sos.state.tx.us/results.html"},
    "GA": {"adapter": "ev", "source_name": "Georgia Secretary of State — Election Results",
           "page": "https://results.sos.ga.gov/results/public/Georgia/elections/11032026GeneralAndSpecialElection",
           "data": "https://results.sos.ga.gov/results/public/api/elections/Georgia/11032026GeneralAndSpecialElection/data"},
    "WA": {"adapter": "ev", "source_name": "Washington Secretary of State — Election Results",
           "page": "https://results.votewa.gov/results/public/washington/elections/20261103",
           "data": "https://results.votewa.gov/results/public/api/elections/washington/20261103/data"},
    "UT": {"adapter": "ev", "source_name": "Utah Lieutenant Governor's Office — Election Results",
           "page": "https://electionresults.utah.gov/results/public/Utah/elections/General11032026",
           "data": "https://electionresults.utah.gov/results/public/api/elections/Utah/General11032026/data"},
    "VA": {"adapter": "ev", "source_name": "Virginia Department of Elections — Election Results",
           "page": "https://enr.elections.virginia.gov/results/public/Virginia/elections/2026-November-General",
           "data": "https://enr.elections.virginia.gov/results/public/api/elections/Virginia/2026-November-General/data"},
    "NC": {"adapter": "nc", "source_name": "North Carolina State Board of Elections — Election Results",
           "page": "https://er.ncsbe.gov/?election_dt=11/03/2026&county_id=0&office=FED&contest=0",
           "data": "https://er.ncsbe.gov/enr/20261103/data/results_0.txt"},
    "NE": {"adapter": "sw", "source_name": "Nebraska Secretary of State — Election Results",
           "page": "https://electionresults.nebraska.gov/resultsSW.aspx?type=SW&map=CTY",
           "data": ["https://electionresults.nebraska.gov/resultsSW.aspx?type=SW&map=CTY", "https://electionresults.nebraska.gov/resultsSW.aspx?type=CG&map=DIST"]},
    "NM": {"adapter": "sw", "source_name": "New Mexico Secretary of State — Election Results",
           "page": "https://electionresults.sos.nm.gov/resultsSW.aspx?type=FED&map=CTY",
           "data": ["https://electionresults.sos.nm.gov/resultsSW.aspx?type=FED&map=CTY", "https://electionresults.sos.nm.gov/resultsSW.aspx?type=SW&map=CTY"]},
    "OR": {"adapter": "sw", "source_name": "Oregon Secretary of State — Election Results", "no_precinct_reporting": True,
           "page": "https://results.oregonvotes.gov/resultsSW.aspx?type=FED&map=CTY",
           "data": ["https://results.oregonvotes.gov/resultsSW.aspx?type=FED&map=CTY", "https://results.oregonvotes.gov/resultsSW.aspx?type=SWPAR&map=CTY"]},
    "MD": {"adapter": "md", "source_name": "Maryland State Board of Elections — Election Results",
           "page": "https://elections.maryland.gov/elections/2026/general_results/",
           "data": ["https://elections.maryland.gov/elections/2026/general_results/gen_results_2026_1.html"] + [f"https://elections.maryland.gov/elections/2026/general_results/gen_results_2026_4_{n}.html" for n in range(1, 9)]},
    "FL": {"adapter": "fl", "source_name": "Florida Department of State, Division of Elections — Florida Election Watch",
           "page": "https://floridaelectionwatch.gov/FederalOffices/USSenator",
           "data": ["https://floridaelectionwatch.gov/FederalOffices/USSenator", "https://floridaelectionwatch.gov/FederalOffices/USRepresentative", "https://floridaelectionwatch.gov/StateOffices/Governor"]},
    "AZ": {"adapter": "ev", "source_name": "Arizona Secretary of State — Election Results (Enhanced Voting results system)",
           "page": "https://app.enhancedvoting.com/results/public/arizona/elections/110326GeneralElection",
           "data": "https://app.enhancedvoting.com/results/public/api/elections/arizona/110326GeneralElection/data"},
    "CO": {"adapter": "clarity", "source_name": "Colorado Secretary of State — Election Night Reporting",
           "page": "https://results.enr.clarityelections.com/CO/127407/web.345435/",
           "data": "clarity:https://results.enr.clarityelections.com/CO/127407/"},
    "IA": {"adapter": "clarity", "source_name": "Iowa Secretary of State — Election Night Reporting",
           "page": "https://electionresults.iowa.gov/IA/127077/",
           "data": "clarity:https://electionresults.iowa.gov/IA/127077/"},
    "LA": {"adapter": "la", "source_name": "Louisiana Secretary of State — Election Results",
           "page": "https://voterportal.sos.la.gov/graphical",
           "data": "la:https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=20261103/"},
    "CA": {"adapter": "ca", "browser": "text", "source_name": "California Secretary of State — Election Results",
           "page": "https://electionresults.sos.ca.gov/returns/governor",
           "data": ["https://electionresults.sos.ca.gov/returns/governor"] + [f"https://electionresults.sos.ca.gov/returns/us-rep/district/{n}" for n in range(1, 53)]},
    "TN": {"adapter": "tn", "browser": "text", "source_name": "Tennessee Secretary of State — Election Night Reporting Dashboard",
           "page": "https://www.elections.tn.gov/categories/congressional/offices",
           "data": ["https://www.elections.tn.gov/categories/congressional/offices", "https://www.elections.tn.gov/categories/governor/offices"]},
    "SC": {"adapter": "clarity", "source_name": "South Carolina Election Commission — Election Night Reporting",
           "page": "https://www.enr-scvotes.org/SC/127300/web.345435/#/summary",
           "data": "clarity:https://www.enr-scvotes.org/SC/127300/"},
    "IN": {"adapter": "in", "source_name": "Indiana Election Division — Election Night Reporting",
           "page": "https://enr.indianavoters.in.gov/",
           "data": "https://enr.indianavoters.in.gov/site/data/OffCatC_1005_B.json"},
}

def urls(cfg): return cfg["data"] if isinstance(cfg["data"], list) else [cfg["data"]]

def parse_one(st, url, raw):
    cfg = SOURCES[st]
    out = ADAPTERS[cfg["adapter"]](raw, cfg)
    for r in out: r["data_url"] = url
    return out

def fetch_one(st, url):
    return get(url, SOURCES[st].get("browser"))

MIN_MARGIN_PTS = 1.0  # hard floor: any contest closer than this is "too close to call" in every state

def status_for(st, race):
    """Apply the inclusion rule. Returns (status, leader_index, note).
    status: certified | leading (unofficial, not certified) | too_close | skipped.
    We never call races; 'leading' only means the state's own unofficial count meets the fixed rule below."""
    cs = [c for c in race["candidates"] if not re.search(r"write[- ]?in|^over ?votes|^under ?votes|^blank", c["name"], re.I)]
    allc = race["candidates"]
    total = sum(c["votes"] for c in allc)
    if not cs or total == 0: return "skipped", None, "no votes reported"
    order = sorted(range(len(allc)), key=lambda i: -allc[i]["votes"])
    lead = order[0]
    if re.search(r"write[- ]?in", allc[lead]["name"], re.I): return "skipped", None, "write-in total leads"
    share = 100 * allc[lead]["votes"] / total
    margin = 100 if len(cs) == 1 else 100 * (allc[lead]["votes"] - allc[order[1]]["votes"]) / total
    if race["official"]:
        return "certified", lead, ("uncontested" if len(cs) == 1 else f"official results; margin {margin:.1f} pts")
    flagged = [i for i, c in enumerate(allc) if c.get("state_winner") or str(c.get("outcome", "")).lower() == "elected"]
    state_marked = len(flagged) == 1 and flagged[0] == lead
    rep = race["reporting"]
    # Reporting must be 100%: every reporting unit in, none only partially reporting.
    if SOURCES[st].get("no_precinct_reporting"):
        if not state_marked: return "skipped", None, "the state publishes no reporting percentage for this contest, so 100% reporting cannot be confirmed"
    elif re.search(r"partial", rep, re.I):
        return "skipped", None, f"reporting under 100%: precincts only partially reporting ({rep})"
    elif not race["complete"] and not state_marked:
        return "skipped", None, f"reporting under 100% ({rep})"
    if len(cs) == 1: return "leading", lead, "uncontested"
    if margin < MIN_MARGIN_PTS: return "too_close", None, f"margin {margin:.2f} pts is under the 1-point floor"
    if (st in MAJORITY and race["cls"][0] != "Governor") or st == "GA":
        if share <= 50: return "too_close", None, f"leader has {share:.1f}%; a majority is required (runoff or ranked-choice)"
    need = LATE_MARGIN_PTS if st in LATE_COUNT else MARGIN_PTS
    if margin < need: return "too_close", None, f"margin {margin:.1f} pts is under the {need:g}-point rule for this state"
    return "leading", lead, (f"margin {margin:.1f} pts" + ("; leader marked by the state's own results file" if state_marked else ""))

FL_STATUS_URL = "https://floridaelectionwatch.gov/CountyReportingStatus"
def fl_reporting_status():
    """Florida's official County Reporting Status page: the TOTAL row's 'Precincts Reporting' column."""
    st, b = get(FL_STATUS_URL)
    if st != 200 or not b: return {"url": FL_STATUS_URL, "pct": None, "lines": None}
    RAWDIR.mkdir(parents=True, exist_ok=True); (RAWDIR / "FL-reporting-status.raw").write_bytes(b)
    L = lines_of_html(b)
    try:
        i = len(L) - 1 - L[::-1].index("TOTAL"); lines = L[i:i + 5]
        pct = lines[4] if re.fullmatch(r"\d+(\.\d+)?%", lines[4]) else None
    except (ValueError, IndexError): lines, pct = None, None
    return {"url": FL_STATUS_URL, "pct": pct, "lines": lines}
REPORTING_STATUS = {"FL": fl_reporting_status}

def main(states):
    prev = read_json(OUT) if OUT.exists() else {"states": {}}
    for st in states:
        cfg = SOURCES[st]
        rec = {"state": st, "source_name": cfg["source_name"], "page": cfg["page"], "retrieved_at": now_iso()}
        races, errs = [], []
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(6) as ex:
            got = list(ex.map(lambda u: fetch_one(st, u), urls(cfg)))
        for n, (u, (status, b)) in enumerate(zip(urls(cfg), got)):
            if status != 200 or not b: errs.append(f"{u}: HTTP {status}"); continue
            RAWDIR.mkdir(parents=True, exist_ok=True); (RAWDIR / f"{st}-{n}.raw").write_bytes(b)
            try: races += parse_one(st, u, b)
            except Exception as e: errs.append(f"{u}: parse error {e}")
        if errs: rec["errors"] = errs
        seen = {}; dedup = []
        for r in races:
            key = tuple(r["cls"])
            if key in seen:
                if [(c["name"], c["votes"]) for c in seen[key]["candidates"]] != [(c["name"], c["votes"]) for c in r["candidates"]]:
                    errs.append(f"conflicting duplicate contest {key}: {seen[key]['label']} / {r['label']}")
                    seen[key]["conflict"] = True
                continue
            seen[key] = r; dedup.append(r)
        races = [r for r in dedup if not r.get("conflict")]
        if errs: rec["errors"] = errs
        if st in REPORTING_STATUS:
            rs = REPORTING_STATUS[st](); rec["reporting_status"] = rs
            for r in races:
                if not r["official"]:
                    r["reporting"] = f'{r["reporting"]}; statewide Precincts Reporting: {rs["pct"] or "not found"} (County Reporting Status)'
                    r["complete"] = rs["pct"] == "100%"
        for r in races:
            s, lead, note = status_for(st, r)
            r.update(status=s, winner=lead, note=note)
        rec["races"] = races
        prev["states"][st] = rec
        print(st, len(races), "races", dict(__import__("collections").Counter(r["status"] for r in races)))
        write_json(OUT, prev)
    write_json(OUT, prev)

if __name__ == "__main__":
    main(sys.argv[1:] or list(SOURCES))
