"""Offline Lobbying Disclosure Act filings from 1999 forward.

Uses the public Senate LDA API at https://lda.gov/api/v1/filings/.
This script is not part of npm run build.

  python3 ingest/career_lda.py

writes data/raw/lda-career/lda.json: filing counts, public URLs, and retrieval dates.
The file is not committed. Profile lobbying ties come from connections_lda.py.
Pass --crawl to resume the raw jsonl download under data/raw. That dump is
not committed. A finished year and filing type is skipped, and a failed page
is retried on the next run.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, ROOT, now_iso, read_json, write_json
from connections_lda import FILING_TYPES, compact, fetch_page

YEARS = tuple(range(1999, 2027))
# Quarterly codes start in 2008. Earlier lobbying reports use mid-year and year-end codes.
# No-activity codes stay out, matching FILING_TYPES.
HISTORICAL_TYPES = ("MM", "MT", "MA", "YY", "YT", "YA")
COUNT_TYPES = tuple(FILING_TYPES) + HISTORICAL_TYPES
RAWDIR = RAW / "lda-career"
PROGRESS = RAWDIR / "progress.json"
TYPES_NOTE = (
    "Counts cover activity-bearing quarterly reports, terminations, and amendments, "
    "plus the earlier mid-year and year-end reports (MM, MT, MA, YY, YT, YA). "
    "No-activity filings are omitted."
)


def period_key(year, filing_type):
    return "%s-%s" % (year, filing_type)


def load_progress():
    if PROGRESS.exists():
        return read_json(PROGRESS)
    return {"periods": {}, "started": now_iso(), "begins": 1999}


def save_progress(progress):
    progress["checkpoint"] = now_iso()
    write_json(PROGRESS, progress)


def crawl_period(year, filing_type, progress):
    key = period_key(year, filing_type)
    info = progress["periods"].setdefault(key, {
        "year": year, "filing_type": filing_type, "next_page": 1, "written": 0, "done": False,
    })
    if info.get("done"):
        print("skip complete", key, flush=True)
        return
    out = RAWDIR / ("%s.jsonl" % key)
    out.parent.mkdir(parents=True, exist_ok=True)
    page = int(info.get("next_page") or 1)
    while True:
        status, data = fetch_page(year, filing_type, page)
        if data is None:
            info["next_page"] = page
            info["error"] = "HTTP %s on page %s" % (status, page)
            save_progress(progress)
            print("stop", key, info["error"], flush=True)
            return
        results = data.get("results") or []
        count = data.get("count") or 0
        info["count"] = count
        with out.open("a", encoding="utf-8") as handle:
            for row in results:
                handle.write(json.dumps(compact(row), ensure_ascii=False) + "\n")
                info["written"] = info.get("written", 0) + 1
        info["next_page"] = page + 1
        save_progress(progress)
        pages = (count + 24) // 25 if count else page
        if page == 1 or page % 20 == 0 or page >= pages:
            print("%s page %s/%s" % (key, page, pages), flush=True)
        if not data.get("next") or page >= pages or not results:
            info["done"] = True
            save_progress(progress)
            return
        page += 1
        time.sleep(0.05)


def count_periods(types):
    """One page per year and filing type. Only the count is kept."""
    periods = []
    for year in YEARS:
        for filing_type in types:
            status, data = fetch_page(year, filing_type, 1)
            count = data.get("count") if data else None
            periods.append({
                "year": year,
                "filing_type": filing_type,
                "count": count,
                "source_url": "https://lda.gov/api/v1/filings/?filing_year=%s&filing_type=%s" % (year, filing_type),
                "retrieved_at": now_iso(),
                "http_status": status,
            })
            print("lda count", year, filing_type, count, flush=True)
            time.sleep(0.05)
    return periods


def write_derived(periods):
    known = [item["count"] for item in periods if isinstance(item["count"], int) and item["count"] > 0]
    begins = min((item["year"] for item in periods if isinstance(item.get("count"), int) and item["count"] > 0), default=1999)
    derived = {
        "retrieved_at": now_iso(),
        "source_name": "Senate Office of Public Records",
        "source_url": "https://lda.gov/api/v1/filings/",
        "begins": begins,
        "filing_count": sum(known),
        "types_note": TYPES_NOTE,
        "periods": periods,
    }
    path = RAW / "lda-career" / "lda.json"
    write_json(path, derived)
    print("wrote data/career/lda.json", len(periods), "periods", flush=True)
    return derived


def summarize_counts():
    """Compact counts for every career year. Filing text stays in the raw crawl."""
    write_derived(count_periods(COUNT_TYPES))


def crawl():
    progress = load_progress()
    for year in YEARS:
        for filing_type in FILING_TYPES:
            crawl_period(year, filing_type, progress)
    done = sum(1 for item in progress["periods"].values() if item.get("done"))
    print("lda career periods done", done, flush=True)


if __name__ == "__main__":
    summarize_counts()
    if "--crawl" in sys.argv:
        crawl()
