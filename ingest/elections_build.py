"""Turn data/build/elections-2026.json (official state results, parsed by elections.py) into:
  * data/manual/elections-2026.json  - leading candidates in unofficial results (or certified winners), plus too-close and skipped lists
  * data/build/site/elections.json   - everything the /elections-2026 pages render
  * election claims merged into data/build/site/claims.json (ids prefixed e_)
Every number shown comes from a claim whose check re-parses the official state source (kind 'state-results').
Run after build.py and before verify.py --stage elections."""
import re, json, hashlib, unicodedata, collections
from common import *
import elections as E

SITE = BUILD / "site"
SEN_XML_URL = "https://www.senate.gov/general/contact_information/senators_cfm.xml"
SPECIAL_CLASS3 = {"FL", "OH"}  # 2026 special elections for Class III seats (vacancies filled by appointment)

from datetime import datetime
from zoneinfo import ZoneInfo
def as_of_ct(iso):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Chicago"))
    return d.strftime("%b %-d, %Y, %-I:%M %p") + " CT"

def eid(*parts): return "e_" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:14]
def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def tidy_case(n):
    if n != n.upper(): return n
    def w(x):
        x = x.capitalize()
        x = re.sub(r"^Mc(\w)", lambda m: "Mc" + m.group(1).upper(), x)
        x = re.sub(r"^O'(\w)", lambda m: "O'" + m.group(1).upper(), x)
        x = re.sub(r"-(\w)", lambda m: "-" + m.group(1).upper(), x)
        return x.upper() if x.upper() in ("II", "III", "IV") else x
    return " ".join(w(x) for x in n.split())

def clean_name(n, party=""):
    n = re.sub(r"\s*\((I|Inc\.?)\)\s*", " ", n)                    # incumbency markers
    n = re.sub(r"\s*\((Rep|Dem|Lib|Grn|Ind|Npa|[A-Z]{2,4})\)\s*$", "", n, flags=re.I)  # trailing party tag
    if party and n.upper().startswith(party.upper() + " "): n = n[len(party) + 1:]   # leading party code (Clarity SC)
    n = re.sub(r"\s+", " ", n).strip()
    if " / " in n: n = n.split(" / ")[0]                            # governor tickets "A / B" -> A (ticket shown separately)
    n = re.sub(r"\s+\((?:DEM|REP|PND|IND|LIB|GRN)\)$", "", n)
    if re.search(r"\band\b", n, re.I) and len(n.split()) > 3: n = re.split(r"\s+and\s+|\s+AND\s+", n)[0]
    return tidy_case(n)

