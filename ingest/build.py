"""Transform raw official records into site data with claim objects.
Every rendered fact references a claim: {id, text, value, excerpt, source_name, source_url, check, retrieved_at, status}.
status starts 'unverified'; verify.py re-fetches sources and sets 'verified' or 'blocked'."""
import re, json, glob, hashlib, unicodedata, collections
import xml.etree.ElementTree as ET
from common import *

SITE = BUILD / "site"
LEG = read_json(RAW / "legislators-current.json")
EXEC = read_json(RAW / "executive.json")
STATE_NAMES = {}

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def cid(*parts):
    return "c_" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:14]

class Claims:
    def __init__(self): self.d = {}
    def add(self, text, value, excerpt, source_name, source_url, check, retrieved_at, key=None):
        i = cid(*(key or (text, source_url, json.dumps(check, sort_keys=True))))
        self.d[i] = {"id": i, "text": text, "value": value, "excerpt": excerpt, "source_name": source_name,
                     "source_url": source_url, "check": check, "retrieved_at": retrieved_at, "status": "unverified"}
        return i

def file_time(p):
    import os, datetime
    return datetime.datetime.fromtimestamp(os.path.getmtime(p), datetime.timezone.utc).replace(microsecond=0).isoformat()

def main():
    C = Claims()
    people, profiles = {}, {}
    used = set()
    def mkslug(name, state=""):
        s = slugify(name)
        if s in used: s = f"{s}-{state.lower()}" if state else s + "-2"
        used.add(s); return s

    # ---------- Congress members ----------
    hd_path = RAW / "committees" / "house-MemberData.xml"
    hd = ET.parse(hd_path).getroot(); hd_t = file_time(hd_path)
    hcom = {c.get("comcode"): c.findtext("committee-fullname") for c in hd.iter("committee") if c.findtext("committee-fullname")}
    hassign = {}
    for m in hd.iter("member"):
        b = m.findtext("member-info/bioguideID")
        if b: hassign[b] = [(c.get("comcode"), c.get("leadership")) for c in m.findall("committee-assignments/committee")]
    sassign = collections.defaultdict(list)
    lastname_state = {}
    for p in LEG:
        t = p["terms"][-1]
        if t["type"] == "sen": lastname_state[(p["name"]["last"].lower(), t["state"])] = p["id"]["bioguide"]
    for f in sorted(glob.glob(str(RAW / "committees" / "senate-*.xml"))):
        r = ET.parse(f).getroot(); code = re.search(r"senate-(\w+)\.xml", f).group(1)
        cname = r.findtext(".//committee_name")
        for mem in r.findall("committees/members/member"):  # full-committee roster only (not subcommittees)
            last = (mem.findtext("name/last") or "").strip(); st = (mem.findtext("state") or "").strip()
            b = lastname_state.get((last.lower(), st))
            if b: sassign[b].append((code, cname, (mem.findtext("position") or "").strip(), last, st, file_time(f)))

    fec = read_json(BUILD / "fec-totals.json") if (BUILD / "fec-totals.json").exists() else {"totals": {}}
    fec_t = fec.get("retrieved_at")
    pac = read_json(BUILD / "fec-pac.json") if (BUILD / "fec-pac.json").exists() else (read_json(BUILD / "fec-pac-partial.json") and {"contributors": read_json(BUILD / "fec-pac-partial.json"), "retrieved_at": file_time(BUILD / "fec-pac-partial.json")} if (BUILD / "fec-pac-partial.json").exists() else {"contributors": {}})
    comms = read_json(BUILD / "fec-committees.json")["committees"] if (BUILD / "fec-committees.json").exists() else {}

    votes = []
    for ch in ("house", "senate"):
        p = BUILD / f"votes-{ch}.json"
        if p.exists(): vv = read_json(p); votes += [dict(v, _t=vv["retrieved_at"]) for v in vv["votes"]]
    def vkey(v):
        m = re.match(r"(\d+)-([A-Za-z]{3})-(\d{4})", v["date"])  # house "3-Jan-2025"
        import datetime
        if m: return datetime.datetime.strptime(v["date"], "%d-%b-%Y").date().isoformat()
        try: return datetime.datetime.strptime(v["date"].split(",")[0] + "," + v["date"].split(",")[1], "%B %d, %Y").date().isoformat()
        except Exception: return "0000"
    for v in votes: v["iso"] = vkey(v)
    votes.sort(key=lambda v: (v["iso"], v["roll"]))

    # bill sponsor index from sponsored lists
    sponsor_of, sp_t = {}, {}
    for f in glob.glob(str(RAW / "congress" / "sponsored" / "*.json")):
        b = re.search(r"(\w+)\.json$", f).group(1); d = json.loads(open(f).read())
        sp_t[b] = d.get("_retrieved_at")
        for it in d.get("sponsoredLegislation", []):
            if it.get("congress") == 119 and it.get("type") and it.get("number"):
                sponsor_of[(it["type"], it["number"])] = (b, it)

    def bill_url(it):
        tmap = {"HR": "house-bill", "S": "senate-bill", "HRES": "house-resolution", "SRES": "senate-resolution",
                "HJRES": "house-joint-resolution", "SJRES": "senate-joint-resolution", "HCONRES": "house-concurrent-resolution", "SCONRES": "senate-concurrent-resolution"}
        return f"https://www.congress.gov/bill/119th-congress/{tmap.get(it['type'], 'bill')}/{it['number']}"
    def bill_label(it):
        lab = {"HR": "H.R.", "S": "S.", "HRES": "H.Res.", "SRES": "S.Res.", "HJRES": "H.J.Res.", "SJRES": "S.J.Res.", "HCONRES": "H.Con.Res.", "SCONRES": "S.Con.Res."}
        return f"{lab.get(it['type'], it['type'])} {it['number']}"

    for p in LEG:
        b = p["id"]["bioguide"]; t = p["terms"][-1]
        mpath = RAW / "congress" / "member" / f"{b}.json"
        if not mpath.exists(): continue
        md = json.loads(mpath.read_text()); m = md["member"]; rt = md.get("_retrieved_at")
        name = m.get("directOrderName") or p["name"].get("official_full")
        slug = mkslug(name, t["state"])
        api = f"https://api.congress.gov/v3/member/{b}"
        human = f"https://www.congress.gov/member/{slugify(name)}/{b}"
        lt = m["terms"][-1]; party = m["partyHistory"][-1]["partyName"]
        chamber = "senate" if lt["chamber"] == "Senate" else "house"
        role = "Senator" if chamber == "senate" else ("Delegate" if lt.get("memberType") == "Delegate" else ("Resident Commissioner" if "Commissioner" in (lt.get("memberType") or "") else "Representative"))
        facts = []
        facts.append({"label": "Office", "value": f"U.S. {role}" if role != "Senator" else "U.S. Senator",
            "claim": C.add(f"{name} is a current member of the U.S. {lt['chamber']}.", lt["chamber"], f'terms[-1].chamber = "{lt["chamber"]}"; currentMember = {str(m.get("currentMember")).lower()}', "Congress.gov (Library of Congress)", human,
                           {"kind": "congress-member", "url": api, "fields": {"terms[-1].chamber": lt["chamber"], "currentMember": True}}, rt)})
        facts.append({"label": "Party", "value": party, "claim": C.add(f"{name}'s party is {party}.", party, f'partyHistory[-1].partyName = "{party}"', "Congress.gov (Library of Congress)", human,
                           {"kind": "congress-member", "url": api, "fields": {"partyHistory[-1].partyName": party}}, rt)})
        st = lt.get("stateName") or m.get("state")
        facts.append({"label": "State", "value": st, "claim": C.add(f"{name} represents {st}.", st, f'terms[-1].stateName = "{st}"', "Congress.gov (Library of Congress)", human,
                           {"kind": "congress-member", "url": api, "fields": {"terms[-1].stateName": st}}, rt)})
        if chamber == "house" and "district" in lt and lt["district"] is not None:
            dv = lt["district"]
            facts.append({"label": "District", "value": "At-large" if dv == 0 else str(dv), "claim": C.add(f"{name} represents district {dv}.", dv, f"terms[-1].district = {dv}", "Congress.gov (Library of Congress)", human,
                           {"kind": "congress-member", "url": api, "fields": {"terms[-1].district": dv}}, rt)})
        first = m["terms"][0]
        facts.append({"label": "First served in Congress", "value": str(first.get("startYear")), "claim": C.add(f"{name} first served in Congress starting {first.get('startYear')}.", first.get("startYear"), f"terms[0].startYear = {first.get('startYear')}", "Congress.gov (Library of Congress)", human,
                           {"kind": "congress-member", "url": api, "fields": {"terms[0].startYear": first.get("startYear")}}, rt)})
        web = m.get("officialWebsiteUrl")
        if web:
            facts.append({"label": "Official website", "value": web, "link": web, "claim": C.add(f"{name}'s official website is {web}.", web, f'officialWebsiteUrl = "{web}"', "Congress.gov (Library of Congress)", human,
                           {"kind": "congress-member", "url": api, "fields": {"officialWebsiteUrl": web}}, rt)})

        # committees
        committees = []
        if chamber == "house":
            for code, lead in hassign.get(b, []):
                nm = hcom.get(code, code)
                committees.append({"name": nm, "role": lead or "Member", "code": code, "claim": C.add(f"{name} serves on the House {nm}.", code,
                    f'<bioguideID>{b}</bioguideID> … <committee comcode="{code}"' + (f' leadership="{lead}"' if lead else "") + ">", "Office of the Clerk, U.S. House (MemberData.xml)",
                    "https://clerk.house.gov/xml/lists/MemberData.xml", {"kind": "house-committee", "url": "https://clerk.house.gov/xml/lists/MemberData.xml", "bioguide": b, "comcode": code}, hd_t)})
        else:
            for code, cname, pos, last, stc, ft in sassign.get(b, []):
                url = f"https://www.senate.gov/general/committee_membership/committee_memberships_{code}.xml"
                committees.append({"name": cname, "role": pos or "Member", "code": code, "claim": C.add(f"{name} serves on the Senate {cname}.", code,
                    f"<last>{last}</last> … <state>{stc}</state> … <position>{pos}</position>", "U.S. Senate committee membership roster", url,
                    {"kind": "senate-committee", "url": url, "last": last, "state": stc}, ft)})

        # sponsored bills (recent 5)
        sp = json.loads((RAW / "congress" / "sponsored" / f"{b}.json").read_text()) if (RAW / "congress" / "sponsored" / f"{b}.json").exists() else {}
        sp_url = f"https://api.congress.gov/v3/member/{b}/sponsored-legislation?format=json&limit=250"
        bills = []
        for it in [x for x in sp.get("sponsoredLegislation", []) if x.get("congress") == 119 and x.get("type")][:6]:
            bills.append({"label": bill_label(it), "title": it.get("title"), "date": it.get("introducedDate"), "url": bill_url(it),
                "claim": C.add(f"{name} sponsored {bill_label(it)} ({it.get('title')}), introduced {it.get('introducedDate')}.", f"{it['type']} {it['number']}",
                    f'type="{it["type"]}", number="{it["number"]}", title="{it.get("title")}", introducedDate="{it.get("introducedDate")}"',
                    "Congress.gov (Library of Congress)", bill_url(it), {"kind": "congress-list", "url": sp_url, "list": "sponsoredLegislation",
                    "match": {"type": it["type"], "number": it["number"], "introducedDate": it.get("introducedDate")}}, sp.get("_retrieved_at"))})
        sp119 = len([x for x in sp.get("sponsoredLegislation", []) if x.get("congress") == 119 and x.get("type")])

        # cosponsorship partners
        co = json.loads((RAW / "congress" / "cosponsored" / f"{b}.json").read_text()) if (RAW / "congress" / "cosponsored" / f"{b}.json").exists() else {}
        co_url = f"https://api.congress.gov/v3/member/{b}/cosponsored-legislation?format=json&limit=250"
        partner = collections.defaultdict(list)
        for it in co.get("cosponsoredLegislation", []):
            if it.get("congress") != 119 or not it.get("type"): continue
            s = sponsor_of.get((it["type"], it["number"]))
            if s and s[0] != b: partner[s[0]].append(it)
        cospons = []
        for pb, items in sorted(partner.items(), key=lambda kv: -len(kv[1]))[:5]:
            ex = []
            for it in items[:3]:
                sit = sponsor_of[(it["type"], it["number"])][1]
                ex.append({"label": bill_label(it), "title": it.get("title"), "url": bill_url(it),
                    "claim": C.add(f"{name} cosponsored {bill_label(it)}.", f"{it['type']} {it['number']}", f'type="{it["type"]}", number="{it["number"]}"',
                        "Congress.gov (Library of Congress)", bill_url(it), {"kind": "congress-list", "url": co_url, "list": "cosponsoredLegislation", "match": {"type": it["type"], "number": it["number"]}}, co.get("_retrieved_at")),
                    "sponsor_claim": C.add(f"{pb} sponsored {bill_label(it)}.", f"{it['type']} {it['number']}", f'type="{it["type"]}", number="{it["number"]}"',
                        "Congress.gov (Library of Congress)", bill_url(it), {"kind": "congress-list", "url": f"https://api.congress.gov/v3/member/{pb}/sponsored-legislation?format=json&limit=250", "list": "sponsoredLegislation", "match": {"type": it["type"], "number": it["number"]}}, sp_t.get(pb))})
            cnt_claim = C.add(f"{name} cosponsored {len(items)} bills sponsored by {pb} in the 119th Congress (within each member's 250 most recent listed items).", len(items),
                f"count of 119th-Congress bills in cosponsoredLegislation[{b}] ∩ sponsoredLegislation[{pb}] = {len(items)}", "Congress.gov (Library of Congress)", co_url.replace("api.congress.gov/v3", "www.congress.gov").split("?")[0] if False else human,
                {"kind": "cosponsor-count", "a": co_url, "b": f"https://api.congress.gov/v3/member/{pb}/sponsored-legislation?format=json&limit=250", "expected": len(items)}, co.get("_retrieved_at"))
            cospons.append({"partner": pb, "count": len(items), "claim": cnt_claim, "examples": ex})

        # FEC totals (aggregate)
        money = []
        ft = fec["totals"].get(b)
        if ft:
            for fld, lab in [("receipts", "Total receipts"), ("disbursements", "Total disbursements"), ("cash_on_hand_end_period", "Cash on hand (end of latest period)"),
                             ("other_political_committee_contributions", "Contributions from other political committees (PACs)"), ("individual_itemized_contributions", "Itemized individual contributions (aggregate)")]:
                val = ft.get(fld)
                if val is None: continue
                val = float(val)
                money.append({"label": lab, "value": val, "claim": C.add(f"{lab} reported by {name}'s campaign for the 2025–2026 cycle: ${val:,.2f}.", val, f"{fld} = {val}",
                    "Federal Election Commission (OpenFEC)", ft["source_url"], {"kind": "fec-totals", "url": ft["api_url"], "field": fld, "expected": val}, fec_t)})
            money_meta = {"candidate_id": ft["candidate_id"], "coverage_end": ft.get("coverage_end_date"), "source_url": ft["source_url"]}
        else:
            money_meta = None

        # political committees giving to the principal campaign committee (aggregated, committee-level only)
        pacs = []
        rows = pac["contributors"].get(b, []) if pac else []
        for r in rows[:6]:
            if r["giver_id"] == r["recipient_id"]: continue
            rc = r["recipient_id"]
            pacs.append({"committee_id": r["giver_id"], "name": r["giver_name"], "largest": r["total"], "count": r["count"], "date": None,
                "url": f"https://www.fec.gov/data/committee/{r['giver_id']}/",
                "receipts_url": f"https://www.fec.gov/data/disbursements/?committee_id={r['giver_id']}&recipient_committee_id={rc}&two_year_transaction_period=2026",
                "claim": C.add(f"{r['giver_name']} ({r['giver_id']}) reported ${r['total']:,.2f} in {r['count']} disbursement(s) to {name}'s principal campaign committee, {r.get('recipient_name')} ({rc}), in 2025–26.", r["total"],
                    f'committee_id="{r["giver_id"]}", committee_name="{r["giver_name"]}", recipient_id="{rc}", total={r["total"]}, count={r["count"]}, cycle=2026',
                    "Federal Election Commission (OpenFEC, Schedule B by recipient)", f"https://www.fec.gov/data/disbursements/?committee_id={r['giver_id']}&recipient_committee_id={rc}&two_year_transaction_period=2026",
                    {"kind": "fec-agg", "url": r["api_url"], "match": {"committee_id": r["giver_id"], "total": r["total"]}}, pac.get("retrieved_at"))})
            if len(pacs) == 5: break

        people[b] = {"slug": slug, "bioguide": b, "name": name, "kind": "congress", "chamber": chamber, "role": role, "party": party,
                     "state": lt.get("stateCode"), "stateName": st, "district": lt.get("district")}
        profiles[b] = {"facts": facts, "committees": committees, "bills": bills, "bills_119_count_in_window": sp119,
                       "cosponsors": cospons, "money": money, "money_meta": money_meta, "pacs": pacs, "api_member": api, "congress_url": human}

    # ---------- Votes: recent + analysis ----------
    from metrics import member_metrics
    per = {}
    for bid in profiles:
        mm = member_metrics(bid, votes)
        if mm["lst"]: per[bid] = mm
    for bid, mm in per.items():
        lst = mm["lst"]; name = people[bid]["name"]
        recent = []
        for v, pos in lst[-8:][::-1]:
            label = {"Y": "Yea", "N": "Nay", "P": "Present", "NV": "Not Voting"}.get(pos, pos)
            src = v.get("source_xml") or v["source_url"]
            recent.append({"date": v["iso"], "chamber": v["chamber"], "roll": v["roll"], "question": v["question"], "legis": v["legis"], "desc": v.get("desc"),
                "result": v["result"], "position": label, "url": v["source_url"],
                "claim": C.add(f"On {v['iso']}, {name} was recorded as {label} on {v['chamber'].title()} roll call {v['roll']} ({v['question']}{' — ' + v['legis'] if v['legis'] else ''}).", label,
                    f"{'name-id' if v['chamber']=='house' else 'lis_member_id'} for {bid}: {label}", "Office of the Clerk, U.S. House" if v["chamber"] == "house" else "U.S. Senate",
                    v["source_url"], {"kind": f"{v['chamber']}-vote", "url": src, "bioguide": bid, "expected": pos}, v["_t"])})
        nv, total = mm["missed"]; pres = mm["present"]; pl_with, pl_n = mm["party_line"]
        div_items = mm["div_items"]; div_base = mm["divergence"][1]
        ch = people[bid]["chamber"]
        src_name = "Office of the Clerk, U.S. House" if ch == "house" else "U.S. Senate"
        src_url = "https://clerk.house.gov/Votes" if ch == "house" else "https://www.senate.gov/legislative/votes_new.htm"
        dkey = {"kind": "derived-votes", "chamber": ch, "bioguide": bid}
        analysis = {
            "total": total,
            "missed": {"count": nv, "rate": round(nv / total, 4) if total else None, "claim": C.add(f"{name} was recorded as Not Voting on {nv} of {total} roll calls ({(nv/total*100 if total else 0):.1f}%) in the 119th Congress through the snapshot date.", [nv, total],
                f"count(position = Not Voting) = {nv}; count(listed) = {total}", src_name, src_url, {**dkey, "metric": "missed", "expected": [nv, total]}, lst[-1][0]["_t"])},
            "present": {"count": pres, "claim": C.add(f"{name} voted Present on {pres} roll calls.", pres, f"count(position = Present) = {pres}", src_name, src_url, {**dkey, "metric": "present", "expected": pres}, lst[-1][0]["_t"])},
        }
        if pl_n:
            analysis["party_line"] = {"with": pl_with, "of": pl_n, "rate": round(pl_with / pl_n, 4), "claim": C.add(f"{name} voted with the majority of their party on {pl_with} of {pl_n} Yea/Nay votes ({pl_with/pl_n*100:.1f}%).", [pl_with, pl_n],
                f"matches party majority = {pl_with}; eligible votes = {pl_n}", src_name, src_url, {**dkey, "metric": "party_line", "expected": [pl_with, pl_n]}, lst[-1][0]["_t"])}
        analysis["divergence"] = {"count": len(div_items), "of": div_base, "measures": div_items[:10], "claim": C.add(f"{name}'s procedural and final-passage votes pointed in opposite directions on {len(div_items)} of {div_base} measures with both vote types.", [len(div_items), div_base],
            f"divergent measures = {len(div_items)} ({', '.join(div_items[:10])}); measures with both = {div_base}", src_name, src_url, {**dkey, "metric": "divergence", "expected": [len(div_items), div_base]}, lst[-1][0]["_t"])}
        profiles[bid]["recent_votes"] = recent
        profiles[bid]["analysis"] = analysis

    # ---------- Executive branch ----------
    wh_path = RAW / "exec" / "cabinet.html"
    if wh_path.exists():
        import html as H
        wh_t = file_time(wh_path)
        t = re.sub(r"<script.*?</script>|<style.*?</style>", "", wh_path.read_text(), flags=re.S)
        L = [re.sub(r"\s+", " ", l).strip() for l in H.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if l.strip()]
        start = [i for i, l in enumerate(L) if l == "The Cabinet"][1]
        execs = [("Donald J. Trump", "President of the United States", "President Donald J. Trump"), ("JD Vance", "Vice President of the United States", "Vice President JD Vance")]
        for i in range(start, len(L) - 1):
            a, bb = L[i], L[i + 1]
            if len(a) <= 45 and len(bb) <= 90 and re.search(r"^(Secretary|Attorney General|Director|Administrator|United States Trade|Chief of Staff|Ambassador)", bb) and re.match(r"^[A-Z][\w\.'’-]+(,? [A-Z][\w\.'’-]+){1,4}$", a):
                execs.append((a, bb, None))
        url = "https://www.whitehouse.gov/administration/cabinet/"
        for nm, title, navtext in execs:
            key = "exec-" + slugify(nm)
            # link to existing congress profile if same person (e.g., none expected) -- executive profiles are separate
            slug = mkslug(nm)
            excerpt = navtext if navtext else f"{nm}\n{title}"
            cl = C.add(f"{nm} holds the office of {title}." if navtext else f"The White House Cabinet page lists {nm} as {title}.", title, excerpt, "The White House", url,
                       {"kind": "text-lines", "url": url, "lines": excerpt.split("\n")}, wh_t)
            people[key] = {"slug": slug, "bioguide": None, "name": nm, "kind": "executive", "chamber": "executive", "role": title, "party": None, "state": None, "stateName": None, "district": None}
            profiles[key] = {"facts": [{"label": "Office", "value": title, "claim": cl}], "committees": [], "bills": [], "cosponsors": [], "money": [], "money_meta": None, "pacs": [], "recent_votes": [], "analysis": None}

    # resolve partner names
    for k, pr in profiles.items():
        for c in pr["cosponsors"]:
            pp = people.get(c["partner"]); c["partner_name"] = pp["name"] if pp else c["partner"]; c["partner_slug"] = pp["slug"] if pp else None
            for ex in c["examples"]:
                C.d[ex["sponsor_claim"]]["text"] = C.d[ex["sponsor_claim"]]["text"].replace(c["partner"], c["partner_name"], 1)
            C.d[c["claim"]]["text"] = C.d[c["claim"]]["text"].replace(c["partner"], c["partner_name"])

    # ---------- Connections (site-wide) ----------
    pairs = []
    for k, pr in profiles.items():
        for c in pr["cosponsors"]:
            pairs.append({"from": k, "to": c["partner"], "count": c["count"], "claim": c["claim"]})
    pairs.sort(key=lambda x: -x["count"])
    pac_members = collections.defaultdict(lambda: {"members": [], "name": None})
    for k, pr in profiles.items():
        for pc in pr["pacs"]:
            e = pac_members[pc["committee_id"]]; e["name"] = pc["name"]; e["members"].append({"who": k, "claim": pc["claim"], "amount": pc["largest"]})
    top_pacs = sorted(([cid_, v] for cid_, v in pac_members.items()), key=lambda kv: -len(kv[1]["members"]))[:30]

    # ---------- write ----------
    write_json(SITE / "people.json", {"generated_at": now_iso(), "people": list(people.values())})
    for k, pr in profiles.items():
        write_json(SITE / "profiles" / f"{people[k]['slug']}.json", {"person": people[k], **pr})
    # Carry over verification only for byte-identical claims (same id, value, excerpt, check); everything else must be re-verified.
    prev = {}
    if (SITE / "claims.json").exists():
        prev = read_json(SITE / "claims.json")["claims"]
    carried = 0
    for i, c in C.d.items():
        p = prev.get(i)
        if c["check"]["kind"] != "senate-committee" and p and p.get("status") == "verified" and p["value"] == c["value"] and p["excerpt"] == c["excerpt"] and p["check"] == c["check"]:
            c.update(status="verified", verified_at=p["verified_at"], verify_note=p.get("verify_note"), retrieved_at=p["retrieved_at"]); carried += 1
    print("verification carried over for identical claims:", carried)
    write_json(SITE / "claims.json", {"generated_at": now_iso(), "claims": C.d})
    write_json(SITE / "connections.json", {"generated_at": now_iso(), "cosponsor_pairs": pairs[:60],
        "pacs": [{"committee_id": k, "name": v["name"], "members": v["members"]} for k, v in top_pacs]})
    write_json(SITE / "stats.json", {"people": len(people), "congress": sum(1 for p in people.values() if p["kind"] == "congress"),
        "executive": sum(1 for p in people.values() if p["kind"] == "executive"), "votes": len(votes), "claims": len(C.d), "retrieved": (fec_t or now_iso())[:10]})
    print("people", len(people), "claims", len(C.d), "votes", len(votes))

if __name__ == "__main__":
    main()
