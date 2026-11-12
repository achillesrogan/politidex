"""Regression tests for LDA name/bill match rules and IE notice dedupe.

Run: python ingest/test_match_validation.py
"""
from __future__ import annotations
import sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lda_match as M

def mem(**kw):
    defaults = dict(firsts=(), chambers=frozenset(), gender="", surname_collision=False)
    defaults.update(kw)
    if not defaults["firsts"]:
        defaults["firsts"] = (defaults["first"].lower(),)
    defaults["last_lower"] = defaults["last"].lower()
    return M.MemberRec(**defaults)

WARREN = mem(bioguide="W000817", official="Elizabeth Warren", first="Elizabeth", last="Warren",
             firsts=("elizabeth",), chambers=frozenset({"sen"}), gender="F", surname_collision=True)
DAVIDSON = mem(bioguide="D000626", official="Warren Davidson", first="Warren", last="Davidson",
               firsts=("warren",), chambers=frozenset({"rep"}), gender="M", surname_collision=True)
ROY = mem(bioguide="R000614", official="Chip Roy", first="Chip", last="Roy",
          firsts=("chip",), chambers=frozenset({"rep"}), gender="M", surname_collision=True)
DEAN = mem(bioguide="D000631", official="Madeleine Dean", first="Madeleine", last="Dean",
           firsts=("madeleine",), chambers=frozenset({"rep"}), gender="F", surname_collision=True)
PAUL = mem(bioguide="P000603", official="Rand Paul", first="Rand", last="Paul",
           firsts=("rand",), chambers=frozenset({"sen"}), gender="M", surname_collision=True)
TONKO = mem(bioguide="T000469", official="Paul Tonko", first="Paul", last="Tonko",
            firsts=("paul",), chambers=frozenset({"rep"}), gender="M", surname_collision=False)
BEAN = mem(bioguide="B001314", official="Aaron Bean", first="Aaron", last="Bean",
           firsts=("aaron",), chambers=frozenset({"rep"}), gender="M", surname_collision=True)
SCOTT = mem(bioguide="S001184", official="Tim Scott", first="Tim", last="Scott",
            firsts=("tim",), chambers=frozenset({"sen", "rep"}), gender="M", surname_collision=True)

failures = []

def check(name, cond, detail=""):
    if cond:
        print("  ok ", name)
    else:
        failures.append(name)
        print(" FAIL", name, detail)

def decisions(text, member):
    return [(h.kind, h.decision, h.matched, h.reason) for h in M.find_position_hits(text, member)]

def test_wrong_member_title_surname():
    print("name matches")
    # 1. Rep. Warren Davidson must not publish on Elizabeth Warren
    hits = M.find_position_hits("Financial Services Counsel, Rep. Warren Davidson", WARREN)
    pub = [h for h in hits if h.decision == "publish"]
    check("Warren Davidson is not published for Elizabeth Warren", not pub, hits)
    # 2. It should publish for Warren Davidson (title + first + last)
    hits = M.find_position_hits("Financial Services Counsel, Rep. Warren Davidson", DAVIDSON)
    check("Warren Davidson publishes for Warren Davidson",
          any(h.decision == "publish" and "Warren Davidson" in h.matched for h in hits), hits)
    # 3. Rep. Roy Blunt / Chip Roy
    hits = M.find_position_hits("Chief of Staff Rep. Roy Blunt", ROY)
    check("Roy Blunt is not published for Chip Roy", not [h for h in hits if h.decision == "publish"], hits)
    # 4. Sen. Dean Heller / Madeleine Dean (also wrong chamber)
    hits = M.find_position_hits("Staff Assistant, Sen. Dean Heller", DEAN)
    pub = [h for h in hits if h.decision == "publish"]
    rej = [h for h in hits if h.decision == "reject"]
    check("Dean Heller is not published for Madeleine Dean", not pub, hits)
    # lookahead should prevent title_last "Sen. Dean"; if anything remains it must not be publish
    # 5. Rep. Paul Tonko / Rand Paul (wrong chamber + following name)
    hits = M.find_position_hits("Legislative Director, Rep. Paul Tonko", PAUL)
    check("Paul Tonko is not published for Rand Paul", not [h for h in hits if h.decision == "publish"], hits)
    hits = M.find_position_hits("Legislative Director, Rep. Paul Tonko", TONKO)
    check("Paul Tonko publishes for Paul Tonko",
          any(h.decision == "publish" for h in hits), hits)
    # 6. Congresswoman Bean / Aaron Bean (gender)
    hits = M.find_position_hits("EA, Congresswoman Bean; Assistant to DepDir, OPM", BEAN)
    check("Congresswoman Bean is rejected or absent for Aaron Bean",
          not [h for h in hits if h.decision == "publish"], hits)
    genderish = [h for h in hits if "gender" in h.reason or "Congresswoman" in h.reason or h.decision == "reject"]
    # lookahead-less title_last should reject on gender
    # 7. Title + surname only never publishes, even when unique-ish
    hits = M.find_position_hits("Staff for Rep. Tonko", TONKO)
    check("title plus surname only is not published (Sen. Tonko)",
          all(h.decision != "publish" or h.kind != "title_last" for h in hits) and
          not any(h.decision == "publish" and h.kind == "title_last" for h in hits), hits)
    hits = M.find_position_hits("Staff for Rep. Tonko", TONKO)
    check("title plus surname is queued for review when chamber fits",
          any(h.decision == "review" and h.kind == "title_last" for h in hits), hits)
    # 8. Tim Scott historically served in the House, so Congressman Tim Scott can publish
    hits = M.find_position_hits("Chief of Staff, Congressman Tim Scott (2011-2012)", SCOTT)
    check("Congressman Tim Scott publishes (House service in history)",
          any(h.decision == "publish" for h in hits), hits)
    # 9. Sen. Elizabeth Warren official / first last publishes
    hits = M.find_position_hits("Counsel to Senator Elizabeth Warren", WARREN)
    check("Senator Elizabeth Warren publishes",
          any(h.decision == "publish" for h in hits), hits)

