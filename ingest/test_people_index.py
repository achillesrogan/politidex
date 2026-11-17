"""Synthetic donors only. No real FEC names."""
import json
import sys
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
    weak = P.build_index([row("SMITH, ALEX", 5_000_000, employer="")], "2026-11-17T02:30:00+00:00")
    check("a blank employer is not published", weak["published"] == [])
    check("the blank employer is flagged for review", weak["unlinked"] and "missing" in weak["unlinked"][0]["clusters"][0]["reason"])


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
        row("DOE, JANE QUINN", 600_000, tran_id="SA1"),
        row("DOE, JANE QUINN", 600_000, tran_id="SA1", sub_id="9"),
    ], "2026-11-17T02:30:00+00:00")
    check("the same transaction id is counted once", dup["published"] == [])
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
    test_parser_drops_zip_and_scope_is_empty()
    if failures:
        print("FAILED", len(failures))
        sys.exit(1)
    print("ok")
