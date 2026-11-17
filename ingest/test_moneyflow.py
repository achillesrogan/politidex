"""Tests for the FEC money-flow ingest: reconciliation and the privacy filter.

Run: python3 ingest/test_moneyflow.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneyflow_lib as M

ROOT = Path(__file__).resolve().parent.parent
failures = []


def check(name, cond, detail=""):
    if cond:
        print("  ok ", name)
    else:
        failures.append(name)
        print(" FAIL", name, detail)


def master_row(**kw):
    row = {
        "committee_id": "C00003418",
        "name": "REPUBLICAN NATIONAL COMMITTEE",
        "committee_type": "Y",
        "designation": "U",
        "party": "REP",
        "org_type": "",
        "connected_organization": None,
        "state": "DC",
    }
    row.update(kw)
    return row


def test_parsers_drop_address_and_people_columns():
    print("parsers")
    treasurer = "SENTINEL_TREASURER"
    street = "SENTINEL_STREET_2501"
    city = "SENTINEL_CITY"
    zip_code = "64108"
    person = "SENTINEL_PERSON"
    line = "|".join([
        "C00000059", "HALLMARK CARDS PAC", treasurer, street, "", city, "MO", zip_code,
        "B", "Q", "UNK", "M", "C", "HALLMARK CARDS, INC.", "H0AL00000",
    ])
    row = M.parse_master_line(line)
    blob = json.dumps(row)
    check("master keeps the committee name", row["name"] == "HALLMARK CARDS PAC")
    check("master drops treasurer", treasurer not in blob)
    check("master drops street", street not in blob)
    check("master drops city", city not in blob)
    check("master drops zip", zip_code not in blob)
    check("master drops candidate id", "H0AL00000" not in blob)
    check("master has no forbidden keys", not M.public_problems(row))
    check("master keeps filing frequency", row["filing_frequency"] == "M")

    # Individual-contribution column (index 7) and refund column must not be parsed.
    fields = ["C00000059", "SOME PAC", "Q", "U", "M", "10.00", "0", "SENTINEL_INDIV_CONTRIB"] + ["0"] * 19
    fields[12] = "20.00"
    fields[26] = "10/14/2026"
    webk = M.parse_webk_line("|".join(fields))
    check("webk reads total disbursements", webk["disbursements_cents"] == 2000)
    check("webk reads total receipts", webk["receipts_cents"] == 1000)
    check("webk does not keep the individual-contribution figure", "SENTINEL_INDIV_CONTRIB" not in json.dumps(webk))
    check("webk has no individual key", "indiv" not in json.dumps(webk).lower())


def test_person_like_org_payees():
    print("person-like organizations")
    master = {"C00003418": master_row()}
    person = "JANE Q DOE"
    benefit = "JANE Q DOE HSA"
    payroll = "JANE Q DOE PAYROLL"
    bare = M.classify_payee("ORG", "", person, None, "001", master, "ADMINISTRATIVE AND MANAGEMENT - SALARY")
    check("bare personal name filed as ORG is the individuals bucket", bare["bucket"] == "individuals" and bare["name"] is None)
    check("bare personal name is not stored", person not in json.dumps(bare))
    hsa = M.classify_payee("ORG", "", benefit, None, "", master, "HEALTH SAVINGS ACCOUNT CONTRIBUTION")
    check("HSA label filed as ORG is the individuals bucket", hsa["bucket"] == "individuals")
    check("HSA label is not stored", benefit not in json.dumps(hsa) and "JANE" not in json.dumps(hsa))
    labeled = M.classify_payee("ORG", "", payroll, None, "", master, "")
    check("payroll label tied to a person is the individuals bucket", labeled["bucket"] == "individuals")
    last_first = M.classify_payee("ORG", "", "DOE, JANE Q", None, "", master, "")
    check("LAST, FIRST filed as ORG is the individuals bucket", last_first["bucket"] == "individuals")
    check("LAST, FIRST is not stored", "JANE" not in json.dumps(last_first))
    com = M.classify_payee("COM", "", person, "24K", None, master, "")
    check("person-like name on a non-person entity type is bucketed", com["bucket"] == "individuals")
    unclear_word = M.classify_payee("ORG", "", "CARSON", None, "", master, "INSURANCE")
    check("one-word label with only an insurance purpose is bucketed", unclear_word["bucket"] == "individuals")
    office = M.classify_payee("ORG", "", "CARSON", None, "", master, "OFFICE EXPENSE")
    check("one-word label with only an office-expense purpose is bucketed", office["bucket"] == "individuals")
    blank = M.classify_payee("ORG", "", "CARSON", "24C", None, master, "")
    check("one-word label with no purpose is bucketed", blank["bucket"] == "individuals")
    vendor = M.classify_payee("ORG", "", "RIPPLEPAY", None, "", master, "PAYROLL TAXES")
    check("one-word payroll vendor stays a business", vendor["node_kind"] == "business" and vendor["name"] == "RIPPLEPAY")
    express = M.classify_payee("ORG", "", "AMERICAN EXPRESS", None, "", master, "CREDIT CARD PAYMENT")
    check("card network stays a business", express["node_kind"] == "business")
    party = M.classify_payee("ORG", "", "EXAMPLE DEMOCRATIC PARTY", None, "", master, "")
    check("party name stays a business", party["node_kind"] == "business")
    domain = M.classify_payee("ORG", "", "DIRECTMAIL.COM", None, "", master, "POSTAGE")
    check("domain payee stays a business", domain["node_kind"] == "business")
    postal = M.classify_payee("ORG", "", "USPS", None, "", master, "POSTAGE")
    check("postal service stays a business", postal["node_kind"] == "business")
    firm = M.classify_payee("ORG", "", "ACME PRINTING LLC", None, "", master, "")
    check("named company with LLC stays a business", firm["node_kind"] == "business" and firm["name"] == "ACME PRINTING LLC")
    initial = M.classify_payee("ORG", "", "DOE, JANE A.", None, "", master, "")
    check("initial with a period is bucketed", initial["bucket"] == "individuals" and "JANE" not in json.dumps(initial))
    plan = M.classify_payee("ORG", "", "ALEX MORA 401K", None, "", master, "")
    paren = M.classify_payee("ORG", "", "ALEX MORA 401(K)", None, "", master, "")
    check("401K label is bucketed", plan["bucket"] == "individuals" and paren["bucket"] == "individuals")
    check("401K label is not stored", "MORA" not in json.dumps(plan) and "MORA" not in json.dumps(paren))
    no_purpose = M.classify_payee("ORG", "", "ALEX MORA", "24K", None, master, "")
    check("bare first and last with no purpose is bucketed", no_purpose["bucket"] == "individuals")
    generic = M.classify_payee("ORG", "", "ALEX MORA SPORTS", None, "", master, "")
    check("personal name plus a generic trade word is bucketed", generic["bucket"] == "individuals" and "MORA" not in json.dumps(generic))
    registered_trade = M.classify_payee("ORG", "", "ALEX MORA SPORTS LLC", None, "", master, "")
    check("the same label with LLC stays a business", registered_trade["node_kind"] == "business")
    registered = M.classify_payee("ORG", "C00003418", person, "24K", None, master, "")
    check("registered committee id is not reclassified as a person", registered["bucket"] == "unclear" or registered.get("official_id") == "C00003418")
    # ORG plus a known committee id is the existing conflict rule.
    check("conflict still does not publish the personal name", person not in json.dumps(registered))
    records = [{
        "payee_key": "residual:individuals", "edge_kind": "reported disbursement", "amount_cents": 5000,
        "count": 2, "purpose_code": None, "name": None, "official_id": None, "node_kind": "residual",
        "terminal": True, "bucket": "individuals", "image": None, "sub_id": None, "file_num": None,
        "sources": ["oppexp"],
    }]
    committee = {
        "committee_id": "C00000001", "name": "EXAMPLE COMMITTEE", "committee_type": "Q",
        "designation": "U", "party": "", "org_type": "C", "connected_organization": None,
        "state": None, "receipts_cents": 5000, "disbursements_cents": 5000,
        "coverage_end": "2026-10-14", "type_conflict": False, "summary_committee_type": "Q",
    }
    shard = M.build_shard(committee, records, "2026-11-16T00:00:00+00:00", {}, top_n=25)
    dumped = json.dumps(shard)
    check("shard for a person-like payee has no name", person not in dumped and "JANE" not in dumped)
    check("shard sample ids for that bucket are empty",
          shard["children"][0]["edge"]["source"]["check"].get("sub_id") is None
          and shard["children"][0]["edge"]["source"]["check"].get("image_number") is None)
    check("person-like amount still reconciles", shard["reconciliation"]["ok"] is True)


def test_privacy_filter():
    print("privacy")
    master = {"C00003418": master_row()}
    person = "SENTINEL_PERSON_NAME"
    unclear = "SENTINEL_UNCLEAR_NAME"
    street = "SENTINEL_STREET"
    ind = M.classify_payee("IND", "C00003418", person, "24K", None, master)
    check("individual is a residual bucket", ind["bucket"] == "individuals" and ind["name"] is None)
    check("individual name is not on the result", person not in json.dumps(ind))
    can = M.classify_payee("CAN", "", person, "24H", None, master)
    check("candidate entity is the individuals bucket", can["bucket"] == "individuals")
    blank = M.classify_payee("", "C00003418", unclear, "24K", None, master)
    check("blank entity type is unclear even with a committee id", blank["bucket"] == "unclear")
    check("blank entity does not keep the name", unclear not in json.dumps(blank))
    check("blank entity does not keep the committee id", "C00003418" not in json.dumps(blank))
    weird = M.classify_payee("XYZ", "", "ACME WIDGET LLC", "24K", None, master)
    check("unrecognized entity type is unclear", weird["bucket"] == "unclear")
    check("unrecognized entity does not keep the organization name", "ACME" not in json.dumps(weird))
    conflict = M.classify_payee("ORG", "C00003418", "ACME", "24K", None, master)
    check("ORG plus a known committee id is unclear", conflict["bucket"] == "unclear")
    vendor = M.classify_payee("ORG", "H6CA24113", "ACME MEDIA LLC", "24E", None, master)
    dumped = json.dumps(vendor)
    check("ORG payee is a business", vendor["node_kind"] == "business" and vendor["name"] == "ACME MEDIA LLC")
    check("candidate id on an independent-expenditure row is not stored", "H6CA24113" not in dumped)
    check("street is not a classify input and is absent", street not in dumped)
    committee = M.classify_payee("CCM", "C00003418", person, "24K", None, master)
    check("candidate committee uses the master name", committee["name"] == "REPUBLICAN NATIONAL COMMITTEE")
    check("transaction name is not kept when the master has a name", person not in json.dumps(committee))
    check("edge kind is an allowed phrase", committee["edge_kind"] in M.EDGE_KIND_SET)


def test_reconciliation():
    print("reconciliation")
    committee = {
        "committee_id": "C00000001",
        "name": "EXAMPLE COMMITTEE",
        "committee_type": "Q",
        "designation": "U",
        "party": "",
        "org_type": "T",
        "connected_organization": None,
        "state": None,
        "receipts_cents": 5000,
        "disbursements_cents": 10000,
        "coverage_end": "2026-10-14",
        "type_conflict": False,
        "summary_committee_type": "Q",
    }
    records = [
        {"payee_key": "business:aaa", "edge_kind": "spent", "amount_cents": 4000, "count": 2,
         "purpose_code": "004", "name": "ACME MEDIA LLC", "official_id": None, "node_kind": "business",
         "terminal": True, "bucket": None, "image": "202601019999999999", "sub_id": "100", "file_num": "10",
         "sources": ["oppexp"]},
        {"payee_key": "business:bbb", "edge_kind": "spent", "amount_cents": 3000, "count": 1,
         "purpose_code": "001", "name": "OTHER VENDOR", "official_id": None, "node_kind": "business",
         "terminal": True, "bucket": None, "image": None, "sub_id": "101", "file_num": "11",
         "sources": ["oppexp"]},
        {"payee_key": "residual:individuals", "edge_kind": "reported disbursement", "amount_cents": 1000,
         "count": 4, "purpose_code": None, "name": None, "official_id": None, "node_kind": "residual",
         "terminal": True, "bucket": "individuals", "image": None, "sub_id": None, "file_num": None,
         "sources": ["oppexp"]},
        {"payee_key": "residual:unclear", "edge_kind": "reported disbursement", "amount_cents": 500,
         "count": 1, "purpose_code": None, "name": None, "official_id": None, "node_kind": "residual",
         "terminal": True, "bucket": "unclear", "image": None, "sub_id": None, "file_num": None,
         "sources": ["oppexp"]},
    ]
    shard = M.build_shard(committee, records, "2026-11-16T00:00:00+00:00", {}, top_n=1)
    recn = shard["reconciliation"]
    check("child edges equal the official total", recn["child_edge_cents"] == 10000 and recn["ok"] is True)
    check("top payee is the larger vendor", shard["children"][0]["node"]["name"] == "ACME MEDIA LLC")
    check("individuals bucket is separate", any(ch["node"]["name"] == M.INDIVIDUAL_BUCKET_NAME for ch in shard["children"]))
    other = [ch for ch in shard["children"] if ch["node"]["name"] == M.OTHER_BUCKET_NAME][0]
    # tail 3000 + unclear 500 + gap 1500 = 5000
    check("other bucket holds the tail, unclear rows, and the unitemized gap", other["edge"]["amount_cents"] == 5000)
    check("fungibility note is on the shard", shard["fungibility_note"] == M.FUNGIBILITY_NOTE)
    check("edge kinds stay inside the allowed list", all(ch["edge"]["kind"] in M.EDGE_KIND_SET for ch in shard["children"]))
    check("claim shape is complete", all(k in shard["node"]["source"] for k in M.CLAIM_KEYS))
    check("no forbidden keys", not M.public_problems(shard))
    check("free-text purpose is not required and category text is official", "ACME" in json.dumps(shard))
    try:
        M.build_shard(dict(committee, disbursements_cents=1000), records, "2026-11-16T00:00:00+00:00", {}, top_n=1)
        check("overage raises", False)
    except M.ReconciliationError as exc:
        check("overage raises", exc.committee_id == "C00000001" and exc.delta_cents > 0, str(exc))
    negative = M.build_shard(
        dict(committee, disbursements_cents=-100, receipts_cents=0), [],
        "2026-11-16T00:00:00+00:00", {}, top_n=1,
    )
    check(
        "negative official total with no itemized rows is one residual",
        negative["reconciliation"]["child_edge_cents"] == -100
        and negative["children"][0]["node"]["name"] == M.OTHER_BUCKET_NAME,
    )


def test_pilot_selection_is_symmetric():
    print("selection")
    rows = []
    for i, amt in enumerate((100, 90, 80, 70)):
        rows.append({
            "committee_id": "C0000001%d" % i, "name": "DEM PARTY %d" % i, "party": "DEM",
            "committee_type": "Y", "designation": "U", "org_type": "",
            "disbursements_cents": amt, "itemized_count": 1, "type_conflict": False, "reconciled": True,
        })
    for i, amt in enumerate((50, 40, 30, 20)):
        rows.append({
            "committee_id": "C0000002%d" % i, "name": "REP PARTY %d" % i, "party": "REP",
            "committee_type": "Y", "designation": "U", "org_type": "",
            "disbursements_cents": amt, "itemized_count": 1, "type_conflict": False, "reconciled": True,
        })
    rows.append({
        "committee_id": "C00000030", "name": "BIG DEM PAC", "party": "DEM",
        "committee_type": "Q", "designation": "U", "org_type": "C",
        "disbursements_cents": 99999, "itemized_count": 5, "type_conflict": False, "reconciled": True,
    })
    rows.append({
        "committee_id": "C00000031", "name": "BLANK CORP PAC", "party": "",
        "committee_type": "Q", "designation": "U", "org_type": "C",
        "disbursements_cents": 10, "itemized_count": 1, "type_conflict": False, "reconciled": True,
    })
    rows.append({
        "committee_id": "C00000032", "name": "BLANK CORP NO ITEMS", "party": "",
        "committee_type": "W", "designation": "U", "org_type": "C",
        "disbursements_cents": 999, "itemized_count": 0, "type_conflict": False, "reconciled": True,
    })
    rows.append({
        "committee_id": "C00000033", "name": "UNKNOWN PARTY PAC", "party": "UNK",
        "committee_type": "Q", "designation": "U", "org_type": "L",
        "disbursements_cents": 999, "itemized_count": 4, "type_conflict": False, "reconciled": True,
    })
    rows.append({
        "committee_id": "C00000034", "name": "THIRD PARTY PAC", "party": "LIB",
        "committee_type": "Q", "designation": "U", "org_type": "T",
        "disbursements_cents": 999, "itemized_count": 4, "type_conflict": False, "reconciled": True,
    })
    rows.append({
        "committee_id": "C00000035", "name": "FAILED PAC", "party": "",
        "committee_type": "Q", "designation": "U", "org_type": "M",
        "disbursements_cents": 999, "itemized_count": 4, "type_conflict": False, "reconciled": False,
    })
    chosen = {c["committee_id"] for c in M.select_pilot(rows)}
    check("three DEM and three REP party committees", len([c for c in chosen if c.startswith("C0000001")]) == 3)
    check("largest DEM party committee is in", "C00000010" in chosen)
    check("fourth DEM party committee is out", "C00000013" not in chosen)
    check("three REP party committees", len([c for c in chosen if c.startswith("C0000002")]) == 3)
    check("a DEM-coded PAC is not the no-party pick", "C00000030" not in chosen)
    check("blank-party corporation PAC with itemized rows is in", "C00000031" in chosen)
    check("larger blank-party PAC with no itemized rows is out", "C00000032" not in chosen)
    check("UNK party code is not treated as no-party", "C00000033" not in chosen)
    check("a third-party code is not treated as no-party", "C00000034" not in chosen)
    check("a committee that failed reconciliation is out", "C00000035" not in chosen)


def test_transaction_direction_and_dates():
    print("direction")
    check("committee-to-committee contribution is money out", M.txn_class("24K") == "out")
    check("transfer out is money out", M.txn_class("24G") == "out")
    check("joint-fundraising memo receipt is not money out", M.txn_class("15J") == "in")
    check("transfer in is not money out", M.txn_class("18G") == "in")
    check("unknown code is not a disbursement", M.txn_class("99Z") == "unknown")
    check("memo X is excluded", M.is_memo("X") and M.is_memo("x") and not M.is_memo(""))
    check("cycle date parses", M.parse_fec_date("10212024") == "2024-10-21")
    check("slashed date parses", M.parse_fec_date("01/31/2025") == "2025-01-31")
    check("bad date is not invented", M.parse_fec_date("99999999") is None)
    check("2024-10-21 is outside the 2026 cycle window", not M.in_cycle("2024-10-21"))
    check("2026-10-14 is inside the cycle window", M.in_cycle("2026-10-14"))
    line = "C001|N|Q2|G2026|202601019999999999|24K|ORG|ACME|CITY|VA|22201|||01012026|10.00|C00003418||T1|1||SUB1"
    # 22 fields for pas2 — build a realistic one via pas2_parts on a crafted line.
    parts = ["C00000935", "N", "Q2", "G2026", "202601019999999999", "24K", "CCM", "SENTINEL_TXN_NAME",
             "SENTINEL_CITY", "VA", "22201", "", "", "01012026", "10.00", "C00003418", "H0VA00000",
             "SB1", "99", "", "", "12345"]
    parsed = M.pas2_parts("|".join(parts))
    check("pas2 amount is cents", parsed["amount_cents"] == 1000)
    check("pas2 does not return the candidate id", "cand" not in parsed and "H0VA00000" not in json.dumps(parsed))
    check("pas2 does not return the city", "SENTINEL_CITY" not in json.dumps(parsed))


def test_committed_pilot_shards():
    print("pilot shards")
    manifest_path = ROOT / "data" / "moneyflow" / "pilot" / "manifest.json"
    check("manifest exists", manifest_path.exists(), str(manifest_path))
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text())
    check("fungibility note is in the manifest", manifest.get("fungibility_note") == M.FUNGIBILITY_NOTE)
    check("manifest has no forbidden keys", not M.public_problems(manifest))
    pilots = manifest.get("pilot") or []
    check("pilot has both major-party rules and a no-party rule",
          any(p.get("selection_rule") == "party-qualified-top3" and p.get("party") == "DEM" for p in pilots)
          and any(p.get("selection_rule") == "party-qualified-top3" and p.get("party") == "REP" for p in pilots)
          and any(p.get("selection_rule") == "org-type-largest-no-party" for p in pilots))
    dem = [p for p in pilots if p.get("selection_rule") == "party-qualified-top3" and p.get("party") == "DEM"]
    rep = [p for p in pilots if p.get("selection_rule") == "party-qualified-top3" and p.get("party") == "REP"]
    check("three committees from each major party", len(dem) == 3 and len(rep) == 3, "%d %d" % (len(dem), len(rep)))
    for row in pilots:
        path = ROOT / row["shard"]
        check("shard file %s" % row["committee_id"], path.exists())
        if not path.exists():
            continue
        shard = json.loads(path.read_text())
        recn = shard["reconciliation"]
        check(
            "reconciles %s" % row["committee_id"],
            recn["ok"] is True and recn["child_edge_cents"] == recn["official_total_out_cents"],
        )
        check("note on %s" % row["committee_id"], shard.get("fungibility_note") == M.FUNGIBILITY_NOTE)
        problems = M.public_problems(shard)
        check("public check %s" % row["committee_id"], not problems, "; ".join(problems[:4]))
        for ch in shard["children"]:
            if ch["node"]["kind"] == "residual":
                check("residual has no sample sub_id %s" % row["committee_id"],
                      ch["edge"]["source"]["check"].get("sub_id") in (None,)
                      and ch["edge"]["source"]["check"].get("sample_sub_id") in (None, )
                      or ch["node"]["name"] != M.INDIVIDUAL_BUCKET_NAME
                      or ch["edge"]["source"]["check"].get("payee_names_stored") is False)


def test_committee_profile_is_factual_and_drops_a_person_like_sponsor():
    print("profile")
    sponsor = "JANE Q DOE"
    org = "HALLMARK CARDS, INC."
    master = {
        "C00000011": {
            "committee_id": "C00000011", "name": "EXAMPLE SSF", "committee_type": "Q",
            "designation": "U", "party": "", "org_type": "C", "filing_frequency": "Q",
            "connected_organization": org, "state": "MO",
        },
        "C00000012": {
            "committee_id": "C00000012", "name": "EXAMPLE PERSON SPONSOR", "committee_type": "Q",
            "designation": "U", "party": "DEM", "org_type": "", "filing_frequency": "M",
            "connected_organization": sponsor, "state": "KS",
        },
    }
    shard = {
        "node": {
            "official_id": "C00000011",
            "connected_organization": org,
            "source": {"retrieved_at": "2026-11-17T00:00:00+00:00"},
            "official_total_out": "10.00",
        },
        "children": [
            {"node": {"official_id": "C00000012", "kind": "committee"}, "edge": {"amount_cents": 100}},
            {"node": {"official_id": None, "kind": "business", "name": "ACME"}, "edge": {"amount_cents": 50}},
        ],
    }
    before = [shard["node"]["official_total_out"], shard["children"][0]["edge"]["amount_cents"]]
    M.attach_profiles(shard, master)
    check("profile does not change amounts", [shard["node"]["official_total_out"], shard["children"][0]["edge"]["amount_cents"]] == before)
    check("organization sponsor is kept", shard["node"]["profile"]["connected_organization"] == org)
    check("person-like sponsor is omitted", sponsor not in json.dumps(shard))
    slogan = "QUIET HARBOR LEAGUE"
    kept = M.committee_profile({
        "committee_id": "C00000013", "committee_type": "Y", "designation": "U",
        "party": "REP", "org_type": "", "filing_frequency": "M",
        "connected_organization": slogan, "state": "DC",
    }, "2026-11-17T00:00:00+00:00")
    check("multi-word organization sponsor is kept", kept["connected_organization"] == slogan)
    check("business node has no profile", "profile" not in shard["children"][1]["node"])
    check("profile source is the committee page", shard["node"]["profile"]["source"]["source_url"].startswith("https://www.fec.gov/data/committee/"))
    check("profile has no forbidden keys", not M.public_problems(shard))


def test_purpose_excerpt_match_ignores_markup_and_whitespace():
    print("purpose excerpt")
    import moneyflow_purposes as P
    page = "<p>The DCCC is the official campaign arm of the Democrats in the House.</p>"
    check("excerpt survives tags", P.excerpt_in_document("The DCCC is the official campaign arm of the Democrats in the House.", page))
    curly = "We\u2019re focused on lowering costs"
    encoded = "<strong>We&#8217;re   focused on lowering costs</strong>"
    check("excerpt survives a curly apostrophe and extra space", P.excerpt_in_document(curly, encoded))
    check("a different sentence is not a match", not P.excerpt_in_document("This sentence is not on the page.", page))


def test_sources_do_not_name_indiv_files():
    print("files")
    blob = json.dumps(M.FILE_URLS)
    check("no indiv bulk file", "indiv" not in blob.lower())
    wording = M.wording_document()
    check("wording note matches", wording["fungibility_note"] == M.FUNGIBILITY_NOTE)
    check("wording edge kinds are the allowed four", set(wording["edge_kinds"]) == set(M.EDGE_KINDS))


def test_web_app_does_not_import_shards():
    print("bundle")
    roots = [ROOT / "app", ROOT / "components", ROOT / "lib"]
    hit = []
    for base in roots:
        for path in base.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".js", ".mjs"}:
                continue
            if path.name.endswith(".test.mjs"):
                continue
            text = path.read_text(errors="replace")
            if "data/moneyflow" in text or "moneyflow_lib" in text:
                hit.append(str(path.relative_to(ROOT)))
    check("web app does not import money-flow shards", not hit, ",".join(hit))


if __name__ == "__main__":
    test_parsers_drop_address_and_people_columns()
    test_person_like_org_payees()
    test_privacy_filter()
    test_reconciliation()
    test_pilot_selection_is_symmetric()
    test_transaction_direction_and_dates()
    test_purpose_excerpt_match_ignores_markup_and_whitespace()
    test_committee_profile_is_factual_and_drops_a_person_like_sponsor()
    test_sources_do_not_name_indiv_files()
    test_web_app_does_not_import_shards()
    test_committed_pilot_shards()
    if failures:
        print("FAILED", len(failures))
        sys.exit(1)
    print("ok")