def test_bill_parse_and_corroboration():
    print("bill matches")
    # misparses
    hits = M.parse_bill_mentions("Release Nos. 34 and related guidance")
    check("Release Nos. 34 is not S. 34", not any(h.typ == "S" and h.number == "34" for h in hits), hits)
    hits = M.parse_bill_mentions("customers. 2024 Farm bill implementation")
    check("customers. 2024 is not S. 2024", not any(h.typ == "S" and h.number == "2024" for h in hits), hits)
    hits = M.parse_bill_mentions("See Res. 89/25 for the attached exhibit")
    check("Res. 89/25 is not H.Res./S.Res. 89", not any(h.number == "89" for h in hits), hits)
    hits = M.parse_bill_mentions("The 2025 Dietary Guidelines for Americans")
    check("2025 Dietary Guidelines is not S. 2025", not any(h.typ == "S" and h.number == "2025" for h in hits), hits)
    # real prefixes still parse
    hits = M.parse_bill_mentions("issues related to H.R. 4366, the Save Local Business Act")
    check("H.R. 4366 still parses", any(h.typ == "HR" and h.number == "4366" for h in hits), hits)
    hits = M.parse_bill_mentions("support for S. 34, a 119th Congress bill")
    check("capital S. 34 still parses", any(h.typ == "S" and h.number == "34" for h in hits), hits)

    # prior congress / public law
    desc = "funding consistent with H.R. 4366, the FY2024 appropriations act (P.L. 118-42)"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Save Local Business Act", "2025-07-14", 2025, "third_quarter")
    check("Comer H.R. 4366 / P.L. 118-42 is rejected", d == "reject" and "118" in reason, (d, reason))

    desc = "H.R. 4366, the Save Local Business Act, in the 119th Congress"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Save Local Business Act", "2025-07-14", 2025, "third_quarter")
    check("H.R. 4366 with 119th short title is published", d == "publish", (d, reason))

    # date corroboration after intro, no conflicting title
    desc = "issues relating to H.R. 9026"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Some Distinctive Longtitle Act", "2025-01-10", 2025, "second_quarter")
    check("H.R. 9026 after introduction is not published on date alone", d == "review", (d, reason))

    # filing before introduction -> reject
    d, reason = M.decide_bill(hit, desc, "Some Distinctive Longtitle Act", "2025-10-01", 2025, "first_quarter")
    check("H.R. 9026 before introduction is rejected", d == "reject" and "before" in reason, (d, reason))

    # year-like S. without short title rejected
    desc = "S. 2025 and related proposals"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Unrelated Measure Act", "2025-01-03", 2025, "fourth_quarter")
    check("S. 2025 without short-title corroboration is rejected", d == "reject", (d, reason))

    desc = "S. 2025, the Distinctive Widgets Act, introduced this Congress"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Distinctive Widgets Act", "2025-01-03", 2025, "fourth_quarter")
    check("S. 2025 with short-title corroboration can publish", d == "publish", (d, reason))

    # different act title -> review even after intro
    desc = "H.R. 10550, the Consolidated Appropriations Act, 2024"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Border Something Unique Act", "2025-06-01", 2025, "third_quarter")
    check("different short title in excerpt goes to review", d == "review", (d, reason))

    # 118th Congress spelled out
    desc = "as passed in the 118th Congress as H.R. 4366"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Save Local Business Act", "2025-07-14", 2025, "fourth_quarter")
    check("118th Congress citation is rejected", d == "reject", (d, reason))


    # Gillen-style: a generic word from a long official title, outside or inside the window, is not enough
    desc = "North Atlantic right whale issues; H.R. 9026 and other coastal bills"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc,
        "To protect the North Atlantic right whale and for other purposes",
        "2025-01-10", 2025, "second_quarter", all_hits=M.parse_bill_mentions(desc))
    check("Gillen H.R. 9026 Atlantic whale word is not published", d != "publish", (d, reason))

    # Title match only in the window between this number and the next
    desc = "Save Local Business Act discussed generally; H.R. 9026; H.R. 1000 the Save Local Business Act"
    hits = M.parse_bill_mentions(desc)
    d, reason = M.decide_bill(hits[0], desc, "Save Local Business Act", "2025-01-10", 2025, "second_quarter", all_hits=hits)
    check("title after the next bill number does not corroborate this number", d != "publish", (d, reason))

    # EPIC Act acronym from Congress.gov short title
    desc = "support for H.R. 1492, the EPIC Act, in this Congress"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "To amend the Social Security Act to adjust the negotiation period",
        "2025-02-01", 2025, "first_quarter",
        short_titles=["EPIC Act"], acronyms={"EPIC"})
    check("Tim Moore H.R. 1492 EPIC Act acronym publishes", d == "publish", (d, reason))

    # pre-introduction even with a matching title is rejected
    d, reason = M.decide_bill(hit, desc, "To amend the Social Security Act",
        "2026-06-01", 2025, "first_quarter",
        short_titles=["EPIC Act"], acronyms={"EPIC"})
    check("filing before introduction is rejected even with a short title", d == "reject", (d, reason))

    # bare number list
    desc = "priorities include H.R. 9026, H.R. 1000, and H.R. 2000"
    hits = M.parse_bill_mentions(desc)
    d, reason = M.decide_bill(hits[0], desc, "Something Distinctive Widgets Act", "2025-01-03", 2025, "second_quarter", all_hits=hits)
    check("bare number list is not published", d != "publish", (d, reason))

    # Local attached short title / acronym (Congress.gov has no formal short title for this bill)
    desc = "Pharmacy issues. H.R. 1492, the EPIC Act, in this Congress."
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "To amend title XI of the Social Security Act to equalize the negotiation period",
        "2025-02-21", 2025, "second_quarter")
    check("H.R. 1492 EPIC Act attached locally publishes without a Congress.gov short title",
          d == "publish", (d, reason))

    desc = "Small molecule discrepancy - H.R. 1492 & S. 832, The EPIC Act; H.R. 1672, the MINI Act"
    hits = M.parse_bill_mentions(desc)
    d, reason = M.decide_bill(hits[0], desc, "To amend title XI of the Social Security Act to equalize the negotiation period",
        "2025-02-21", 2025, "third_quarter", all_hits=hits)
    check("H.R. 1492/S. 832 companion cluster still sees EPIC Act", d == "publish", (d, reason, [h.raw for h in hits]))

    desc = "H.R. 1492 -- \"To amend title XI of the Social Security Act to equalize the negotiation period between small-molecule and biologic candidates under the Drug Price Negotiation Program.\""
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "To amend title XI of the Social Security Act to equalize the negotiation period between small-molecule and biologic candidates under the Drug Price Negotiation Program.",
        "2025-02-21", 2025, "third_quarter")
    check("quoted official long title in the local window can publish", d == "publish", (d, reason))

    # Waters H.J.Res. 170 (119th introduced 2026-04-30): earlier filing is rejected
    desc = "H.J.Res. 170, providing for congressional disapproval of the HUD and USDA energy efficiency rule"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc,
        "Providing for congressional disapproval under chapter 8 of title 5, United States Code, of the rule submitted by the Department of Housing and Urban Development",
        "2026-04-30", 2025, "fourth_quarter")
    check("Waters H.J.Res. 170 before introduction is rejected", d == "reject" and "before" in reason, (d, reason, hit))

    # Murray S. 4503 (119th introduced 2026-05-12)
    desc = "S. 4503, the Advancing Menopause Care and Mid-Life Women's Health Act"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Advancing Menopause Care and Mid-Life Women's Health Act",
        "2026-05-12", 2025, "fourth_quarter")
    check("Murray S. 4503 before introduction is rejected", d == "reject" and "before" in reason, (d, reason))
    d, reason = M.decide_bill(hit, desc, "Advancing Menopause Care and Mid-Life Women's Health Act",
        "2026-05-12", 2026, "third_quarter")
    check("Murray S. 4503 after introduction publishes on the short title", d == "publish", (d, reason))

    # Cassidy S. 4965 (119th introduced 2026-07-14)
    desc = "S. 4965, the Railroad Retirement Board Stability Act"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(hit, desc, "Railroad Retirement Board Stability Act",
        "2026-07-14", 2026, "second_quarter")
    check("Cassidy S. 4965 before introduction is rejected", d == "reject" and "before" in reason, (d, reason))
    d, reason = M.decide_bill(hit, desc, "Railroad Retirement Board Stability Act",
        "2026-07-14", 2026, "third_quarter")
    check("Cassidy S. 4965 after introduction publishes on the short title", d == "publish", (d, reason))

    # B27: a generic policy acronym (PFAS) in the window is not title corroboration
    desc = ("ity protection related to water sector, H.R. 1267. Monitor status of "
            "USEPA vaildated risk assessment model related to PFAS and biosolids.")
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(
        hit, desc, "Water Systems PFAS Liability Protection Act",
        "2025-02-12", 2025, "second_quarter",
        short_titles=["Water Systems PFAS Liability Protection Act"])
    check("Wesley Bell H.R. 1267 generic PFAS acronym is not published",
          d != "publish", (d, reason))

    # The same short title still publishes when the full title is in the window
    desc = "H.R. 1267, the Water Systems PFAS Liability Protection Act"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(
        hit, desc, "Water Systems PFAS Liability Protection Act",
        "2025-02-12", 2025, "second_quarter",
        short_titles=["Water Systems PFAS Liability Protection Act"])
    check("H.R. 1267 still publishes on the full short title", d == "publish", (d, reason))

    # Title (number) lists: the title BEFORE the number is the one that belongs to it.
    desc = ("Born-Alive Abortion Survivors Protection Act (H.R. 1061) - "
            "Protecting Sensitive Locations Act (S. 229)")
    hits = M.parse_bill_mentions(desc)
    hr = next(h for h in hits if h.typ == "HR" and h.number == "1061")
    d, reason = M.decide_bill(
        hr, desc, "Protecting Sensitive Locations Act",
        "2025-02-06", 2025, "first_quarter",
        short_titles=["Protecting Sensitive Locations Act"], all_hits=hits)
    check("Garamendi H.R. 1061 Title (number) list is not published on the next item's title",
          d != "publish", (d, reason))

    desc = "S. 455/H.R. 1061, Protecting Sensitive Locations Act; detention of children in ICE facilities (general)"
    hits = M.parse_bill_mentions(desc)
    hr = next(h for h in hits if h.typ == "HR" and h.number == "1061")
    d, reason = M.decide_bill(
        hr, desc, "Protecting Sensitive Locations Act",
        "2025-02-06", 2025, "first_quarter",
        short_titles=["Protecting Sensitive Locations Act"], all_hits=hits)
    check("Garamendi H.R. 1061 still publishes when the short title follows the number",
          d == "publish", (d, reason))

    desc = "Protecting Sensitive Locations Act (S.455 / H.R. 1061): Letter to Congress in support"
    hits = M.parse_bill_mentions(desc)
    hr = next(h for h in hits if h.typ == "HR" and h.number == "1061")
    d, reason = M.decide_bill(
        hr, desc, "Protecting Sensitive Locations Act",
        "2025-02-06", 2025, "first_quarter",
        short_titles=["Protecting Sensitive Locations Act"], all_hits=hits)
    check("Garamendi H.R. 1061 publishes when the preceding Title (number) matches",
          d == "publish", (d, reason, [h.raw for h in hits]))

    desc = ("Follow the Science Act (H.R. 8765) - Prioritizing Primary Care Act (H.R. 21/S.6) - "
            "Born-Alive Abortion Survivors Protection Act (H.R. 1061)")
    hits = M.parse_bill_mentions(desc)
    hr = next(h for h in hits if h.typ == "HR" and h.number == "8765")
    d, reason = M.decide_bill(
        hr, desc, "Prioritizing Primary Care Act of 2026",
        "2026-05-12", 2026, "second_quarter",
        short_titles=["Prioritizing Primary Care Act of 2026"], all_hits=hits)
    check("Rouzer H.R. 8765 Title (number) list is not published on the next item's title",
          d != "publish", (d, reason))

    desc = "ACP supported H.R. 8765, the Prioritizing Primary Care Act."
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(
        hit, desc, "Prioritizing Primary Care Act of 2026",
        "2026-05-12", 2026, "third_quarter",
        short_titles=["Prioritizing Primary Care Act of 2026"])
    check("Rouzer H.R. 8765 still publishes when the short title follows the number",
          d == "publish", (d, reason))

    desc = ("Addressing Barriers for Caregivers (ABC) Act (H.R. 879) - "
            "Medicare Patient Access and Practice Stabilization Act (H.R. 1510) - "
            "Due Process Continuity of Care Act (S. 891)")
    hits = M.parse_bill_mentions(desc)
    hr = next(h for h in hits if h.typ == "HR" and h.number == "879")
    d, reason = M.decide_bill(
        hr, desc, "Medicare Patient Access and Practice Stabilization Act of 2025",
        "2025-01-31", 2025, "first_quarter",
        short_titles=["Medicare Patient Access and Practice Stabilization Act of 2025"],
        all_hits=hits)
    check("Sherman H.R. 879 Title (number) list is not published on the next item's title",
          d != "publish", (d, reason))

    desc = ("Ensuring Community Access to Pharmacist Services Act S. 2617/H.R. 1244; "
            "Reducing Drug Prices for Seniors Act S. 882; Patients Before Middlemen Act S. 927")
    hits = M.parse_bill_mentions(desc)
    hr = next(h for h in hits if h.typ == "HR" and h.number == "1244")
    d, reason = M.decide_bill(
        hr, desc, "Reducing Drug Prices for Seniors Act",
        "2025-02-12", 2026, "first_quarter",
        short_titles=["Reducing Drug Prices for Seniors Act"], all_hits=hits)
    check("Donald Davis H.R. 1244 Title-then-number list is not published on the next item's title",
          d != "publish", (d, reason, [h.raw for h in hits]))

    desc = "HR 1244, Reducing Drug Prices for Seniors Act"
    hit = M.parse_bill_mentions(desc)[0]
    d, reason = M.decide_bill(
        hit, desc, "Reducing Drug Prices for Seniors Act",
        "2025-02-12", 2025, "fourth_quarter",
        short_titles=["Reducing Drug Prices for Seniors Act"])
    check("Donald Davis H.R. 1244 still publishes when the short title follows the number",
          d == "publish", (d, reason))



