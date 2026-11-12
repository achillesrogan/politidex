"""Stage 1: special-interest money and outside spending from official FEC bulk files.

Sources (retrieved and stored under data/raw/fec/):
  * Committee master (cm26.zip) — committee type, designation, interest group category
    (ORG_TP), connected organization name. Field descriptions:
    https://www.fec.gov/campaign-finance-data/committee-master-file-description/
  * Committee type labels:
    https://www.fec.gov/campaign-finance-data/committee-type-code-descriptions/
  * Candidate-committee linkage (ccl26.zip)
  * Contributions from committees to candidates (pas226.zip / itpas2.txt),
    transaction type 24K. File description:
    https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/
  * Any transaction from one committee to another (oth26.zip / itoth.txt),
    transaction type 24K to leadership PAC recipients. File description:
    https://www.fec.gov/campaign-finance-data/any-transaction-one-committee-another-file-description/
  * Independent expenditures file:
    https://www.fec.gov/files/bulk-downloads/2026/independent_expenditure_2026.csv
    https://www.fec.gov/campaign-finance-data/independent-expenditures-file-description/

Interest-group grouping uses only the FEC ORG_TP (“Interest group category”)
codes and committee_type / connected_organization_name. No invented industry labels.

Recipient committees are each current member’s principal campaign committee (P)
and leadership PAC (D) for the 2026 cycle. Memo-coded rows (MEMO_CD=X) are
kept in the item count but excluded from totals, per the FEC memo-code
description (amount not incorporated into the committee’s summarized total).

Optional: `python ingest/connections_fec.py --leadership-api` looks up
sponsor_candidate_ids for designation-D committees on the OpenFEC API
(api key from env only; never written).

Usage: python ingest/connections_fec.py
"""
import csv, json, sys, re, collections, urllib.parse
from pathlib import Path
from datetime import datetime, date
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import datetime as _ie_dt

RAWFEC = RAW / "fec"
UNP = RAWFEC / "unpacked"
OUT = BUILD / "connections-fec.json"
LEAD_CACHE = BUILD / "connections-leadership-pacs.json"

COMMITTEE_TYPE = {  # official labels, committee-type-code-descriptions
    "C": "Communication cost",
    "D": "Delegate committee",
    "E": "Electioneering communication",
    "H": "House",
    "I": "Independent expenditor (person or group)",
    "N": "PAC - nonqualified",
    "O": "Independent expenditure-only (Super PACs)",
    "P": "Presidential",
    "Q": "PAC - qualified",
    "S": "Senate",
    "U": "Single-candidate independent expenditure",
    "V": "Hybrid PAC (with Non-Contribution Account) - Nonqualified",
    "W": "Hybrid PAC (with Non-Contribution Account) - Qualified",
    "X": "Party - nonqualified",
    "Y": "Party - qualified",
    "Z": "National party nonfederal account",
}
ORG_TYPE = {  # official “Interest group category”, committee-master-file-description
    "C": "Corporation",
    "L": "Labor organization",
    "M": "Membership organization",
    "T": "Trade association",
    "V": "Cooperative",
    "W": "Corporation without capital stock",
}
DESIGNATION = {  # official, committee-master-file-description
    "A": "Authorized by a candidate",
    "B": "Lobbyist/Registrant PAC",
    "D": "Leadership PAC",
    "J": "Joint fundraiser",
    "P": "Principal campaign committee of a candidate",
    "U": "Unauthorized",
}
TYPE_SOURCE = "https://www.fec.gov/campaign-finance-data/committee-type-code-descriptions/"
ORG_SOURCE = "https://www.fec.gov/campaign-finance-data/committee-master-file-description/"
PAS2_SOURCE = "https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/"
PAS2_FILE = "https://www.fec.gov/files/bulk-downloads/2026/pas226.zip"
CM_FILE = "https://www.fec.gov/files/bulk-downloads/2026/cm26.zip"
CCL_FILE = "https://www.fec.gov/files/bulk-downloads/2026/ccl26.zip"
IE_FILE = "https://www.fec.gov/files/bulk-downloads/2026/independent_expenditure_2026.csv"
IE_DESC = "https://www.fec.gov/campaign-finance-data/independent-expenditures-file-description/"
OTH_SOURCE = "https://www.fec.gov/campaign-finance-data/any-transaction-one-committee-another-file-description/"
OTH_FILE = "https://www.fec.gov/files/bulk-downloads/2026/oth26.zip"

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "org"

