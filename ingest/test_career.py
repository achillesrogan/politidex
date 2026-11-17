"""Career ingest stays offline. No network and no API key."""
import json
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import career_congress as C
import career_fec as F

failures = []


def check(label, ok, detail=""):
    print(("  ok  " if ok else " FAIL ") + label + ((" — " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(label)


def test_fec_urls():
    print("fec")
    check("1980 committee master stays on fec.gov", F.bulk_url(1980, "cm") == "https://www.fec.gov/files/bulk-downloads/1980/cm80.zip")
    check("1980 pac summary stays on fec.gov", F.bulk_url(1980, "webk").endswith("/webk80.zip"))
    check("1980 committee-to-candidate file stays on fec.gov", F.bulk_url(2026, "pas2").endswith("/pas226.zip"))
    refused = False
    try:
        F.bulk_url(1980, "indiv")
    except ValueError:
        refused = True
    check("an individual contribution file is refused", refused)
    check("fec.gov is allowlisted", F.host_allowed("www.fec.gov", False))
    check("the government bucket is allowlisted only after a redirect", F.host_allowed("files.s3-us-gov-west-1.amazonaws.com", True) and not F.host_allowed("files.s3-us-gov-west-1.amazonaws.com", False))
    check("another host is refused", not F.host_allowed("example.com", True))
    fields = ["C00000001", "N", "", "", "", "24K", "PAC", "EXAMPLE PAC", "CITY", "IL", "62701", "", "", "03011980", "500.00", "", "H0IL00000", "", "", "", "", "1"]
    row = F.pas2_candidate("|".join(fields))
    check("a committee-to-candidate row keeps the candidate id", row["candidate_id"] == "H0IL00000" and row["committee_id"] == "C00000001" and row["amount"] == "500.00")
    check("a committee-to-candidate row drops the ZIP", "62701" not in json.dumps(row) and "CITY" not in json.dumps(row))


def test_congress_script():
    print("congress")
    check("the bill link uses that congress", C.public_bill_url(101, "HR", "7") == "https://www.congress.gov/bill/101st-congress/house-bill/7")
    check("119 keeps the th suffix", C.public_bill_url(119, "S", 12).endswith("/119th-congress/senate-bill/12"))
    check("a key is not placed in the URL", "api_key" not in C.request_url("/member/A000001?format=json"))
    refused = False
    try:
        C.request_url("/member/A000001?api_key=secret")
    except SystemExit:
        refused = True
    check("a path that already contains a key is refused", refused)
    limit = C.HourLimit(5000)
    check("five thousand requests take at least an hour", abs(limit.interval - 0.72) < 1e-9 and limit.wait(0) == 0)
    gap = limit.wait(0)
    check("the next request waits out the interval", abs(gap - 0.72) < 1e-9)
    cleaned = C.scrub({"api_key": "secret", "url": "https://api.congress.gov/v3/member/A000001?api_key=secret", "ok": True})
    check("the key is removed from saved JSON", "secret" not in json.dumps(cleaned) and cleaned["ok"] is True)

    class Response:
        def read(self):
            return b'{"member":{"terms":[{"startYear":1975,"chamber":"House of Representatives"}]}}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    seen = {}

    def opener(req, timeout=40):
        seen["url"] = req.full_url
        seen["header"] = req.get_header("X-api-key")
        seen["timeout"] = timeout
        return Response()

    data = C.fetch_json("/member/A000001?format=json", "secret-value", opener)
    check("the key travels only in the header", seen["url"].startswith("https://api.congress.gov/v3/member/A000001") and "secret-value" not in seen["url"] and seen["header"] == "secret-value")
    check("the member term year is kept", data["member"]["terms"][0]["startYear"] == 1975)
    text = Path(C.__file__).read_text()
    check("the script does not fall back to a demo key", "DEMO_KEY" not in text and "api_key(" not in text)
    hits = {"stolen": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/stolen":
                hits["stolen"] += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"stolen")
                return
            self.send_response(302)
            self.send_header("Location", "/stolen")
            self.end_headers()

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    refused = False
    try:
        C.no_redirect_opener().open(
            urllib.request.Request("http://127.0.0.1:%d/start" % port, headers={"X-Api-Key": "secret-value"}),
            timeout=5,
        )
    except SystemExit as exc:
        refused = "not forwarded" in str(exc)
    finally:
        server.shutdown()
    check("a redirect is refused before the key header is forwarded", refused and hits["stolen"] == 0)
    check("the script does not call plain urlopen", "urlopen" not in text)


def test_default_openers_do_not_forward_the_key():
    """one_member and fetch_json, with no opener argument, must refuse a redirect."""
    print("default opener")
    hits = {"stolen": 0, "key_on_stolen": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/stolen":
                hits["stolen"] += 1
                hits["key_on_stolen"].append(self.headers.get("X-Api-Key"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"stolen")
                return
            self.send_response(302)
            self.send_header("Location", "/stolen")
            self.end_headers()

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    old_base = C.BASE
    C.BASE = "http://127.0.0.1:%d" % port

    class NoWait:
        def wait(self, _now):
            return 0

    refused_fetch = False
    refused_member = False
    try:
        try:
            C.fetch_json("/start", "secret-value")
        except SystemExit as exc:
            refused_fetch = "not forwarded" in str(exc)
        except Exception:
            refused_fetch = False
        try:
            C.one_member("A000001", "secret-value", NoWait(), sleep=lambda _delay: None)
        except SystemExit as exc:
            refused_member = "not forwarded" in str(exc)
        except Exception:
            refused_member = False
    finally:
        C.BASE = old_base
        server.shutdown()
    check("fetch_json's default opener does not forward the key", refused_fetch and hits["stolen"] == 0 and not hits["key_on_stolen"])
    check("one_member's default opener does not forward the key", refused_member and hits["stolen"] == 0)


def test_derived_outputs_are_compact_and_key_free():
    print("derived")
    root = Path(__file__).resolve().parents[1]
    congress = json.loads((root / "data" / "career" / "congress.json").read_text())
    blob = json.dumps(congress).lower()
    check("congress derived file has no api key", "api_key=" not in blob and "data_gov_api_key" not in blob and "api.congress.gov" not in blob)
    check("congress coverage begins with a year", isinstance(congress.get("earliest_year"), int))
    check("congress citation is the public site", congress.get("source_url") == "https://www.congress.gov/")
    member = congress["members"]["S000033"]
    check("a member has a first year, terms, and a bill count", isinstance(member["first_year"], int) and member["terms"] and isinstance(member["sponsored_bill_count"], int))
    check("the bill count does not include an amendments field", "amendment" not in json.dumps(member["sponsored_bills"][:1]))
    bill = member["sponsored_bills"][0]
    check("a sponsored bill is congress, type, and number", isinstance(bill, list) and len(bill) == 3)
    check("the derived congress file stays under 5 MB", (root / "data" / "career" / "congress.json").stat().st_size < 5_000_000)
    check("a member record keeps its retrieval date", isinstance(member.get("retrieved_at"), str) and member["retrieved_at"])
    years = json.loads((root / "data" / "career" / "first-years.json").read_text())
    check("the small index has this member's first year", years["S000033"] == member["first_year"])
    coverage = json.loads((root / "data" / "career" / "coverage.json").read_text())
    check("coverage begins values are integers", all(isinstance(coverage[name]["begins"], int) for name in ("fec", "lda", "congress")))
    fec = json.loads((root / "data" / "career" / "fec.json").read_text())
    check("fec derived coverage begins in 1980", fec.get("begins") == 1980 and fec["cycles"][0]["cycle"] == 1980)
    check("fec derived output does not list an individual file", "itcont" not in json.dumps(fec) and "indiv" not in json.dumps(fec["cycles"]))
    lda = json.loads((root / "data" / "career" / "lda.json").read_text())
    lda_blob = json.dumps(lda).lower()
    check("lda derived file has no api key", "api_key" not in lda_blob)
    check("lda citation is the public filings api", lda.get("source_url") == "https://lda.gov/api/v1/filings/")
    check("lda derived coverage begins in 1999", lda.get("begins") == 1999)
    check(
        "1999 mid-year or year-end reports are counted",
        any(item.get("year") == 1999 and item.get("filing_type") in ("MM", "YY") and isinstance(item.get("count"), int) and item["count"] > 0 for item in lda["periods"]),
    )


def test_build_does_not_download():
    print("build")
    prebuild = json.loads(Path(__file__).resolve().parents[1].joinpath("package.json").read_text())["scripts"]["prebuild"]
    check("prebuild does not run the career download", "career_fec" not in prebuild and "career_lda" not in prebuild and "career_congress" not in prebuild)


if __name__ == "__main__":
    test_fec_urls()
    test_congress_script()
    test_default_openers_do_not_forward_the_key()
    test_derived_outputs_are_compact_and_key_free()
    test_build_does_not_download()
    if failures:
        print("FAILED", len(failures))
        sys.exit(1)
    print("ok")
