"""Turn official connection records into profile ties, org pages, and claims.

Merges new claims into data/build/site/claims.json without wiping existing
verified claims. Does not run ingest/build.py.

Claim ID prefixes:
  m_  itemized 24K committee contribution to a principal or leadership PAC
  mc_ FEC interest-group category total for a member
  ie_ independent expenditure (Schedule E / official IE file)
  lb_ LDA specific-issues text matching a sponsored or cosponsored bill
  rd_ LDA covered position naming the member

Displayed lists are capped (top committee givers, top IE spenders, top
lobbying matches). Org pages are created for organizations that appear in
those lists. A connection documents a record; it does not imply coordination,
influence, or wrongdoing.
"""
from __future__ import annotations
import hashlib, json, re, collections, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from lda_match import is_individual_registrant, load_individual_registrant_ids, looks_like_person_name
from connections_fec import (
    ORG_SOURCE, TYPE_SOURCE, PAS2_SOURCE, PAS2_FILE, OTH_SOURCE, OTH_FILE,
    IE_FILE, IE_DESC, ORG_TYPE,
)

SITE = BUILD / "site"
CLAIMS_PATH = SITE / "claims.json"
FEC_PATH = BUILD / "connections-fec.json"
LDA_PATH = BUILD / "connections-lda.json"
ORG_DIR = SITE / "orgs"
TOP_MONEY = 20
TOP_IE = 15
TOP_LOBBY = 20
TOP_RD = 15
LDA_DISCLAIMER = (
    "The Senate Office of Public Records cannot vouch for the accuracy of "
    "these lobbying disclosure filings after they were retrieved. Politidex "
    "does not use the Senate seal."
)
CONN_NOTE = (
    "A connection documents a fact in the official record. It does not, by "
    "itself, imply coordination, influence, or wrongdoing."
)

def cid(prefix, *parts):
    return prefix + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:14]

def last_name(name):
    parts = (name or "").split()
    skip = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v", "vi", "2nd", "3rd", "4th", "junior", "senior"}
    while parts and parts[-1].lower().strip(",.") in skip:
        parts.pop()
    return parts[-1].strip(",.") if parts else (name or "")

def usd(n):
    n = float(n)
    return f"${n:,.0f}" if abs(n - round(n)) < 0.005 else f"${n:,.2f}"

def org_slug_fec(committee_id):
    return "fec-" + (committee_id or "unknown").lower()

def org_slug_lda(kind, ident, name):
    ident = str(ident or "unknown")
    base = re.sub(r"[^a-z0-9]+", "-", (name or "org").lower()).strip("-")[:40] or "org"
    return f"lda-{kind}-{ident}-{base}"[:80]

def fec_disbursement_url(giver_id, recipient_id):
    return (f"https://www.fec.gov/data/disbursements/?committee_id={giver_id}"
            f"&recipient_committee_id={recipient_id}&two_year_transaction_period=2026")

def fec_ie_url(spender_id, candidate_id):
    return (f"https://www.fec.gov/data/independent-expenditures/?committee_id={spender_id}"
            f"&candidate_id={candidate_id}&two_year_transaction_period=2026")

class ClaimBank:
    def __init__(self, data):
        self.data = data
        self.claims = data["claims"]
        self.added = self.updated = self.kept = 0

    def add(self, prefix, key, text, value, excerpt, source_name, source_url, check, retrieved_at):
        i = cid(prefix, *key)
        old = self.claims.get(i)
        rec = {"id": i, "text": text, "value": value, "excerpt": excerpt,
               "source_name": source_name, "source_url": source_url,
               "check": check, "retrieved_at": retrieved_at, "status": "unverified"}
        if (old and old.get("check") == check and old.get("value") == value
                and old.get("excerpt") == excerpt and old.get("source_url") == source_url
                and old.get("status") in ("verified", "blocked")):
            rec["status"] = old["status"]
            rec["verified_at"] = old.get("verified_at")
            rec["verify_note"] = old.get("verify_note")
            rec["blocked_reason"] = old.get("blocked_reason")
            rec["retrieved_at"] = old.get("retrieved_at") or retrieved_at
            rec["text"] = text  # allow wording updates without re-fetch
            self.kept += 1
        elif old:
            self.updated += 1
        else:
            self.added += 1
        self.claims[i] = rec
        return i

    def save(self):
        write_json(CLAIMS_PATH, self.data)