def parse_cm():
    out = {}
    for line in (UNP / "cm.txt").read_text(errors="replace").splitlines():
        c = line.split("|")
        if len(c) < 15: continue
        cid = c[0].strip()
        out[cid] = {
            "committee_id": cid, "name": c[1].strip(), "designation": c[8].strip(),
            "committee_type": c[9].strip(), "party": c[10].strip(),
            "org_type": c[12].strip(), "connected_org": c[13].strip(),
            "candidate_id": c[14].strip(),
        }
    return out

def parse_ccl():
    # CAND_ID, CAND_ELECTION_YR, FEC_ELECTION_YR, CMTE_ID, CMTE_TP, CMTE_DSGN, LINKAGE_ID
    rows = []
    for line in (UNP / "ccl.txt").read_text(errors="replace").splitlines():
        c = line.split("|")
        if len(c) < 7: continue
        rows.append({"candidate_id": c[0].strip(), "cand_election_yr": c[1].strip(),
                     "fec_election_yr": c[2].strip(), "committee_id": c[3].strip(),
                     "committee_type": c[4].strip(), "designation": c[5].strip(),
                     "linkage_id": c[6].strip()})
    return rows

def load_members():
    L = read_json(RAW / "legislators-current.json")
    people_site = read_json(BUILD / "site" / "people.json")["people"]
    by_bio = {p["bioguide"]: p for p in people_site if p.get("bioguide")}
    fec2bio, bio = {}, {}
    for p in L:
        b = p["id"]["bioguide"]
        ids = list(p["id"].get("fec") or [])
        bio[b] = {"bioguide": b, "name": by_bio.get(b, {}).get("name") or " ".join(p["name"].get(k, "") for k in ("first", "last")).strip(),
                  "slug": by_bio.get(b, {}).get("slug"), "fec_ids": ids}
        for f in ids:
            fec2bio[f] = b
    return bio, fec2bio

def leadership_from_api(cm, fec2bio):
    """Fill sponsor_candidate_ids for designation-D committees missing a candidate id."""
    if LEAD_CACHE.exists():
        return read_json(LEAD_CACHE)
    from fec import get
    out = {}
    page = 1
    while page <= 20:
        d, url = get("/committees/", [("designation", "D"), ("per_page", 100), ("page", page), ("cycle", 2026)])
        if not d: break
        for r in d.get("results") or []:
            cid = r.get("committee_id")
            sponsors = r.get("sponsor_candidate_ids") or ([] if not r.get("sponsor_candidate_id") else [r.get("sponsor_candidate_id")])
            out[cid] = {"committee_id": cid, "name": r.get("name"), "sponsor_candidate_ids": sponsors,
                        "designation": r.get("designation"), "source": "OpenFEC /committees/?designation=D&cycle=2026"}
        pag = d.get("pagination") or {}
        if page >= (pag.get("pages") or 1): break
        page += 1
    write_json(LEAD_CACHE, {"retrieved_at": now_iso(), "committees": out})
    return read_json(LEAD_CACHE)

def recipient_map(cm, ccl, bio, fec2bio, lead_api=None):
    """committee_id -> {bioguide, role: principal|leadership_pac, ...}"""
    rec = {}
    # principals and leadership PACs from 2026-cycle linkage
    for r in ccl:
        if r["fec_election_yr"] != "2026": continue
        if r["designation"] not in ("P", "D"): continue
        b = fec2bio.get(r["candidate_id"])
        if not b: continue
        rec[r["committee_id"]] = {"bioguide": b, "candidate_id": r["candidate_id"],
                                  "role": "principal" if r["designation"] == "P" else "leadership_pac",
                                  "designation": r["designation"], "via": "ccl"}
    # committee master CAND_ID for P/D
    for cid, c in cm.items():
        if c["designation"] not in ("P", "D") or not c["candidate_id"]: continue
        b = fec2bio.get(c["candidate_id"])
        if not b: continue
        rec.setdefault(cid, {"bioguide": b, "candidate_id": c["candidate_id"],
                             "role": "principal" if c["designation"] == "P" else "leadership_pac",
                             "designation": c["designation"], "via": "cm"})
    if lead_api:
        for cid, info in (lead_api.get("committees") or lead_api).items() if isinstance(lead_api, dict) else []:
            if isinstance(info, str): continue
            if not isinstance(info, dict) or "sponsor_candidate_ids" not in info:
                continue
            for sid in info.get("sponsor_candidate_ids") or []:
                b = fec2bio.get(sid)
                if b:
                    rec.setdefault(cid, {"bioguide": b, "candidate_id": sid, "role": "leadership_pac",
                                         "designation": "D", "via": "openfec-sponsor"})
                    break
    return rec