def key_last(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().upper()
    n = re.sub(r'"[^"]*"|\'[^\']*\'|\([^)]*\)', " ", n)
    toks = [t for t in re.sub(r"[^A-Z\- ]", " ", n).split() if t not in ("JR", "SR", "II", "III", "IV")]
    return toks[-1] if toks else ""

def key_first(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().upper()
    toks = [t for t in re.sub(r"[^A-Z ]", " ", n).split() if len(t) > 1]
    return toks[0] if toks else ""

NICK = {"JIM": "JAMES", "JIMMY": "JAMES", "BILL": "WILLIAM", "BOB": "ROBERT", "MIKE": "MICHAEL", "LOU": "LUIS", "RICH": "RICHARD",
        "RICK": "RICHARD", "TOM": "THOMAS", "TED": "EDWARD", "GREG": "GREGORY", "CHUCK": "CHARLES", "CHIP": "CHARLES", "ZACH": "ZACHARY",
        "GIL": "GILBERT", "JOHNNY": "JOHN", "HANK": "HENRY", "DAN": "DANIEL", "DAVE": "DAVID", "STEVE": "STEVEN", "JOE": "JOSEPH", "PETE": "PETER"}
def _names(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().upper()
    return [t for t in re.sub(r"[^A-Z ]", " ", n).split() if len(t) > 1 and t not in ("JR", "SR", "II", "III", "IV")]
def same_person(a, b):
    """Conservative match of a ballot name to a current member: same last name AND a compatible given name
    (same first 3 letters, a common nickname, or the ballot's first name appears among the member's names)."""
    if key_last(a) != key_last(b): return False
    fa, fb = key_first(a), key_first(b)
    nb = set(_names(b)); na = set(_names(a))
    return fa[:3] == fb[:3] or NICK.get(fa, fa) == NICK.get(fb, fb) or fa in nb or fb in na or NICK.get(fa) in nb

def main():
    res = read_json(BUILD / "elections-2026.json")
    people = read_json(SITE / "people.json")["people"]
    profiles = {}
    claims_doc = read_json(SITE / "claims.json"); claims = claims_doc["claims"]
    old = {k: v for k, v in claims.items() if k.startswith("e_")}
    for k in list(old): del claims[k]

    st_code, sen_raw = fetch(SEN_XML_URL)
    sen_t = now_iso()
    (RAW / "senators_cfm.xml").write_bytes(sen_raw)
    sen_lines = E.lines_of_html(sen_raw)
    def senate_holder(st, cls):
        # find "<Last> (P-ST)" block whose class line matches; excerpt = consecutive lines of that member block
        for i, l in enumerate(sen_lines):
            if re.match(rf"^.+ \([A-Z]-{st}\)$", l):
                j = next((j for j in range(i, min(i + 14, len(sen_lines))) if sen_lines[j].startswith("Class ")), None)
                if j is not None and sen_lines[j] == cls:
                    block = sen_lines[i:j + 2]
                    bio = block[-1]
                    p = next((p for p in people if p.get("bioguide") == bio), None)
                    return p, block
        return None, None

    def add_claim(text, value, excerpt, source_name, source_url, check, retrieved_at):
        i = eid(text, source_url, json.dumps(check, sort_keys=True))
        c = {"id": i, "text": text, "value": value, "excerpt": excerpt, "source_name": source_name, "source_url": source_url,
             "check": check, "retrieved_at": retrieved_at, "status": "unverified"}
        o = old.get(i)
        if o and o.get("status") == "verified" and all(o.get(k) == c[k] for k in ("value", "excerpt", "check")):
            c.update(status="verified", verified_at=o.get("verified_at"), verify_note=o.get("verify_note"))
        claims[i] = c; return i

    races_out, elect, uncalled, states_out = [], [], [], {}
    used = set(p["slug"] for p in people)
    for st, rec in sorted(res["states"].items()):
        srcname = rec["source_name"]; t = rec["retrieved_at"]
        states_out[st] = {"state": st, "stateName": E.STATE_NAMES[st], "source_name": srcname, "page": rec["page"],
                          "retrieved_at": t, "as_of": as_of_ct(t), "errors": rec.get("errors", []), "races": 0}
        rep_claim = None
        rs = rec.get("reporting_status")
        if rs and rs.get("lines"):
            rep_claim = add_claim(f"{srcname.split(' — ')[0]} County Reporting Status, TOTAL row: Precincts Reporting {rs['pct']}", rs["pct"], "\n".join(rs["lines"]),
                                  srcname.split(" — ")[0] + " — County Reporting Status", rs["url"], {"kind": "text-lines", "url": rs["url"], "lines": rs["lines"]}, t)
            states_out[st]["reporting_status"] = {"url": rs["url"], "pct": rs["pct"], "claim": rep_claim}
        for r in rec["races"]:
            office, dist, special = r["cls"]
            url = r["data_url"]; src_url = url if url.startswith("http") else rec["page"]
            cands = [{"name": c["name"], "display": clean_name(c["name"], c.get("party", "")), "party": c.get("party", ""), "votes": c["votes"]} for c in r["candidates"]]
            total = sum(c["votes"] for c in cands) or 1
            for c in cands: c["pct"] = round(100 * c["votes"] / total, 2)
            check = {"kind": "state-results", "state": st, "url": url, "office": office, "district": dist,
                     "candidates": [[c["name"], c["votes"]] for c in r["candidates"]]}
            where = f"{E.STATE_NAMES[st]}" + (f" District {dist}" if office == "U.S. House" and dist else (" at-large" if office == "U.S. House" else ""))
            rc = add_claim(f"Official {srcname.split(' — ')[0]} results for {office}, {where} ({r['label']}): " + "; ".join(f"{c['name']} {c['votes']:,}" for c in r["candidates"]) + f" ({r['reporting']})",
                           [[c["name"], c["votes"]] for c in r["candidates"]], "\n".join(r["excerpt"]), srcname, src_url, check, t)
            race = {"id": f"{st}-{office}-{dist}".lower().replace(" ", "").replace(".", ""), "state": st, "stateName": E.STATE_NAMES[st],
                    "office": office, "district": dist, "special": special or (office == "U.S. Senate" and st in SPECIAL_CLASS3),
                    "label": r["label"], "reporting": r["reporting"], "status": r["status"], "note": r["note"], "claim": rc,
                    "source_name": srcname, "source_url": src_url, "page": rec["page"], "retrieved_at": t, "as_of": as_of_ct(t), "candidates": cands, "winner": None}
            if rep_claim: race["reporting_claim"] = rep_claim
            # who holds the seat now (from verified official records)
            inc, inc_claim = None, None
            if office == "U.S. House":
                inc = next((p for p in people if p.get("chamber") == "house" and p["state"] == st and (p.get("district") or 0) == dist), None)
                if inc:
                    prof = read_json(SITE / "profiles" / f"{inc['slug']}.json")
                    inc_claim = next((f["claim"] for f in prof["facts"] if f["label"] == "District"), None) or next((f["claim"] for f in prof["facts"] if f["label"] == "Office"), None)
            elif office == "U.S. Senate":
                cls = "Class III" if st in SPECIAL_CLASS3 else "Class II"
                inc, block = senate_holder(st, cls)
                if inc and block:
                    inc_claim = add_claim(f"{inc['name']} holds the {st} {cls} Senate seat", cls, "\n".join(block), "U.S. Senate — Senators' contact information (XML)",
                                          SEN_XML_URL, {"kind": "text-lines", "url": SEN_XML_URL, "lines": block}, sen_t)
                race["seat_class"] = cls
            if inc: race["incumbent"] = {"slug": inc["slug"], "name": inc["name"], "party": inc["party"], "claim": inc_claim}
            if r["status"] in ("leading", "certified") and r["winner"] is not None:
                w = cands[r["winner"]]
                state_label = srcname.split(" — ")[0]
                date = t[:10]
                label = (f"Certified winner, per {state_label}, retrieved {date}." if r["status"] == "certified"
                         else f"Leading in unofficial results, per {state_label}, retrieved {date}. Not certified.")
                ru = sorted(cands, key=lambda c: -c["votes"])
                runner = ru[1] if len(ru) > 1 and ru[0] is w else (ru[0] if ru[0] is not w else None)
                reelect = bool(inc) and same_person(w["display"], inc["name"])
                member_now = inc if reelect else next((p for p in people if p.get("kind") == "congress" and p["state"] == st and same_person(w["display"], p["name"])), None)
                race["winner"] = {"name": w["display"], "ballot_name": w["name"], "party": w["party"], "votes": w["votes"], "pct": w["pct"],
                                  "label": label, "reelected": reelect, "current_member": bool(member_now),
                                  "runner_up": ({"name": runner["display"], "votes": runner["votes"], "pct": runner["pct"]} if runner else None)}
                s = slugify(w["display"])
                if member_now and not reelect:
                    race["winner"]["slug"] = member_now["slug"]; race["winner"]["current_member_seat"] = member_now.get("district")
                elif not reelect:
                    if s in used: s = f"{s}-{st.lower()}"
                    used.add(s); race["winner"]["slug"] = s
                    elect.append({"kind": "governor" if office == "Governor" else "congress", "slug": s, "name": w["display"], "ballot_name": w["name"], "office": office, "state": st, "district": dist,
                                  "party": w["party"], "status": r["status"], "label": label, "race": race["id"], "claim": rc, "as_of": as_of_ct(t),
                                  "source_name": srcname, "source_url": src_url, "excerpt_lines": r["excerpt"], "retrieved_at": t,
                                  "replaces": race.get("incumbent")})
                    if office == "Governor": race["winner"]["governor"] = True
                else:
                    race["winner"]["slug"] = inc["slug"]
            else:
                uncalled.append({"race": race["id"], "state": st, "office": office, "district": dist, "status": r["status"], "reason": r["note"]})
            races_out.append(race); states_out[st]["races"] += 1

    not_covered = read_json(ROOT / "data" / "manual" / "elections-2026-coverage.json")
    out = {"election": "2026-11-03", "generated": now_iso(), "rule": {"min_margin_pts": E.MIN_MARGIN_PTS, "margin_pts": E.MARGIN_PTS, "late_margin_pts": E.LATE_MARGIN_PTS,
           "late_count_states": sorted(E.LATE_COUNT), "majority_states": sorted(E.MAJORITY)},
           "states": states_out, "races": races_out, "elect": elect, "uncalled": uncalled, "not_covered": not_covered}
    write_json(SITE / "elections.json", out)
    man = read_json(ROOT / "data" / "manual" / "elections-2026.json")
    man["entries"] = [{"name": e["name"], "office": e["office"], "state": e["state"], "district": e["district"], "party": e["party"],
                       "status": e["status"], "label": e["label"], "source_name": e["source_name"], "source_url": e["source_url"],
                       "excerpt_lines": e["excerpt_lines"], "retrieved_at": e["retrieved_at"], "claim": e["claim"],
                       "replaces": (e["replaces"] or {}).get("slug")} for e in elect]
    man["reelected_or_retained"] = [{"race": r["id"], "name": r["winner"]["name"], "status": r["status"], "label": r["winner"]["label"], "claim": r["claim"]}
                                    for r in races_out if r.get("winner") and r["winner"].get("reelected")]
    man.pop("uncalled", None)
    man["too_close_to_call"] = [u for u in uncalled if u["status"] == "too_close"]
    man["skipped"] = [u for u in uncalled if u["status"] == "skipped"]
    write_json(ROOT / "data" / "manual" / "elections-2026.json", man)
    claims_doc["claims"] = claims
    write_json(SITE / "claims.json", claims_doc)
    c = collections.Counter(r["status"] for r in races_out)
    print(f"states {len(states_out)} races {len(races_out)} {dict(c)} new leading candidates {len(elect)}")

if __name__ == "__main__":
    main()