def money_claim(bank, member, row, retrieved):
    g = row["giver"]
    gname = g.get("name") or row["giver_id"]
    role = row["recipient_role"]
    role_l = "principal campaign committee" if role == "principal" else "leadership PAC"
    src_file = row.get("source_file") or ("oth" if role == "leadership_pac" else "pas2")
    if src_file == "oth":
        source_name = "Federal Election Commission (any transaction from one committee to another, 2026 cycle)"
        desc = OTH_SOURCE
        bulk = OTH_FILE
    else:
        source_name = "Federal Election Commission (contributions from committees to candidates, 2026 cycle)"
        desc = PAS2_SOURCE
        bulk = PAS2_FILE
    text = (f"In the 2026 election cycle, {gname} ({row['giver_id']}) reported "
            f"{usd(row['total'])} in itemized committee contributions (transaction type 24K, "
            f"{row['count']} {'receipt' if row['count']==1 else 'receipts'}; memo-coded rows excluded) "
            f"to {row['recipient_name'] or row['recipient_id']} ({row['recipient_id']}), "
            f"the {role_l} of {member['name']}.")
    excerpt = (f"sum(TRANSACTION_TP=24K, MEMO_CD!=X, CMTE_ID={row['giver_id']}, "
               f"OTHER_ID={row['recipient_id']}) = {row['total']}; count = {row['count']}")
    check = {"kind": "fec-bulk-24k", "giver_id": row["giver_id"], "recipient_id": row["recipient_id"],
             "source_file": src_file, "expected_total": row["total"], "expected_count": row["count"],
             "bulk_url": bulk, "description_url": desc}
    return bank.add("m_", (row["giver_id"], row["recipient_id"], "24K", src_file),
                    text, row["total"], excerpt, source_name,
                    fec_disbursement_url(row["giver_id"], row["recipient_id"]),
                    check, retrieved)

def category_claim(bank, member, cat, recipient_ids, retrieved):
    label = cat["org_type_full"] or "Interest group category not reported"
    code = cat.get("org_type") or ""
    if code:
        text = (f"Of itemized 24K committee contributions reported to {member['name']}'s "
                f"principal campaign committee and leadership PAC in the 2026 cycle, "
                f"{usd(cat['total'])} came from committees the FEC Interest group category "
                f"lists as “{label}.”")
    else:
        text = (f"Of itemized 24K committee contributions reported to {member['name']}'s "
                f"principal campaign committee and leadership PAC in the 2026 cycle, "
                f"{usd(cat['total'])} came from committees with no FEC Interest group category reported.")
    excerpt = (f"Interest group category (ORG_TP) {code or '(blank)'} = {label}; "
               f"sum of 24K totals = {cat['total']}; givers = {cat['givers']}")
    check = {"kind": "fec-bulk-24k-category", "recipient_ids": sorted(recipient_ids),
             "org_type": code, "expected_total": cat["total"],
             "label": label, "description_url": ORG_SOURCE}
    return bank.add("mc_", (member["bioguide"], "org", code or "blank"),
                    text, cat["total"], excerpt,
                    "Federal Election Commission (committee master, Interest group category)",
                    ORG_SOURCE, check, retrieved)