def classify(cm_row):
    ot = (cm_row or {}).get("org_type") or ""
    ct = (cm_row or {}).get("committee_type") or ""
    dg = (cm_row or {}).get("designation") or ""
    return {
        "committee_type": ct, "committee_type_full": COMMITTEE_TYPE.get(ct, ct or None),
        "org_type": ot, "org_type_full": ORG_TYPE.get(ot) if ot else None,
        "designation": dg, "designation_full": DESIGNATION.get(dg, dg or None),
        "connected_org": (cm_row or {}).get("connected_org") or None,
        "name": (cm_row or {}).get("name"),
    }

def parse_pas2(cm, recipients):
    """Aggregate 24K contributions to our P/D committees. Exclude memo X from totals."""
    # columns per official PAS2 description (0-based)
    # 0 CMTE_ID (filer/giver), 5 TRANSACTION_TP, 7 NAME, 14 AMT, 15 OTHER_ID (recipient),
    # 16 CAND_ID, 17 TRAN_ID, 19 MEMO_CD, 20 MEMO_TEXT, 21 SUB_ID
    pairs = {}  # (recip, giver) -> agg
    skipped_tp = collections.Counter()
    n_memo = n_used = n_other_recip = 0
    for line in (UNP / "itpas2.txt").read_text(errors="replace").splitlines():
        c = line.split("|")
        if len(c) < 22: continue
        tp = c[5].strip()
        if tp != "24K":
            skipped_tp[tp] += 1
            continue
        rid = c[15].strip()
        if rid not in recipients:
            n_other_recip += 1
            continue
        gid = c[0].strip()
        try:
            amt = float(c[14] or 0)
        except ValueError:
            continue
        memo = c[19].strip()
        key = (rid, gid)
        e = pairs.get(key)
        if not e:
            e = {"recipient_id": rid, "giver_id": gid, "recipient_name_file": c[7].strip(),
                 "total": 0.0, "count": 0, "memo_count": 0, "memo_total": 0.0,
                 "dates": [], "sub_ids": []}
            pairs[key] = e
        if memo == "X":
            e["memo_count"] += 1
            e["memo_total"] += amt
            n_memo += 1
            continue
        e["total"] += amt
        e["count"] += 1
        n_used += 1
        dt = c[13].strip()
        if dt and len(e["dates"]) < 3:
            e["dates"].append(dt)
        if len(e["sub_ids"]) < 3:
            e["sub_ids"].append(c[21].strip())
    rows = []
    for e in pairs.values():
        if e["count"] == 0 and e["memo_count"]:
            continue  # only memo items, no amount in the summarized total
        g = classify(cm.get(e["giver_id"]) or {})
        if not g.get("name"):
            g["name"] = None
        e["giver"] = {"committee_id": e["giver_id"], **g, "name": g.get("name")}
        e["total"] = round(e["total"], 2)
        e["memo_total"] = round(e["memo_total"], 2)
        e["source_file"] = "pas2"
        rows.append(e)
    stats = {"itemized_24k_included": n_used, "memo_excluded_from_totals": n_memo,
             "pairs": len(rows), "other_24k_not_to_our_recipients": n_other_recip,
             "other_transaction_types": dict(skipped_tp)}
    return rows, stats


