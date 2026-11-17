"""Synthetic donors only. No real FEC names."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import people_index as P

failures = []


def check(label, ok, detail=""):
    print(("  ok  " if ok else " FAIL ") + label + ((" — " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(label)


def row(name, amount, **over):
    base = {
        "committee_id": "C00000001",
        "image": "202601019900000001",
        "txn_type": "15",
        "entity": "IND",
        "name": name,
        "city": "SPRINGFIELD",
        "state": "IL",
        "employer": "EXAMPLE SCHOOL",
        "occupation": "TEACHER",
        "date": "2026-03-01",
        "amount_cents": amount,
        "tran_id": "",
        "memo": "",
        "sub_id": "1",
    }
    base.update(over)
    return base


def test_threshold_and_aggregation():
    print("threshold")
    under = P.build_index([row("DOE, JANE QUINN", 600_000), row("DOE, JANE QUINN", 399_999, sub_id="2")], "2026-11-17T02:30:00+00:00")
    check("9999.99 is not published", under["published"] == [] and under["below_threshold_rows"] == 2)
    exact = P.build_index([
        row("DOE, JANE QUINN", 600_000),
        row("DOE, JANE QUINN", 400_000, sub_id="2", date="2026-04-02"),
    ], "2026-11-17T02:30:00+00:00")
    check("10000.00 is published once", len(exact["published"]) == 1 and exact["published"][0]["amount"] == "10000.00")
    check("two gifts stay on the person", len(exact["published"][0]["contributions"]) == 2)
    refund = P.build_index([
        row("DOE, JANE QUINN", 1_200_000),
        row("DOE, JANE QUINN", -300_000, sub_id="2", txn_type="22Y"),
    ], "2026-11-17T02:30:00+00:00")
    check("a refund can drop the person below the threshold", refund["published"] == [])
    positive_refund = P.build_index([
        row("DOE, JANE QUINN", 1_200_000),
        row("DOE, JANE QUINN", 300_000, sub_id="2", txn_type="22Y"),
    ], "2026-11-17T02:30:00+00:00")
    check("a positive 22Y refund is subtracted", positive_refund["published"] == [])
    earmark = P.build_index([
        row("DOE, JANE QUINN", 600_000, txn_type="15E"),
        row("DOE, JANE QUINN", 600_000, sub_id="2", txn_type="24T"),
    ], "2026-11-17T02:30:00+00:00")
    check("an earmark is not also counted as the conduit forwarding", earmark["published"] == [])
    conduit = P.build_index([
        row("DOE, JANE QUINN", 1_000_000, txn_type="15E"),
        row("DOE, JANE QUINN", 1_000_000, sub_id="2", txn_type="15T"),
        row("DOE, JANE QUINN", 1_000_000, sub_id="3", txn_type="15I"),
    ], "2026-11-17T02:30:00+00:00")
    check("15E is kept and 15I/15T are not added again", len(conduit["published"]) == 1 and conduit["published"][0]["amount"] == "10000.00")
    counted = P.build_index([row("DOE, JANE QUINN", 1_000_000, txn_type="10")], "2026-11-17T02:30:00+00:00")
    check("transaction type 10 is counted", len(counted["published"]) == 1 and counted["published"][0]["amount"] == "10000.00")
    memo = P.build_index([row("DOE, JANE QUINN", 1_000_000, txn_type="10J")], "2026-11-17T02:30:00+00:00")
    check("joint-fundraising memo type 10J is not a second gift", memo["published"] == [])
    national = P.build_index([
        row("DOE, JANE QUINN", 1_200_000),
        row("DOE, JANE QUINN", 400_000, sub_id="2", txn_type="40Y"),
    ], "2026-11-17T02:30:00+00:00")
    check("a 40Y refund is subtracted", national["published"] == [])
    missed = P.build_index([
        row("DOE, JOHN Q", 1_500_000),
        row("DOE, JOHN Q", 900_000, sub_id="2", txn_type="22Y", employer="", occupation=""),
    ], "2026-11-17T02:30:00+00:00")
    check("a 15000 gift plus a 9000 refund with blank work fields is not published at 15000", missed["published"] == [])
    ambiguous = P.build_index([
        row("DOE, JOHN Q", 1_200_000, employer="EXAMPLE SCHOOL"),
        row("DOE, JOHN Q", 1_500_000, sub_id="2", employer="OTHER SCHOOL"),
        row("DOE, JOHN Q", 300_000, sub_id="3", txn_type="22Y", employer="", occupation=""),
    ], "2026-11-17T02:30:00+00:00")
    check("an ambiguous refund publishes neither cluster", ambiguous["published"] == [])
    check("that refund is sent to review", any("refund did not match" in item["reason"].lower() for item in ambiguous["unlinked"]))
    bare_name = P.build_index([
        row("DOE, JOHN Q", 1_500_000),
        row("DOE, JOHN", 900_000, sub_id="2", txn_type="22Y", employer="", occupation=""),
    ], "2026-11-17T02:30:00+00:00")
    check("a refund to DOE, JOHN against DOE, JOHN Q is not published at 15000", bare_name["published"] == [])
    check("the unmatched middle-name gift is on the review list", any(item["name"] == "DOE, JOHN" for item in bare_name["unlinked"]))
    middle_refund = P.build_index([
        row("DOE, JOHN Q", 2_000_000),
        row("DOE, JOHN Q", 500_000, sub_id="2", txn_type="22Y", employer="", occupation=""),
    ], "2026-11-17T02:30:00+00:00")
    check("a refund with the same middle name is subtracted", len(middle_refund["published"]) == 1 and middle_refund["published"][0]["amount"] == "15000.00")


def test_same_name_is_not_linked():
    print("disambiguation")
    rows = [
        row("DOE, JANE QUINN", 1_200_000),
        row("DOE, JANE MARIE", 1_200_000, sub_id="2"),
        row("DOE, JANE QUINN", 1_200_000, sub_id="3", city="CHICAGO"),
        row("DOE, JANE QUINN", 1_200_000, sub_id="4", employer="OTHER SCHOOL"),
    ]
    built = P.build_index(rows, "2026-11-17T02:30:00+00:00")
    check("four substantiated clusters stay separate", len(built["published"]) == 4)
    check("the shared first and last name is in the review list", any(item["name"] == "DOE, JANE" for item in built["unlinked"]))
    weak = P.build_index([
        row("SMITH, ALEX", 5_000_000, employer=""),
        row("SMITH, ALEX", 5_000_000, sub_id="2", employer="", city="CHICAGO"),
    ], "2026-11-17T02:30:00+00:00")
    check("a blank employer is not published", weak["published"] == [])
    check("the blank employer is flagged for review", weak["unlinked"] and "missing" in weak["unlinked"][0]["clusters"][0]["reason"])
    suffixes = P.build_index([
        row("SMITH, JOHN JR", 1_200_000),
        row("SMITH, JOHN SR", 1_200_000, sub_id="2"),
    ], "2026-11-17T02:30:00+00:00")
    check("JR and SR stay different people", len(suffixes["published"]) == 2)
    check("the suffix is part of the published name", {person["name"] for person in suffixes["published"]} == {"SMITH, JOHN JR", "SMITH, JOHN SR"})
    retired = P.build_index([
        row("DOE, JANE", 1_200_000, employer="RETIRED", occupation="RETIRED"),
        row("DOE, JANE", 1_200_000, sub_id="2", employer="NOT EMPLOYED", occupation="N/A"),
    ], "2026-11-17T02:30:00+00:00")
    check("generic employment does not merge two people", retired["published"] == [])
    small = P.build_index([
        row("DOE, JANE QUINN", 100, city="CHICAGO"),
        row("DOE, JANE QUINN", 100, sub_id="2"),
    ], "2026-11-17T02:30:00+00:00")
    check("clusters under 10000 are not in the review list", small["unlinked"] == [])
    split = P.build_index([
        row("DOE, JANE QUINN JR", 1_200_000, city="SPRINGFIELD", state="IL", employer="EXAMPLE SCHOOL", occupation="TEACHER"),
        row("DOE, JANE MARIE", 1_200_000, sub_id="2", city="CHICAGO", state="IL", employer="OTHER SCHOOL", occupation="NURSE"),
    ], "2026-11-17T02:30:00+00:00")
    review = next(item for item in split["unlinked"] if item["name"] == "DOE, JANE")
    by_city = {cluster["city"]: cluster for cluster in review["clusters"]}
    check("review city is the city field", by_city["SPRINGFIELD"]["city"] == "SPRINGFIELD" and by_city["CHICAGO"]["state"] == "IL")
    check("review suffix middle employer and occupation use the identity fields",
          by_city["SPRINGFIELD"]["suffix"] == "JR" and by_city["SPRINGFIELD"]["middle"] == "QUINN"
          and by_city["SPRINGFIELD"]["employer"] == "EXAMPLE SCHOOL" and by_city["SPRINGFIELD"]["occupation"] == "TEACHER"
          and by_city["CHICAGO"]["employer"] == "OTHER SCHOOL" and by_city["CHICAGO"]["occupation"] == "NURSE")
    generic = P.build_index([
        row("DOE, JANE QUINN", 600_000, employer="RETIRED", occupation="RETIRED"),
        row("DOE, JANE QUINN", 600_000, sub_id="2", employer="NONE", occupation="N/A"),
    ], "2026-11-17T02:30:00+00:00")
    check("a shared middle name and city do not merge without a real work field", generic["published"] == [])
    alone = P.build_index([
        row("DOE, JANE QUINN", 1_200_000, employer="RETIRED", occupation="N/A"),
    ], "2026-11-17T02:30:00+00:00")
    check("one weak cluster at 10000 is on the review list", alone["published"] == [] and len(alone["unlinked"]) == 1 and alone["unlinked"][0]["clusters"][0]["city"] == "SPRINGFIELD")
    parts = P.build_index([
        row("DOE, JANE QUINN", 600_000, employer="RETIRED", occupation="N/A"),
        row("DOE, JANE QUINN", 600_000, sub_id="2", employer="NONE", occupation="RETIRED"),
    ], "2026-11-17T02:30:00+00:00")
    check("weak rows that sum to 10000 are one review cluster", parts["published"] == [] and parts["unlinked"] and parts["unlinked"][0]["clusters"][0]["rows"] == 2 and parts["unlinked"][0]["clusters"][0]["amount"] == "12000.00")


def test_address_and_memo_and_duplicates():
    print("stripping")
    dirty = row("DOE, JANE QUINN", 1_000_000)
    dirty["zip"] = "64108"
    dirty["street"] = "2501 MAIN STREET"
    built = P.build_index([dirty], "2026-11-17T02:30:00+00:00")
    blob = json.dumps(built["published"])
    check("ZIP is not published", "64108" not in blob)
    check("street is not published", "2501" not in blob and "MAIN STREET" not in blob)
    memo = P.build_index([
        row("DOE, JANE QUINN", 1_000_000, memo="X"),
        row("DOE, JANE QUINN", 100, sub_id="2"),
    ], "2026-11-17T02:30:00+00:00")
    check("memo code X is not counted toward the threshold", memo["published"] == [])
    dup = P.build_index([
        row("DOE, JANE QUINN", 600_000, tran_id="SA1", file_num="1", amend="N"),
        row("DOE, JANE QUINN", 1_000_000, tran_id="SA1", sub_id="9", file_num="2", amend="A"),
    ], "2026-11-17T02:30:00+00:00")
    check("the later filing replaces the earlier one", len(dup["published"]) == 1 and dup["published"][0]["amount"] == "10000.00")
    bare = P.build_index([
        row("DOE, JANE QUINN", 600_000, tran_id="", sub_id="77", file_num="1", amend="N"),
        row("DOE, JANE QUINN", 1_000_000, tran_id="", sub_id="77", file_num="2", amend="A"),
    ], "2026-11-17T02:30:00+00:00")
    check("rows without a transaction id dedupe on sub_id", len(bare["published"]) == 1 and bare["published"][0]["amount"] == "10000.00")
    reused = P.build_index([
        row("DOE, JANE QUINN", 600_000, tran_id="SA1", image="202601019900000001", date="2026-03-01", sub_id="1"),
        row("DOE, JANE QUINN", 600_000, tran_id="SA1", image="202601019900000002", date="2026-04-02", sub_id="2"),
    ], "2026-11-17T02:30:00+00:00")
    check("the same transaction id on another date is kept", len(reused["published"]) == 1 and reused["published"][0]["amount"] == "12000.00")
    amended = P.build_index([
        row("DOE, JANE QUINN", 1_500_000, tran_id="SA9", image="202601019900000001", file_num="1", amend="N"),
        row("DOE, JANE QUINN", 1_500_000, tran_id="SA9", image="202601019900000099", sub_id="9", file_num="2", amend="A"),
    ], "2026-11-17T02:30:00+00:00")
    check("an amendment with a new image is not counted twice", len(amended["published"]) == 1 and amended["published"][0]["amount"] == "15000.00")
    spaced = P.build_index([
        row("DOE, JOHN Q", 1_500_000, tran_id="SA3", file_num="1", amend="N"),
        row("DOE,JOHN Q", 1_500_000, tran_id="SA3", sub_id="2", file_num="2", amend="A"),
        row("DOE , JOHN Q", 1_500_000, tran_id="SA3", sub_id="3", file_num="3", amend="A"),
    ], "2026-11-17T02:30:00+00:00")
    check("spacing around the comma does not publish the amendment twice", len(spaced["published"]) == 1 and spaced["published"][0]["amount"] == "15000.00")
    corrected = P.build_index([
        row("DOE, JANE QUINN", 1_500_000, tran_id="SA4", date="2026-03-01", file_num="1", amend="N"),
        row("DOE, JANE QUINN", 1_500_000, tran_id="SA4", date="2026-04-02", sub_id="2", file_num="2", amend="A"),
    ], "2026-11-17T02:30:00+00:00")
    check("a date-correcting amendment replaces the earlier row", len(corrected["published"]) == 1 and corrected["published"][0]["amount"] == "15000.00")
    titled = P.parse_person_name("DOE, JOHN Q MR")
    comma = P.parse_person_name("DOE, JOHN Q,")
    check("a title and a stray comma are not part of the middle name", titled["middle"] == "Q" and comma["middle"] == "Q")
    unnamed = P.build_index([
        row("DOE, JANE QUINN", 1_500_000),
        row("NOT A PERSON", 500_000, sub_id="2", txn_type="22Y"),
    ], "2026-11-17T02:30:00+00:00")
    check("a refund whose name cannot be parsed is reviewed", len(unnamed["published"]) == 1 and any(item["name"] == "NOT A PERSON" for item in unnamed["unlinked"]))
    spouses = P.build_index([
        row("DOE, JOHN", 600_000),
        row("DOE, MRS JOHN", 600_000, sub_id="2"),
    ], "2026-11-17T02:30:00+00:00")
    check("MRS JOHN is not merged into JOHN", spouses["published"] == [])
    check("MS stays on the name", P.parse_person_name("DOE, JOHN MS")["middle"] == "MS")
    check("MR after the first name is not part of the middle name", P.parse_person_name("DOE, JOHN Q MR")["middle"] == "Q")
    check("a trailing HON stays on the name", P.parse_person_name("DOE, JOHN HON")["middle"] == "HON")
    reversed_name = P.build_index([
        row("DOE, JOHN Q", 1_500_000),
        row("JOHN Q DOE", 900_000, sub_id="2", txn_type="22Y"),
    ], "2026-11-17T02:30:00+00:00")
    check("an unparsed refund that names the donor is not left published", reversed_name["published"] == [])
    for refund_name in ("J DOE", "JOHN/DOE", "JOHN DOE-SMITH", "DOE,", "JOHNDOE"):
        held = P.build_index([
            row("DOE, JOHN Q", 1_500_000),
            row(refund_name, 900_000, sub_id="2", txn_type="22Y"),
        ], "2026-11-17T02:30:00+00:00")
        check(
            "refund %s does not publish DOE, JOHN Q" % refund_name,
            held["published"] == [] and any(item["name"] == "DOE, JOHN" for item in held["unlinked"]),
        )
    surname_only = P.build_index([
        row("DOE, JOHN Q", 1_500_000),
        row("DOE, JANE QUINN", 1_500_000, sub_id="2", employer="OTHER SCHOOL"),
        row("DOE,", 900_000, sub_id="3", txn_type="22Y"),
    ], "2026-11-17T02:30:00+00:00")
    check("a last-name-only refund holds every DOE cluster", surname_only["published"] == [])
    blank_refund = P.build_index([
        row("DOE, JOHN Q", 1_500_000),
        row("   ", 900_000, sub_id="2", txn_type="22Y"),
    ], "2026-11-17T02:30:00+00:00")
    check(
        "a blank refund name stays in review",
        len(blank_refund["published"]) == 1 and blank_refund["published"][0]["amount"] == "15000.00",
    )

    def held(donor, refund_name):
        built = P.build_index([
            row(donor, 1_500_000),
            row(refund_name, 900_000, sub_id="2", txn_type="22Y"),
        ], "2026-11-17T02:30:00+00:00")
        return built["published"] == []

    check("JOHN SMITH-DOE holds SMITH-DOE, JOHN", held("SMITH-DOE, JOHN", "JOHN SMITH-DOE"))
    check("J SMITHDOE holds SMITH-DOE, JOHN", held("SMITH-DOE, JOHN", "J SMITHDOE"))
    check("PATRICK O'BRIEN holds O'BRIEN, PATRICK", held("O'BRIEN, PATRICK", "PATRICK O'BRIEN"))
    check("P OBRIEN holds O'BRIEN, PATRICK", held("O'BRIEN, PATRICK", "P OBRIEN"))
    check("MARIA DE LA CRUZ holds DE LA CRUZ, MARIA", held("DE LA CRUZ, MARIA", "MARIA DE LA CRUZ"))
    check("JOHN DOE JR holds DOE JR, JOHN", held("DOE JR, JOHN", "JOHN DOE JR"))
    check("JOSE MUNOZ holds MUÑOZ, JOSE", held("MUÑOZ, JOSE", "JOSE MUNOZ"))
    check("JOSÉ MUÑOZ holds MUÑOZ, JOSÉ", held("MUÑOZ, JOSÉ", "JOSÉ MUÑOZ"))
    check("JOHN DOË holds DOE, JOHN Q", held("DOE, JOHN Q", "JOHN DOË"))
    for refund_name in ("MR DOE", "MRS DOE", "MR. & MRS. DOE", "DOE JR", "Q DOE", "JQ DOE", "DOE FAMILY", "THE DOE TRUST"):
        check("refund %s holds DOE, JOHN Q" % refund_name, held("DOE, JOHN Q", refund_name))
    late = P.build_index([
        row("DOE, JANE QUINN", 1_500_000, tran_id="SA5", date="2026-04-02", file_num="2", amend="N"),
        row("DOE, JANE QUINN", 1_500_000, tran_id="SA5", date="2026-03-01", sub_id="2", file_num="1", amend="A"),
    ], "2026-11-17T02:30:00+00:00")
    check("a lower file number amendment does not stay as a second row", len(late["published"]) == 1 and late["published"][0]["amount"] == "15000.00")
    closest = P.build_index([
        row("DOE, JANE QUINN", 1_000_000, tran_id="SA6", date="2026-03-01", file_num="1", amend="N"),
        row("DOE, JANE QUINN", 2_000_000, tran_id="SA6", date="2026-06-01", sub_id="2", file_num="2", amend="N"),
        row("DOE, JANE QUINN", 1_200_000, tran_id="SA6", date="2026-04-01", sub_id="3", file_num="4", amend="A"),
    ], "2026-11-17T02:30:00+00:00")
    gifts = {item["amount"] for item in closest["published"][0]["contributions"]} if closest["published"] else set()
    check("an amendment replaces the closest-dated original", gifts == {"20000.00", "12000.00"}, str(gifts))
    check("the notice is on the result", P.NOTICE in built["notice"] and "30111" in built["notice"])


def test_rebuild_and_links():
    print("rebuild")
    rows = [row("DOE, JANE QUINN", 1_000_000)]
    built = P.build_index(rows, "2026-11-17T02:30:00+00:00")
    check("rebuild matches", P.verify_index(rows, built["published"], "2026-11-17T02:30:00+00:00"))
    changed = [row("DOE, JANE QUINN", 100)]
    check("a smaller rebuild does not still verify", not P.verify_index(changed, built["published"], "2026-11-17T02:30:00+00:00"))
    gift = built["published"][0]["contributions"][0]
    check("gift and identity each have a source", gift["source"]["source_url"].startswith("https://") and built["published"][0]["identity_source"]["excerpt"])
    ok = P.business_website("EXAMPLE SCHOOL", "https://example.school/about", {
        "method": "company_domain",
        "host": "example.school",
        "source": {"source_name": "Example School", "source_url": "https://example.school/about", "retrieved_at": "2026-11-17T02:30:00+00:00", "excerpt": "Example School official site."},
    })
    bad = P.business_website("EXAMPLE SCHOOL", "https://not-example.test/", {
        "method": "company_domain",
        "host": "example.school",
        "source": {"source_name": "Example School", "source_url": "https://example.school/about", "retrieved_at": "2026-11-17T02:30:00+00:00", "excerpt": "Example School official site."},
    })
    check("a verified company domain links", ok and ok["url"].startswith("https://example.school/"))
    check("a different host does not link", bad is None)
    officer = {
        "name": "DOE, JANE QUINN", "role": "treasurer", "city": "SPRINGFIELD", "state": "IL",
        "employer": "EXAMPLE SCHOOL", "occupation": "TEACHER",
        "source": {"source_name": "Federal Election Commission", "source_url": "https://www.fec.gov/data/committee/C00000001/", "retrieved_at": "2026-11-17T02:30:00+00:00", "excerpt": "Form 1 names Jane Quinn Doe as treasurer."},
    }
    linked = P.link_officer_donations(officer, rows, "2026-11-17T02:30:00+00:00")
    other_city = P.link_officer_donations(officer, [row("DOE, JANE QUINN", 1_000_000, city="CHICAGO")], "2026-11-17T02:30:00+00:00")
    check("an official treasurer links to the matching gifts", linked["linked"] and linked["officer_source"]["source_url"])
    check("the same name in another city does not link", other_city["linked"] is False)
    nameless = dict(officer)
    nameless["role"] = "friend"
    check("a role the source does not list as an office is dropped", P.link_officer_donations(nameless, rows, "2026-11-17T02:30:00+00:00") is None)


def _wide_name(i):
    """Eight letters, each starting with Q, so one refund cannot contain two of them."""
    chars = ["Q"]
    n = i
    for _ in range(7):
        chars.append(chr(ord("A") + (n % 26)))
        n //= 26
    return "".join(chars)


def test_refund_check_is_fast():
    print("speed")
    rows = []
    for i in range(60_000):
        rows.append(row(
            "%s, FIRST" % _wide_name(i),
            1_500_000,
            sub_id=str(i + 1),
            tran_id="T%06d" % i,
            city="CITY%03d" % (i % 200),
            employer="EMPLOYER %d" % (i % 40),
        ))
    for j in range(1_000):
        rows.append(row("NN %s" % _wide_name(j), 100_000, sub_id="p%d" % j, txn_type="22Y"))
    for j in range(1_000):
        rows.append(row("Z%s" % _wide_name(1_000 + j), 100_000, sub_id="j%d" % j, txn_type="22Y"))
    clusters = 60_000
    refunds = 2_000
    calls = {"n": 0}
    original = P._name_pieces

    def counted(raw):
        calls["n"] += 1
        return original(raw)

    # Both the indexed check and the old per-cluster check call _name_pieces.
    P._name_pieces = counted
    try:
        started = time.perf_counter()
        built = P.build_index(rows, "2026-11-17T18:40:00+00:00")
        elapsed = time.perf_counter() - started
    finally:
        P._name_pieces = original
    # The indexed check is about one call per cluster last name plus one per refund.
    # Checking every cluster calls it twice per pair, about 240 million times here.
    limit = 2 * (clusters + refunds)
    check(
        "name-piece calls stay under twice the clusters plus the refunds",
        calls["n"] < limit,
        "%d calls, limit %d" % (calls["n"], limit),
    )
    if os.environ.get("POLITIDEX_REFUND_TIMING"):
        check("60k clusters and 2k refunds finish in under 10 seconds (%.2fs)" % elapsed, elapsed < 10)
    check("those refunds hold only the last names they name", len(built["published"]) == 58_000, str(len(built["published"])))


def test_parser_drops_zip_and_scope_is_empty():
    print("parser")
    line = "|".join([
        "C00000001", "N", "M2", "P2026", "202601019900000001", "15", "IND",
        "DOE, JANE QUINN", "SPRINGFIELD", "IL", "SENTINEL_ZIP_64108",
        "EXAMPLE SCHOOL", "TEACHER", "03012026", "10000.00", "", "SA1", "100", "", "", "99",
    ])
    parsed = P.parse_indiv_line(line)
    blob = json.dumps(parsed)
    check("parser reads the person and the amount", parsed["amount_cents"] == 1_000_000 and parsed["city"] == "SPRINGFIELD")
    check("parser does not keep the ZIP", "64108" not in blob and "SENTINEL_ZIP" not in blob)
    scope = P.scope_report()
    check("no real person is in the scope report", scope["published_people"] == [] and scope["status"] == "not_run")
    check("scope names the file size", scope["indiv_zip_bytes"] == 2602361290)


if __name__ == "__main__":
    test_threshold_and_aggregation()
    test_same_name_is_not_linked()
    test_address_and_memo_and_duplicates()
    test_rebuild_and_links()
    test_refund_check_is_fast()
    test_parser_drops_zip_and_scope_is_empty()
    if failures:
        print("FAILED", len(failures))
        sys.exit(1)
    print("ok")