def test_ie_dedupe_tuple():
    print("IE notice/report dedupe")
    from connections_fec import dedupe_ie_rows

    # New Deal notice + later report, same dissem date: count $826,729 once
    rows = [
        {"spe_id": "C1", "cand_id": "S1", "exp_amo": "826729", "exp_date": "14-OCT-26",
         "dissem_dt": "14-OCT-26", "receipt_dat": "15-OCT-26", "pay": "Canal Partners Media",
         "sup_opp": "O", "file_num": "2026573", "tran_id": "E-8", "prev_file_num": "", "amndt_ind": "N"},
        {"spe_id": "C1", "cand_id": "S1", "exp_amo": "826729", "exp_date": "14-OCT-26",
         "dissem_dt": "14-OCT-26", "receipt_dat": "03-NOV-26", "pay": "Canal Partners Media",
         "sup_opp": "O", "file_num": "2046197", "tran_id": "E-77", "prev_file_num": "2026573", "amndt_ind": "A1"},
        {"spe_id": "C1", "cand_id": "S1", "exp_amo": "20000", "exp_date": "14-OCT-26",
         "dissem_dt": "14-OCT-26", "receipt_dat": "03-NOV-26", "pay": "Canal Partners Media",
         "sup_opp": "O", "file_num": "2046200", "tran_id": "E-78", "prev_file_num": "", "amndt_ind": "A1"},
    ]
    kept, stats = dedupe_ie_rows(rows)
    total = sum(float(r["exp_amo"]) for r in kept)
    check("New Deal $826,729 counted once",
          sum(1 for r in kept if r["exp_amo"] == "826729") == 1 and stats["notice_report_rows_dropped"] == 1,
          (kept, stats))
    check("unique other payment kept", any(r["exp_amo"] == "20000" for r in kept) and abs(total - 846729) < 0.01, total)

    # HMP vs Bresnahan: same amount, no exp_date, different dissem dates — two buys
    hmp = [
        {"spe_id": "C009", "cand_id": "H4PA08124", "exp_amo": "238937.5", "exp_date": "",
         "dissem_dt": "27-OCT-26", "receipt_dat": "28-OCT-26", "pay": "MVAR Media LLC",
         "sup_opp": "O", "file_num": "2042895", "tran_id": "500693270", "prev_file_num": "", "amndt_ind": "N"},
        {"spe_id": "C009", "cand_id": "H4PA08124", "exp_amo": "238937.5", "exp_date": "",
         "dissem_dt": "28-OCT-26", "receipt_dat": "29-OCT-26", "pay": "MVAR Media LLC",
         "sup_opp": "O", "file_num": "2044083", "tran_id": "500693622", "prev_file_num": "", "amndt_ind": "N"},
    ]
    kept, stats = dedupe_ie_rows(hmp)
    total = sum(float(r["exp_amo"]) for r in kept)
    check("HMP vs Bresnahan Oct 27 and Oct 28 both kept",
          len(kept) == 2 and abs(total - 477875) < 0.01 and stats["notice_report_rows_dropped"] == 0,
          (len(kept), total, stats))

    # Two notices, same amount, same dissem date, still both kept (not notice+report)
    same = [
        {**hmp[0], "dissem_dt": "27-OCT-26", "receipt_dat": "28-OCT-26", "file_num": "1", "tran_id": "A"},
        {**hmp[0], "dissem_dt": "27-OCT-26", "receipt_dat": "28-OCT-26", "file_num": "2", "tran_id": "B"},
    ]
    kept, stats = dedupe_ie_rows(same)
    check("two notices with the same amount are not merged",
          len(kept) == 2 and stats["notice_report_rows_dropped"] == 0, (len(kept), stats))

    # Same amount, payee, and dissem date, but no previous-file link: do not merge
    # just because one receipt is more than three days after dissemination.
    unlinked = [
        {"spe_id": "C00718353", "cand_id": "H0MI02094", "exp_amo": "200", "exp_date": "19-OCT-26",
         "dissem_dt": "17-OCT-26", "receipt_dat": "20-OCT-26", "pay": "One Stop Promotions and Apparel",
         "sup_opp": "O", "file_num": "2032918", "tran_id": "SE.5842", "prev_file_num": "", "amndt_ind": "N"},
        {"spe_id": "C00718353", "cand_id": "H0MI02094", "exp_amo": "200", "exp_date": "19-OCT-26",
         "dissem_dt": "17-OCT-26", "receipt_dat": "24-OCT-26", "pay": "One Stop Promotions and Apparel",
         "sup_opp": "O", "file_num": "2041261", "tran_id": "SE.5905", "prev_file_num": "", "amndt_ind": "N"},
    ]
    kept, stats = dedupe_ie_rows(unlinked)
    check("Huizenga two $200 notices without a previous-file link are both kept",
          len(kept) == 2 and stats["notice_report_rows_dropped"] == 0
          and abs(sum(float(r["exp_amo"]) for r in kept) - 400) < 0.01,
          (len(kept), stats))

    calvert = [
        {"spe_id": "C00525824", "cand_id": "H2CA37023", "exp_amo": "2500", "exp_date": "28-MAY-26",
         "dissem_dt": "30-MAY-26", "receipt_dat": "28-MAY-26", "pay": "AUDACY",
         "sup_opp": "S", "file_num": "1980096", "tran_id": "SE.4229", "prev_file_num": "", "amndt_ind": "N"},
        {"spe_id": "C00525824", "cand_id": "H2CA37023", "exp_amo": "2500", "exp_date": "28-MAY-26",
         "dissem_dt": "30-MAY-26", "receipt_dat": "01-JUN-26", "pay": "AUDACY",
         "sup_opp": "S", "file_num": "1980695", "tran_id": "SE.4230", "prev_file_num": "", "amndt_ind": "N"},
        {"spe_id": "C00525824", "cand_id": "H2CA37023", "exp_amo": "2500", "exp_date": "28-MAY-26",
         "dissem_dt": "30-MAY-26", "receipt_dat": "04-JUN-26", "pay": "AUDACY",
         "sup_opp": "S", "file_num": "1981278", "tran_id": "SE.4232", "prev_file_num": "", "amndt_ind": "N"},
    ]
    kept, stats = dedupe_ie_rows(calvert)
    check("Calvert three $2,500 Audacy rows without a previous-file link are all kept",
          len(kept) == 3 and stats["notice_report_rows_dropped"] == 0
          and abs(sum(float(r["exp_amo"]) for r in kept) - 7500) < 0.01,
          (len(kept), stats))

    # Official 2026 IE file: named spender/candidate pairs must keep separate dissem dates
    import csv
    from pathlib import Path
    ie_path = Path(__file__).resolve().parents[1] / "data" / "raw" / "fec" / "independent_expenditure_2026.csv"
    official_rows = list(csv.DictReader(ie_path.open(newline="", encoding="utf-8", errors="replace")))
    pairs = {
        "HMP vs Bresnahan": ("C00495028", "H4PA08124", 4817026.34, 37),
        "HMP vs Valadao": ("C00495028", "H2CA20094", 8617134.57, 56),
        "HMP vs Max Miller": ("C00495028", "H2OH16051", 6830073.27, 16),
        "UDP vs Stevens": ("C00799031", "S6MI00426", 10498735.23, 25),
    }
    for label, (spe, cand, amt, count) in pairs.items():
        sub = [r for r in official_rows if (r.get("spe_id") or "").strip()==spe and (r.get("cand_id") or "").strip()==cand]
        kept, stats = dedupe_ie_rows(sub)
        total = sum(float(r.get("exp_amo") or 0) for r in kept)
        check(f"{label} official-file total is {amt} across {count} rows",
              len(kept)==count and abs(total-amt)<0.02,
              (label, len(kept), total, stats))