def parse_oth_leadership(cm, recipients):
    """24K contributions to leadership PAC recipients from the official OTH file.

    The PAS2 file is limited to committee contributions to candidates, so
    receipts to leadership PACs are not in itpas2.txt. They appear as
    committee-to-committee 24K rows (OTHER_ID = leadership PAC) in itoth.txt.
    Memo-coded rows (MEMO_CD=X) are excluded from totals, same rule as PAS2.
    """
    lp = {cid for cid, info in recipients.items() if info["role"] == "leadership_pac"}
    path = UNP / "itoth.txt"
    if not path.exists():
        raise FileNotFoundError("unpacked/itoth.txt missing; unzip data/raw/fec/oth26.zip first")
    pairs = {}
    n_memo = n_used = n_other = 0
    for line in path.open(errors="replace"):
        c = line.split("|")
        if len(c) < 20:
            continue
        if c[5].strip() != "24K":
            continue
        rid = c[15].strip()
        if rid not in lp:
            n_other += 1
            continue
        gid = c[0].strip()
        try:
            amt = float(c[14] or 0)
        except ValueError:
            continue
        memo = c[19].strip()
        key = (rid, gid)
        e = pairs.get(key)
        if not e:
            e = {"recipient_id": rid, "giver_id": gid, "recipient_name_file": c[7].strip(),
                 "total": 0.0, "count": 0, "memo_count": 0, "memo_total": 0.0,
                 "dates": [], "sub_ids": []}
            pairs[key] = e
        if memo == "X":
            e["memo_count"] += 1
            e["memo_total"] += amt
            n_memo += 1
            continue
        e["total"] += amt
        e["count"] += 1
        n_used += 1
        dt = c[13].strip()
        if dt and len(e["dates"]) < 3:
            e["dates"].append(dt)
        if len(e["sub_ids"]) < 3 and len(c) > 21:
            e["sub_ids"].append(c[21].strip())
    rows = []
    for e in pairs.values():
        if e["count"] == 0 and e["memo_count"]:
            continue
        g = classify(cm.get(e["giver_id"]) or {})
        if not g.get("name"):
            g["name"] = None
        e["giver"] = {"committee_id": e["giver_id"], **g, "name": g.get("name")}
        e["total"] = round(e["total"], 2)
        e["memo_total"] = round(e["memo_total"], 2)
        e["source_file"] = "oth"
        rows.append(e)
    stats = {"itemized_24k_included": n_used, "memo_excluded_from_totals": n_memo,
             "pairs": len(rows), "other_24k_not_to_our_leadership_pacs": n_other}
    return rows, stats


