"""Full-career Congress.gov terms and sponsored bills.

The Congress.gov API does not provide a member's committee-assignment history.
This script does not invent those assignments. Committee rosters already on the
site stay the current House Clerk and Senate files.

The key is read only from DATA_GOV_API_KEY. It is sent only as the X-Api-Key
header. It is not printed, not written into the output, and not put in the URL.
Requests stay at or under 5,000 per hour. A finished bioguide is skipped.

  DATA_GOV_API_KEY='your-key' python3 ingest/career_congress.py

Optional: --bioguides path/to/ids.txt (one bioguide per line).
Without that flag, bioguides are read from data/build/site/people.json.
Output: data/career/congress.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, ROOT, UA, now_iso, write_json

BASE = "https://api.congress.gov/v3"
PER_HOUR = 5000
INTERVAL = 3600 / PER_HOUR
PAGE_LIMIT = 250
MAX_PAGES = 40
RAW = ROOT / "data" / "raw" / "congress-career"
OUT = ROOT / "data" / "career" / "congress.json"
TYPE_PATH = {
    "HR": "house-bill",
    "S": "senate-bill",
    "HRES": "house-resolution",
    "SRES": "senate-resolution",
    "HJRES": "house-joint-resolution",
    "SJRES": "senate-joint-resolution",
    "HCONRES": "house-concurrent-resolution",
    "SCONRES": "senate-concurrent-resolution",
}


def load_key():
    key = os.environ.get("DATA_GOV_API_KEY") or ""
    if not key.strip():
        raise SystemExit("Set DATA_GOV_API_KEY in the environment. The key is not read from a file.")
    return key


def ordinal(year):
    number = int(year)
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return "%d%s" % (number, suffix)


def public_bill_url(congress, bill_type, number):
    slug = TYPE_PATH.get((bill_type or "").upper())
    if not slug or not str(number).isdigit() or not str(congress).isdigit():
        return None
    return "https://www.congress.gov/bill/%s-congress/%s/%s" % (ordinal(int(congress)), slug, int(number))


class HourLimit:
    """At most `per_hour` calls. `wait` returns how long the caller should sleep."""

    def __init__(self, per_hour=PER_HOUR):
        self.per_hour = per_hour
        self.interval = 3600 / per_hour
        self.sent = []

    def wait(self, now):
        cutoff = now - 3600
        self.sent = [stamp for stamp in self.sent if stamp > cutoff]
        delay = 0
        if len(self.sent) >= self.per_hour:
            delay = self.sent[0] + 3600 - now
        elif self.sent:
            delay = max(0, self.interval - (now - self.sent[-1]))
        self.sent.append(now + delay)
        return delay


def request_url(path):
    if path.startswith("http") or "api_key=" in path or "DATA_GOV_API_KEY" in path:
        raise SystemExit("refusing a request path that is not a relative API path")
    return BASE + path


class RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect must not be followed. The X-Api-Key header would be copied onto it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SystemExit("refusing an HTTP redirect so the API key is not forwarded")


def no_redirect_opener():
    return urllib.request.build_opener(RefuseRedirect())


def fetch_json(path, key, opener=None):
    url = request_url(path)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "X-Api-Key": key,
    })
    if any(name.lower() == "api_key" for name, _value in req.header_items()):
        raise SystemExit("refusing to send the key as a header other than X-Api-Key")
    open_fn = opener if opener is not None else no_redirect_opener().open
    try:
        with open_fn(req, timeout=40) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        print("HTTP %s %s" % (exc.code, path.split("?", 1)[0]), flush=True)
        return None
    data = json.loads(body)
    return scrub(data)


def scrub(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in {"api_key", "apikey", "x-api-key"}:
                continue
            out[key] = scrub(item)
        return out
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str) and "api_key=" in value:
        return value.split("api_key=", 1)[0].rstrip("?&")
    return value


def terms_of(member):
    rows = []
    years = []
    for term in member.get("terms") or []:
        start = term.get("startYear")
        if isinstance(start, int):
            years.append(start)
        rows.append({
            "chamber": term.get("chamber"),
            "congress": term.get("congress"),
            "startYear": start,
            "endYear": term.get("endYear"),
            "state": term.get("stateCode") or term.get("stateName"),
            "district": term.get("district"),
        })
    return rows, (min(years) if years else None)


def sponsored_of(pages):
    bills = []
    seen = set()
    for page in pages:
        for item in page.get("sponsoredLegislation") or []:
            congress = item.get("congress")
            bill_type = item.get("type")
            number = item.get("number")
            key = (congress, bill_type, str(number))
            if key in seen:
                continue
            seen.add(key)
            url = public_bill_url(congress, bill_type, number)
            if not url:
                continue
            bills.append({
                "congress": congress,
                "type": bill_type,
                "number": str(number),
            })
    return bills


def bioguides_from_people(path):
    if not path.exists():
        return []
    people = json.loads(path.read_text()).get("people") or []
    return [person["bioguide"] for person in people if person.get("bioguide")]


def read_bioguides(argv):
    if "--bioguides" in argv:
        path = Path(argv[argv.index("--bioguides") + 1])
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return bioguides_from_people(BUILD / "site" / "people.json")


def assemble(member_dir=RAW):
    """Compact members keyed by bioguide. Bill URLs are rebuilt with public_bill_url."""
    members = {}
    earliest = None
    if not member_dir.exists():
        return {"members": {}, "earliest_year": None}
    for path in sorted(member_dir.glob("*.json")):
        row = json.loads(path.read_text())
        if not row.get("complete"):
            continue
        terms = []
        years = []
        for term in row.get("terms") or []:
            start = term.get("startYear")
            if isinstance(start, int):
                years.append(start)
            item = {
                "chamber": term.get("chamber"),
                "congress": term.get("congress"),
                "startYear": start,
                "endYear": term.get("endYear"),
                "state": term.get("state"),
            }
            if term.get("district") is not None:
                item["district"] = term.get("district")
            terms.append(item)
        first = min(years) if years else row.get("earliest_year")
        bills = []
        for bill in row.get("sponsored_bills") or []:
            bills.append([bill.get("congress"), bill.get("type"), str(bill.get("number"))])
        members[row["bioguide"]] = {
            "first_year": first,
            "retrieved_at": row.get("retrieved_at"),
            "terms": terms,
            # Sponsored bills and resolutions only. Amendments are not in this count.
            "sponsored_bill_count": len(bills),
            "sponsored_bills": bills,
        }
        if isinstance(first, int) and (earliest is None or first < earliest):
            earliest = first
    return {
        "retrieved_at": now_iso(),
        "source_name": "Congress.gov",
        "source_url": "https://www.congress.gov/",
        "earliest_year": earliest,
        "committee_note": "The Congress.gov API has no member committee-assignment history. This file does not include committee assignments.",
        "sponsored_bills_note": "sponsored_bill_count is sponsored bills and resolutions. Amendments are not included. Public bill URLs are rebuilt with public_bill_url.",
        "members": members,
    }


def write_compact(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def paced(path, key, limit, opener, sleep):
    delay = limit.wait(time.time())
    if delay:
        sleep(delay)
    # None selects the no-redirect opener inside fetch_json.
    return fetch_json(path, key, opener)


def one_member(bioguide, key, limit, opener=None, sleep=time.sleep):
    detail = paced("/member/%s?format=json" % bioguide, key, limit, opener, sleep)
    if not detail or "member" not in detail:
        return None
    terms, earliest = terms_of(detail["member"])
    pages = []
    offset = 0
    for _ in range(MAX_PAGES):
        page = paced(
            "/member/%s/sponsored-legislation?format=json&limit=%d&offset=%d" % (bioguide, PAGE_LIMIT, offset),
            key,
            limit,
            opener,
            sleep,
        )
        if not page:
            break
        pages.append(page)
        count = page.get("pagination", {}).get("count")
        got = len(page.get("sponsoredLegislation") or [])
        offset += PAGE_LIMIT
        if got < PAGE_LIMIT or (isinstance(count, int) and offset >= count):
            break
    return {
        "bioguide": bioguide,
        "complete": True,
        "retrieved_at": now_iso(),
        "earliest_year": earliest,
        "terms": terms,
        "sponsored_bills": sponsored_of(pages),
        "committees": None,
    }


def main(argv):
    ids = read_bioguides(argv)
    if not ids:
        raise SystemExit("No bioguides. Pass --bioguides ids.txt or build data/build/site/people.json first.")
    key = load_key()
    RAW.mkdir(parents=True, exist_ok=True)
    limit = HourLimit()
    for bioguide in ids:
        dest = RAW / ("%s.json" % bioguide)
        if dest.exists():
            try:
                if json.loads(dest.read_text()).get("complete"):
                    continue
            except json.JSONDecodeError:
                pass
        row = one_member(bioguide, key, limit)
        if row:
            write_json(dest, scrub(row))
            print("saved", bioguide, flush=True)
    write_compact(OUT, scrub(assemble()))
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