def test_individual_registrant_label():
    print("individual registrant label")
    check("Stephanie Kennan is an individual registrant",
          M.is_individual_registrant("STEPHANIE KENNAN", "STEPHANIE KENNAN"))
    check("Last, First form matches",
          M.is_individual_registrant("Kennan, Stephanie", "STEPHANIE KENNAN"))
    check("self-filing org AARP is not an individual",
          not M.is_individual_registrant("AARP", "AARP"))
    check("corporation equal to its own name is not an individual",
          not M.is_individual_registrant("AVERY DENNISON CORPORATION", "AVERY DENNISON CORPORATION"))
    check("registrant name alone, without a matching lobbyist, is not enough",
          not M.is_individual_registrant("STEPHANIE KENNAN", None))
    check("client-name fallback must not be used: Boards vs Jane Boards",
          not M.is_individual_registrant("FEDERATION OF STATE MEDICAL BOARDS", "JANE BOARDS"))
    check("O'Brien looks like a person", M.looks_like_person_name("KERRY O'BRIEN"))


def test_last_name_suffixes():
    from connections_build import last_name
    print("last_name suffixes")
    check("Pallone, Jr. -> Pallone", last_name("Frank Pallone, Jr.") == "Pallone")
    check("Pallone Jr. -> Pallone", last_name("Frank Pallone Jr.") == "Pallone")
    check("Timmons IV -> Timmons", last_name("William Timmons IV") == "Timmons")
    check("Warren unchanged", last_name("Elizabeth Warren") == "Warren")