def ie_claim(bank, member, row, retrieved):
    so = row["support_oppose_full"]
    name = row.get("spender_name") or row["spender_id"]
    text = (f"In the 2026 election cycle, {name} ({row['spender_id']}) reported "
            f"{usd(row['total'])} in independent expenditures to {so.lower()} {member['name']} "
            f"({row['count']} {'expenditure' if row['count']==1 else 'expenditures'}; "
            f"latest amendment per transaction).")
    excerpt = (f"sum(spe_id={row['spender_id']}, cand_id={row['candidate_id']}, "
               f"sup_opp={row['support_oppose']}, latest file_num per tran_id) = {row['total']}; "
               f"count = {row['count']}")
    check = {"kind": "fec-bulk-ie", "spender_id": row["spender_id"],
             "candidate_id": row["candidate_id"], "support_oppose": row["support_oppose"],
             "expected_total": row["total"], "expected_count": row["count"],
             "bulk_url": IE_FILE, "description_url": IE_DESC}
    return bank.add("ie_", (row["spender_id"], row["candidate_id"], row["support_oppose"]),
                    text, row["total"], excerpt,
                    "Federal Election Commission (independent expenditures, 2026 cycle)",
                    fec_ie_url(row["spender_id"], row["candidate_id"]),
                    check, retrieved)

def lobby_claim(bank, row, retrieved):
    verb = "sponsored" if row["role"] == "sponsor" else "cosponsored"
    title = f" ({row['bill_title']})" if row.get("bill_title") else ""
    text = (f"This filing's issue text lists {row['bill_label']}. "
            f"{row['member_name']} {verb} {row['bill_label']} (119th Congress).")
    excerpt = row["excerpt"]
    check = {"kind": "lda-excerpt", "url": row["api_url"], "excerpt": excerpt,
             "needle": row["bill_label"].replace(" ", ""), "field": "description"}
    return bank.add("lb_", (row["bioguide"], row["filing_uuid"], row["bill_type"], row["bill_number"], row["role"]),
                    text, row["bill_label"], excerpt,
                    "Senate Office of Public Records (LDA.gov)",
                    row.get("document_url") or row["api_url"],
                    check, retrieved)

def rd_claim(bank, row, retrieved):
    who = row.get("lobbyist_name") or "a lobbyist"
    text = (f"A lobbying disclosure filing by {row['registrant_name']}, on behalf of "
            f"{row['client_name']}, lists a covered position for {who}: “{row['excerpt']}.”")
    excerpt = row["excerpt"]
    check = {"kind": "lda-excerpt", "url": row["api_url"], "excerpt": excerpt,
             "name": last_name(row["member_name"]), "field": "covered_position"}
    return bank.add("rd_", (row["bioguide"], row["filing_uuid"], row.get("lobbyist_name"), row["covered_position"][:80]),
                    text, row["covered_position"], excerpt,
                    "Senate Office of Public Records (LDA.gov)",
                    row.get("document_url") or row["api_url"],
                    check, retrieved)

def scheme_claim(bank, retrieved):
    excerpt = ("Interest group category. C = Corporation; L = Labor organization; "
               "M = Membership organization; T = Trade association; V = Cooperative; "
               "W = Corporation without capital stock")
    # The live page wording may wrap; the verifier looks for each official label.
    text = ("The FEC committee master file records an Interest group category (ORG_TP) "
            "with the official values Corporation, Labor organization, Membership organization, "
            "Trade association, Cooperative, and Corporation without capital stock.")
    check = {"kind": "source-excerpt", "url": ORG_SOURCE,
             "needles": ["Interest group category", "Corporation", "Labor organization",
                         "Membership organization", "Trade association", "Cooperative",
                         "Corporation without capital stock"]}
    return bank.add("mc_", ("scheme", "org_tp"), text, "ORG_TP", excerpt,
                    "Federal Election Commission (committee master file description)",
                    ORG_SOURCE, check, retrieved)

