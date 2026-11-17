"""Career ingest stays offline. No network and no API key."""
import json
import sys
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


def test_build_does_not_download():
    print("build")
    prebuild = json.loads(Path(__file__).resolve().parents[1].joinpath("package.json").read_text())["scripts"]["prebuild"]
    check("prebuild does not run the career download", "career_fec" not in prebuild and "career_lda" not in prebuild and "career_congress" not in prebuild)


if __name__ == "__main__":
    test_fec_urls()
    test_congress_script()
    test_build_does_not_download()
    if failures:
        print("FAILED", len(failures))
        sys.exit(1)
    print("ok")