def test_same_name_former_members():
    print("same-name former members")
    # Current House Rob/Robert Menendez Jr. (NJ, 2023-), vs former Sen. Bob Menendez (NJ, Senate)
    son = mem(bioguide="M001226", official="Robert Menendez", first="Robert", last="Menendez",
              firsts=("robert", "rob", "bob"), chambers=frozenset({"rep"}), gender="M",
              states=frozenset({"NJ"}), term_years=((2023, 2027, "rep", "NJ"),),
              first_last_collisions=((frozenset({"NJ"}), frozenset({"rep", "sen"}),
                                      ((1993, 2006, "rep", "NJ"), (2006, 2024, "sen", "NJ")), "M000639"),))
    hits = M.find_position_hits("Intern, Office of Senator Robert Menendez (D-NJ)", son)
    check("Senator Robert Menendez is not published on the House member",
          not any(h.decision == "publish" for h in hits), [(h.decision, h.reason, h.kind) for h in hits])
    hits = M.find_position_hits("September 2007 - September 2013, State Director to U.S. Senator Robert Menendez", son)
    check("2007-2013 Senator Menendez years are rejected for the House member",
          any(h.decision == "reject" for h in hits) and not any(h.decision == "publish" for h in hits),
          [(h.decision, h.reason) for h in hits])

    al = mem(bioguide="R000575", official="Mike Rogers", first="Mike", last="Rogers",
             firsts=("mike", "michael"), chambers=frozenset({"rep"}), gender="M",
             states=frozenset({"AL"}), term_years=((2003, 2027, "rep", "AL"),),
             first_last_collisions=((frozenset({"MI"}), frozenset({"rep"}),
                                     ((2001, 2015, "rep", "MI"),), "R000572"),))
    hits = M.find_position_hits("Chief of Staff, Rep. Mike Rogers (R-MI)", al)
    check("Rep. Mike Rogers (R-MI) is not published on Mike Rogers (AL)",
          not any(h.decision == "publish" for h in hits), [(h.decision, h.reason) for h in hits])
    hits = M.find_position_hits("Legislative Assistant, Rep. Mike Rogers", al)
    check("Rep. Mike Rogers without a state goes to review when a namesake exists",
          any(h.decision == "review" for h in hits) and not any(h.decision == "publish" for h in hits),
          [(h.decision, h.reason) for h in hits])

    md = mem(bioguide="H001052", official="Andy Harris", first="Andy", last="Harris",
             firsts=("andy", "andrew"), chambers=frozenset({"rep"}), gender="M",
             states=frozenset({"MD"}), term_years=((2011, 2027, "rep", "MD"),))
    hits = M.find_position_hits("Intern, Representative Andy Harris (R-MO) May 2019-July 2019", md)
    check("Andy Harris (R-MO) is rejected for the Maryland member",
          any(h.decision == "reject" for h in hits) and not any(h.decision == "publish" for h in hits),
          [(h.decision, h.reason) for h in hits])
    hits = M.find_position_hits("Intern, Representative Andy Harris (R-MD-01) May 2019 - July 2019", md)
    check("Andy Harris (R-MD-01) still publishes",
          any(h.decision == "publish" for h in hits), [(h.decision, h.reason) for h in hits])

    # Jack Reed (RI, Senate) vs historic House John Reeds: unique Senate title can publish
    reed = mem(bioguide="R000122", official="John F. Reed", first="John", last="Reed",
               firsts=("john", "jack"), chambers=frozenset({"sen", "rep"}), gender="M",
               states=frozenset({"RI"}), term_years=((1991, 1997, "rep", "RI"), (1997, 2027, "sen", "RI")),
               first_last_collisions=((frozenset({"MA"}), frozenset({"rep"}),
                                       ((1813, 1817, "rep", "MA"),), "R000120"),))
    hits = M.find_position_hits("Legislative Assistant, Senator Jack Reed", reed)
    check("Senator Jack Reed publishes for the Rhode Island senator",
          any(h.decision == "publish" for h in hits), [(h.decision, h.reason, h.kind, h.matched) for h in hits])

    # John Kennedy (LA) vs JFK (also a senator): no state or years -> review, not publish
    ken = mem(bioguide="K000393", official="John Neely Kennedy", first="John", last="Kennedy",
              firsts=("john",), chambers=frozenset({"sen"}), gender="M",
              states=frozenset({"LA"}), term_years=((2017, 2029, "sen", "LA"),),
              first_last_collisions=((frozenset({"MA"}), frozenset({"sen", "rep", "prez"}),
                                      ((1947, 1953, "rep", "MA"), (1953, 1961, "sen", "MA")), "K000107"),))
    hits = M.find_position_hits("Intern, Office of Senator John Kennedy", ken)
    check("undated Senator John Kennedy without a state goes to review",
          any(h.decision == "review" for h in hits) and not any(h.decision == "publish" for h in hits),
          [(h.decision, h.reason, h.kind) for h in hits])
    hits = M.find_position_hits("Legislative Correspondent, Senator John Kennedy (LA)", ken)
    check("Senator John Kennedy (LA) publishes",
          any(h.decision == "publish" for h in hits), [(h.decision, h.reason) for h in hits])