def main():
    fec = read_json(FEC_PATH)
    lda = read_json(LDA_PATH) if LDA_PATH.exists() else {"lobbying": [], "revolving": [], "coverage": {}, "retrieved_at": None, "source": {}}
    bank = ClaimBank(read_json(CLAIMS_PATH))
    retrieved = fec["retrieved_at"]
    lda_retrieved = lda.get("retrieved_at") or retrieved
    people = {p["slug"]: p for p in read_json(SITE / "people.json")["people"]}
    by_bio = {p["bioguide"]: p for p in people.values() if p.get("bioguide")}
    rec = fec["recipients"]
    rec_by_bio = collections.defaultdict(list)
    for cid_, info in rec.items():
        rec_by_bio[info["bioguide"]].append(cid_)


    def _denylist_pats():
        terms = []
        pth = ROOT / ".opsec-denylist"
        if pth.exists():
            terms.extend(x.strip() for x in pth.read_text().splitlines() if x.strip())
        import os
        terms.extend(x.strip() for x in (os.environ.get("OPSEC_DENYLIST") or "").split(",") if x.strip())
        return [re.compile(re.escape(x), re.I) for x in terms]
    _DENY = _denylist_pats()
    def _denied_text(*parts):
        if not _DENY:
            return False
        blob = " ".join("" if x is None else str(x) for x in parts)
        return any(p.search(blob) for p in _DENY)

    scheme_id = scheme_claim(bank, retrieved)
    lda_by_bio = collections.defaultdict(list)
    rd_by_bio = collections.defaultdict(list)
    for row in lda.get("lobbying") or []:
        lda_by_bio[row["bioguide"]].append(row)
    for row in lda.get("revolving") or []:
        rd_by_bio[row["bioguide"]].append(row)

    # orgs: slug -> record
    orgs = {}

    def ensure_fec_org(committee_id, name, meta, kind_note):
        slug = org_slug_fec(committee_id)
        if slug not in orgs:
            orgs[slug] = {
                "slug": slug, "kind": "fec-committee", "committee_id": committee_id,
                "name": name or committee_id, "url": f"https://www.fec.gov/data/committee/{committee_id}/",
                "connected_org": (meta or {}).get("connected_org"),
                "committee_type": (meta or {}).get("committee_type"),
                "committee_type_full": (meta or {}).get("committee_type_full"),
                "org_type": (meta or {}).get("org_type"),
                "org_type_full": (meta or {}).get("org_type_full"),
                "designation": (meta or {}).get("designation"),
                "designation_full": (meta or {}).get("designation_full"),
                "members": [],
            }
        return slug

    def ensure_lda_org(kind, ident, name):
        slug = org_slug_lda(kind, ident, name)
        if slug not in orgs:
            orgs[slug] = {
                "slug": slug, "kind": f"lda-{kind}", "lda_id": ident,
                "name": name or str(ident), "url": None, "members": [],
            }
        return slug

    individual_registrant_ids = load_individual_registrant_ids()

    def mark_individual(slug, registrant_id=None, registrant_name=None, lobbyist_name=None):
        if orgs.get(slug, {}).get("kind") != "lda-registrant":
            return
        if orgs[slug].get("registrant_individual"):
            return
        rid = registrant_id if registrant_id is not None else orgs[slug].get("lda_id")
        if rid in individual_registrant_ids or str(rid) in individual_registrant_ids:
            orgs[slug]["registrant_individual"] = True
            return
        if is_individual_registrant(registrant_name, lobbyist_name):
            orgs[slug]["registrant_individual"] = True

    def add_org_member(slug, entry):
        orgs[slug]["members"].append(entry)

    profiles_dir = SITE / "profiles"
    n_money = n_ie = n_lb = n_rd = n_prof = 0
    members_with = collections.Counter()

    for bio, blob in fec["members"].items():
        person = by_bio.get(bio) or {"name": blob.get("name"), "slug": blob.get("slug"), "bioguide": bio}
        slug = person.get("slug") or blob.get("slug")
        if not slug:
            continue
        path = profiles_dir / f"{slug}.json"
        if not path.exists():
            continue
        pr = read_json(path)
        recipient_ids = rec_by_bio.get(bio, [])
        money_sorted = blob.get("money") or []
        ie_sorted = sorted(blob.get("ie") or [], key=lambda x: -x["total"])
        cats = blob.get("categories") or []

        money_rows = []
        for row in money_sorted[:TOP_MONEY]:
            claim = money_claim(bank, person, row, retrieved)
            g = row["giver"]
            gslug = ensure_fec_org(row["giver_id"], g.get("name"), g, "money")
            money_rows.append({
                "giver_id": row["giver_id"], "giver_name": g.get("name") or row["giver_id"],
                "org_slug": gslug, "connected_org": g.get("connected_org"),
                "committee_type_full": g.get("committee_type_full"),
                "org_type_full": g.get("org_type_full") or "Interest group category not reported",
                "designation_full": g.get("designation_full"),
                "recipient_id": row["recipient_id"], "recipient_name": row.get("recipient_name"),
                "recipient_role": row["recipient_role"], "total": row["total"], "count": row["count"],
                "source_file": row.get("source_file"), "claim": claim,
            })
            add_org_member(gslug, {
                "slug": slug, "name": person["name"], "bioguide": bio,
                "relationship": "committee contribution to " + (
                    "principal campaign committee" if row["recipient_role"]=="principal" else "leadership PAC"),
                "total": row["total"], "claim": claim,
            })
        n_money += len(money_rows)

        cat_rows = []
        # Recompute org_type code onto categories from official labels.
        label_to_code = {v: k for k, v in ORG_TYPE.items()}
        for cat in cats:
            label = cat["org_type_full"] or "Interest group category not reported"
            code = label_to_code.get(cat["org_type_full"] or "", "")
            cat = {**cat, "org_type": code}
            claim = category_claim(bank, person, cat, recipient_ids, retrieved)
            cat_rows.append({**cat, "claim": claim})

        ie_rows = []
        for row in ie_sorted[:TOP_IE]:
            claim = ie_claim(bank, person, row, retrieved)
            sslug = ensure_fec_org(row["spender_id"], row.get("spender_name"),
                                   {"name": row.get("spender_name")}, "ie")
            ie_rows.append({
                "spender_id": row["spender_id"], "spender_name": row.get("spender_name") or row["spender_id"],
                "org_slug": sslug, "support_oppose": row["support_oppose"],
                "support_oppose_full": row["support_oppose_full"],
                "candidate_id": row["candidate_id"], "total": row["total"], "count": row["count"],
                "claim": claim,
            })
            add_org_member(sslug, {
                "slug": slug, "name": person["name"], "bioguide": bio,
                "relationship": f"independent expenditure — {row['support_oppose_full']}",
                "total": row["total"], "claim": claim,
            })
        n_ie += len(ie_rows)

        # Lobbying: prefer sponsored, then unique client+bill, cap
        lobby_src = sorted(lda_by_bio.get(bio, []), key=lambda r: (0 if r["role"]=="sponsor" else 1, r.get("client_name") or ""))
        lobby_rows, seen_l = [], set()
        for row in lobby_src:
            k = (row["client_id"], row["bill_type"], row["bill_number"], row["registrant_id"])
            if k in seen_l:
                continue
            seen_l.add(k)
            claim = lobby_claim(bank, row, lda_retrieved)
            cslug = ensure_lda_org("client", row["client_id"], row["client_name"])
            rslug = ensure_lda_org("registrant", row["registrant_id"], row["registrant_name"])
            item = {
                "bill_label": row["bill_label"], "bill_title": row.get("bill_title"),
                "role": row["role"], "client_name": row["client_name"], "client_id": row["client_id"],
                "client_slug": cslug, "registrant_name": row["registrant_name"],
                "registrant_id": row["registrant_id"], "registrant_slug": rslug,
                "general_issue_code_display": row.get("general_issue_code_display"),
                "filing_year": row.get("filing_year"), "filing_type_display": row.get("filing_type_display"),
                "document_url": row.get("document_url"), "excerpt": row["excerpt"], "claim": claim,
            }
            if _denied_text(item.get("excerpt"), item.get("client_name"), item.get("registrant_name"), item.get("bill_title")):
                continue
            lobby_rows.append(item)
            rel = f"lobbying disclosure on {row['bill_label']} ({row['role']})"
            add_org_member(cslug, {"slug": slug, "name": person["name"], "bioguide": bio, "relationship": rel, "claim": claim})
            add_org_member(rslug, {"slug": slug, "name": person["name"], "bioguide": bio, "relationship": rel, "claim": claim})
            mark_individual(rslug, row.get("registrant_id"), row.get("registrant_name"), row.get("lobbyist_name"))
            if len(lobby_rows) >= TOP_LOBBY:
                break
        n_lb += len(lobby_rows)

        rd_rows, seen_r = [], set()
        for row in rd_by_bio.get(bio, []):
            k = (re.sub(r"\s+", " ", (row.get("lobbyist_name") or "").strip().upper()),
                 str(row.get("registrant_id") or ""))
            if k in seen_r:
                continue
            seen_r.add(k)
            claim = rd_claim(bank, row, lda_retrieved)
            rslug = ensure_lda_org("registrant", row["registrant_id"], row["registrant_name"])
            item = {
                "lobbyist_name": row.get("lobbyist_name"), "excerpt": row["excerpt"],
                "covered_position": row["covered_position"],
                "registrant_name": row["registrant_name"], "registrant_slug": rslug,
                "client_name": row["client_name"], "document_url": row.get("document_url"),
                "filing_year": row.get("filing_year"), "claim": claim,
            }
            if _denied_text(item.get("excerpt"), item.get("covered_position"), item.get("registrant_name"), item.get("lobbyist_name"), item.get("client_name")):
                continue
            rd_rows.append(item)
            add_org_member(rslug, {
                "slug": slug, "name": person["name"], "bioguide": bio,
                "relationship": "covered position listed on a lobbying disclosure filing",
                "claim": claim,
            })
            mark_individual(rslug, row.get("registrant_id"), row.get("registrant_name"), row.get("lobbyist_name"))
            if len(rd_rows) >= TOP_RD:
                break
        n_rd += len(rd_rows)

        pr["ties"] = {
            "note": CONN_NOTE,
            "lda_disclaimer": LDA_DISCLAIMER,
            "scheme_claim": scheme_id,
            "retrieved_at": retrieved,
            "lda_retrieved_at": lda.get("retrieved_at"),
            "lda_coverage": lda.get("coverage"),
            "money": {
                "source_note": ("Itemized committee contributions (FEC transaction type 24K) to this member’s "
                                "principal campaign committee, from the official contributions-from-committees-to-candidates "
                                "file, and to this member’s leadership PAC, from the official any-transaction-from-one-committee-to-another "
                                "file, 2026 cycle. Memo-coded rows are excluded from totals. Interest group category is the FEC ORG_TP field. "
                                f"The list shows the {TOP_MONEY} largest giving committees."),
                "rows": money_rows,
                "categories": cat_rows,
                "all_givers": len(money_sorted),
            },
            "ie": {
                "source_note": ("Independent expenditures reported in the official FEC 2026 independent expenditures file. "
                                "For each spender, candidate, and transaction ID, the row with the highest file number is used. "
                                "A later filing is merged with an earlier one only when the later row's previous-file "
                                "number (or amendment chain) points to the earlier filing and they share spender, "
                                "candidate, amount, payee, and support or oppose. Two unlinked notices or reports "
                                "with the same amount are counted as separate expenditures. "
                                f"The list shows the {TOP_IE} largest spender–position totals."),
                "rows": ie_rows,
                "all_pairs": len(ie_sorted),
            },
            "lobbying": {
                "source_note": ("Senate LDA quarterly filings (2025–2026) whose specific-issues text names a bill this member "
                                "sponsored or cosponsored in the 119th Congress. A mention is listed only when the text "
                                "immediately before the number in a Title (number) list, or between this bill number "
                                "and the next (including a House/Senate companion in the same cluster), "
                                "contains a distinctive multi-word short title or acronym from Congress.gov, or, when "
                                "Congress.gov has no formal short title, a distinctive name many LDA filings attach to "
                                "that bill number. A title that belongs to the next bill in a Title (number) list is "
                                "not used to corroborate this number. The filing period must not end before the bill was introduced. "
                                "A filing date is never, by itself, a reason to publish. Mentions of a 110th–118th Congress "
                                "law or a bare list of bill numbers are not published. "
                                f"Up to {TOP_LOBBY} matches are listed."),
                "rows": lobby_rows,
                "all_matches": len(lda_by_bio.get(bio, [])),
            },
            "revolving": {
                "source_note": "The filing text is shown; Politidex does not characterize the relationship.",
                "rows": rd_rows,
                "all_matches": len(rd_by_bio.get(bio, [])),
            },
        }
        write_json(path, pr)
        n_prof += 1
        if money_rows: members_with["money"] += 1
        if ie_rows: members_with["ie"] += 1
        if lobby_rows: members_with["lobbying"] += 1
        if rd_rows: members_with["revolving"] += 1

    # Label self-registered individual registrants from official filings
    # (never from registrant-name == client-name; that flags self-filing orgs).
    n_ind = 0
    for org in orgs.values():
        if org.get("kind") != "lda-registrant":
            continue
        rid = org.get("lda_id")
        if rid in individual_registrant_ids or str(rid) in individual_registrant_ids:
            org["registrant_individual"] = True
            n_ind += 1
        else:
            org.pop("registrant_individual", None)
    n_client_ind = 0
    for org in orgs.values():
        if org.get("kind") != "lda-client":
            continue
        if looks_like_person_name(org.get("name") or ""):
            org["client_individual"] = True
            n_client_ind += 1
        else:
            org.pop("client_individual", None)

    # Write org pages (dedupe member entries per claim)
    if ORG_DIR.exists():
        for old in ORG_DIR.glob("*.json"):
            old.unlink()
    index = []
    for slug, org in sorted(orgs.items(), key=lambda kv: (-len(kv[1]["members"]), kv[1]["name"] or "")):
        seen = set()
        uniq = []
        for m in org["members"]:
            k = (m.get("claim"), m.get("slug"), m.get("relationship"))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(m)
        org["members"] = uniq
        org["member_count"] = len({m["slug"] for m in uniq})
        org["note"] = CONN_NOTE
        if org["kind"].startswith("lda"):
            org["lda_disclaimer"] = LDA_DISCLAIMER
        write_json(ORG_DIR / f"{slug}.json", org)
        index.append({"slug": slug, "name": org["name"], "kind": org["kind"],
                      "member_count": org["member_count"], "committee_id": org.get("committee_id"),
                      "lda_id": org.get("lda_id")})
    write_json(SITE / "orgs-index.json", {
        "generated_at": now_iso(), "count": len(index), "orgs": index,
        "note": CONN_NOTE,
    })
    bank.save()
    stats = {
        "profiles_updated": n_prof,
        "claims_added": bank.added, "claims_updated": bank.updated, "claims_kept_verified": bank.kept,
        "money_rows": n_money, "ie_rows": n_ie, "lobbying_rows": n_lb, "revolving_rows": n_rd,
        "org_pages": len(index), "individual_registrant_orgs": n_ind, "individual_client_orgs": n_client_ind,
        "members_with": dict(members_with),
        "lda_coverage": lda.get("coverage"),
        "total_claims": len(bank.claims),
    }
    write_json(BUILD / "connections-build-stats.json", stats)
    print(json.dumps(stats, indent=1))

if __name__ == "__main__":
    main()