def parse_ie_date(s):
    """Parse official IE file dates (14-OCT-26, 14-OCT-2026, or MM/DD/YYYY)."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return _ie_dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def ie_activity_date(row):
    """Dissemination date, falling back to expenditure date."""
    return parse_ie_date(row.get("dissem_dt")) or parse_ie_date(row.get("exp_date"))


def is_ie_notice(row):
    """Best-effort label for a 24/48-hour notice vs a regular report.

    Not used to decide whether two rows are the same expenditure. Merge
    decisions use previous-file-number chains only.
    """
    prev = (row.get("prev_file_num") or "").strip()
    if prev:
        return False
    if not (row.get("exp_date") or "").strip():
        return True
    rec = parse_ie_date(row.get("receipt_dat"))
    act = ie_activity_date(row)
    if rec and act and 0 <= (rec - act).days <= 3:
        return True
    return False


def _ie_file_num(row):
    try:
        return int(row.get("file_num") or 0)
    except ValueError:
        return 0


def _ie_prev_file_num(row):
    prev = (row.get("prev_file_num") or "").strip()
    if not prev:
        return None
    try:
        return int(prev)
    except ValueError:
        return None


def _ie_sig(row):
    try:
        amt = f"{float(row.get('exp_amo') or 0):.2f}"
    except ValueError:
        amt = "0.00"
    return (
        (row.get("spe_id") or "").strip(),
        (row.get("cand_id") or "").strip(),
        amt,
        (row.get("pay") or "").strip(),
        (row.get("sup_opp") or "").strip().upper(),
    )


def dedupe_ie_rows(rows):
    """Latest amendment per (spender, candidate, tran_id), then merge a
    later filing with an earlier one only when the later row's previous-file
    number (or the amendment chain of previous-file numbers) points to the
    earlier filing and the rows share spender, candidate, amount, payee, and
    support/oppose. Receipt-minus-dissemination date is never a reason to merge.
    Two unlinked notices or reports with the same amount are kept as separate buys.
    Returns (kept_rows, stats).
    """
    latest = {}
    for row in rows:
        cand = (row.get("cand_id") or "").strip()
        spe = (row.get("spe_id") or "").strip()
        so = (row.get("sup_opp") or "").strip().upper()
        if so not in ("S", "O"):
            continue
        tid = (row.get("tran_id") or "").strip() or (row.get("image_num") or "")
        fnum = _ie_file_num(row)
        key = (spe, cand, tid)
        prev = latest.get(key)
        if not prev or fnum >= prev[0]:
            latest[key] = (fnum, row)
    remaining = [row for _, row in latest.values()]
    by_file = collections.defaultdict(list)
    for row in remaining:
        spe = (row.get("spe_id") or "").strip()
        cand = (row.get("cand_id") or "").strip()
        by_file[(spe, cand, _ie_file_num(row))].append(row)

    def ancestor_files(spe, cand, start_prev):
        seen, cur = set(), start_prev
        while cur and cur not in seen:
            seen.add(cur)
            nxt = None
            for r in by_file.get((spe, cand, cur), []):
                p = _ie_prev_file_num(r)
                if p:
                    nxt = p
                    break
            cur = nxt
        return seen

    dropped = set()
    for row in remaining:
        prev = _ie_prev_file_num(row)
        if not prev:
            continue
        spe = (row.get("spe_id") or "").strip()
        cand = (row.get("cand_id") or "").strip()
        sig = _ie_sig(row)
        later_f = _ie_file_num(row)
        for anc in ancestor_files(spe, cand, prev):
            for earlier in by_file.get((spe, cand, anc), []):
                if earlier is row or id(earlier) in dropped:
                    continue
                if _ie_file_num(earlier) >= later_f:
                    continue
                if _ie_sig(earlier) == sig:
                    dropped.add(id(earlier))

    kept = [r for r in remaining if id(r) not in dropped]
    n_dropped = len(dropped)
    amt_removed = 0.0
    for r in remaining:
        if id(r) in dropped:
            try:
                amt_removed += float(r.get("exp_amo") or 0)
            except ValueError:
                pass
    stats = {
        "unique_amended_rows": len(latest),
        "rows_after_notice_dedupe": len(kept),
        "notice_report_rows_dropped": n_dropped,
        "notice_report_amount_dropped": round(amt_removed, 2),
        "cross_filing_duplicate_rows_dropped": n_dropped,
        "cross_filing_amount_dropped": round(amt_removed, 2),
    }
    return kept, stats


def parse_ie(fec2bio):
    """Sum independent expenditures after official-file dedupes.

    1) For each (spender, candidate, transaction_id), keep the row with the
       highest file number (latest amendment).
    2) Merge a later filing with an earlier one only when the later row's
       previous-file number (or amendment chain) points to the earlier filing
       and the rows share spender, candidate, amount, payee, and support/oppose.
       Two unlinked notices or reports with the same amount are separate buys.
    """
    path = RAWFEC / "independent_expenditure_2026.csv"
    raw_rows = []
    with path.open(newline="", errors="replace") as f:
        for row in csv.DictReader(f):
            cand = (row.get("cand_id") or "").strip()
            if cand not in fec2bio:
                continue
            raw_rows.append(row)
    kept, dedupe_stats = dedupe_ie_rows(raw_rows)
    agg = {}
    for row in kept:
        cand = row["cand_id"].strip()
        spe = (row.get("spe_id") or "").strip()
        so = (row.get("sup_opp") or "").strip().upper()
        if so not in ("S", "O"): continue
        try:
            amt = float(row.get("exp_amo") or 0)
        except ValueError:
            continue
        key = (fec2bio[cand], cand, spe, so)
        e = agg.get(key)
        if not e:
            e = {"bioguide": fec2bio[cand], "candidate_id": cand, "spender_id": spe,
                 "spender_name": (row.get("spe_nam") or "").strip(),
                 "support_oppose": so,
                 "support_oppose_full": "Support" if so == "S" else "Oppose",
                 "total": 0.0, "count": 0}
            agg[key] = e
        e["total"] += amt
        e["count"] += 1
    for e in agg.values():
        e["total"] = round(e["total"], 2)
    stats = {
        "unique_amended_rows_for_current_members": dedupe_stats["unique_amended_rows"],
        "rows_after_notice_dedupe": len(kept),
        "cross_filing_duplicate_rows_dropped": dedupe_stats["notice_report_rows_dropped"],
        "cross_filing_amount_dropped": dedupe_stats["notice_report_amount_dropped"],
        "notice_report_rows_dropped": dedupe_stats["notice_report_rows_dropped"],
        "notice_report_amount_dropped": dedupe_stats["notice_report_amount_dropped"],
        "pairs": len(agg),
    }
    return list(agg.values()), stats

def main():
    use_api = "--leadership-api" in sys.argv
    bio, fec2bio = load_members()
    cm = parse_cm()
    ccl = parse_ccl()
    lead = None
    if use_api:
        print("fetching leadership PAC sponsors from OpenFEC", flush=True)
        lead = leadership_from_api(cm, fec2bio)
        # cache shape
        if "committees" not in lead:
            lead = {"committees": lead, "retrieved_at": now_iso()}
    elif LEAD_CACHE.exists():
        lead = read_json(LEAD_CACHE)
    rec = recipient_map(cm, ccl, bio, fec2bio, lead)
    # annotate recipient names
    for cid, info in rec.items():
        info["committee_name"] = (cm.get(cid) or {}).get("name")
        info["committee_type"] = (cm.get(cid) or {}).get("committee_type")
        info["member_name"] = bio.get(info["bioguide"], {}).get("name")
        info["member_slug"] = bio.get(info["bioguide"], {}).get("slug")
    money, money_stats = parse_pas2(cm, rec)
    oth_money, oth_stats = parse_oth_leadership(cm, rec)
    money.extend(oth_money)
    money_stats["leadership_pac_oth"] = oth_stats
    ie, ie_stats = parse_ie(fec2bio)
    # per-member rollups
    by_member = collections.defaultdict(lambda: {"money": [], "ie": []})
    for e in money:
        info = rec[e["recipient_id"]]
        by_member[info["bioguide"]]["money"].append({**e, "recipient_role": info["role"],
            "recipient_name": info.get("committee_name") or e["recipient_name_file"],
            "candidate_id": info["candidate_id"]})
    for e in ie:
        by_member[e["bioguide"]]["ie"].append(e)
    members_out = {}
    for b, blob in by_member.items():
        money_sorted = sorted(blob["money"], key=lambda x: -x["total"])
        cats = collections.defaultdict(lambda: {"total": 0.0, "count": 0, "givers": 0})
        for e in money_sorted:
            label = e["giver"].get("org_type_full") or "Interest group category not reported"
            cats[label]["total"] += e["total"]
            cats[label]["count"] += e["count"]
            cats[label]["givers"] += 1
        members_out[b] = {
            "bioguide": b, "name": bio.get(b, {}).get("name"), "slug": bio.get(b, {}).get("slug"),
            "money": money_sorted,
            "categories": [{"org_type_full": k, "total": round(v["total"], 2), "count": v["count"], "givers": v["givers"]}
                           for k, v in sorted(cats.items(), key=lambda kv: -kv[1]["total"])],
            "ie": sorted(blob["ie"], key=lambda x: -x["total"]),
        }
    out = {
        "retrieved_at": now_iso(),
        "cycle": 2026,
        "sources": {
            "committee_master": {"file": CM_FILE, "description": ORG_SOURCE},
            "committee_type_labels": {"description": TYPE_SOURCE},
            "linkage": {"file": CCL_FILE},
            "committee_contributions": {"file": PAS2_FILE, "description": PAS2_SOURCE,
                                        "transaction_type": "24K",
                                        "note": "Itemized contributions from committees to candidates (principals). MEMO_CD=X rows are excluded from totals."},
            "committee_to_committee": {"file": OTH_FILE, "description": OTH_SOURCE,
                                       "transaction_type": "24K",
                                       "note": "Itemized 24K contributions from committees to current members' leadership PACs. PAS2 does not include these receipts. MEMO_CD=X rows are excluded from totals."},
            "independent_expenditures": {"file": IE_FILE, "description": IE_DESC,
                                         "note": "For each spender, candidate, and transaction ID, the row with the highest file number is used (latest amendment)."},
        },
        "codes": {"committee_type": COMMITTEE_TYPE, "org_type": ORG_TYPE, "designation": DESIGNATION},
        "stats": {
            "current_members": len(bio), "members_with_fec_ids": len(set(fec2bio.values())),
            "recipient_committees": len(rec),
            "principals": sum(1 for v in rec.values() if v["role"] == "principal"),
            "leadership_pacs": sum(1 for v in rec.values() if v["role"] == "leadership_pac"),
            "members_with_money": sum(1 for v in members_out.values() if v["money"]),
            "members_with_ie": sum(1 for v in members_out.values() if v["ie"]),
            "money": money_stats, "ie": ie_stats,
        },
        "recipients": rec,
        "members": members_out,
    }
    write_json(OUT, out)
    print(json.dumps(out["stats"], indent=1))

if __name__ == "__main__":
    main()