def test_individual_middle_initial_and_nickname():
    print("individual registrant name variants")
    check("Michael R. Pawlowski matches lobbyist Michael Pawlowski",
          M.is_individual_registrant("MICHAEL R. PAWLOWSKI", "MICHAEL PAWLOWSKI"))
    check("Kim Krenik matches lobbyist Kimberly Krenik",
          M.is_individual_registrant("KIM KRENIK", "KIMBERLY KRENIK"))
    check("Mark Hastings looks like a person", M.looks_like_person_name("MARK HASTINGS"))

    check("Biotechnology Innovation Organization is not a person", not M.looks_like_person_name("BIOTECHNOLOGY INNOVATION ORGANIZATION"))
    check("LPL Financial is not a person", not M.looks_like_person_name("LPL FINANCIAL"))
    check("Common Cause is not a person", not M.looks_like_person_name("COMMON CAUSE"))
    check("Public Citizen is not a person", not M.looks_like_person_name("PUBLIC CITIZEN"))

    check("City of Dallas is not a person", not M.looks_like_person_name("CITY OF DALLAS"))
    check("CVS Health is not a person", not M.looks_like_person_name("CVS HEALTH"))
    check("Business Roundtable is not a person", not M.looks_like_person_name("BUSINESS ROUNDTABLE"))

if __name__ == "__main__":
    test_wrong_member_title_surname()
    test_bill_parse_and_corroboration()
    test_ie_dedupe_tuple()
    test_individual_registrant_label()
    test_last_name_suffixes()
    test_same_name_former_members()
    test_individual_middle_initial_and_nickname()
    print()
    if failures:
        print("FAILED", len(failures), "checks:", failures)
        sys.exit(1)
    print("All match-validation checks passed.")
