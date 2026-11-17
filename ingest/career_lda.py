"""Offline Lobbying Disclosure Act filings from 1999 forward.

Uses the public Senate LDA API at https://lda.gov/api/v1/filings/.
This script is not part of npm run build. It is resumable: a finished
year and filing type is skipped, and a failed page is retried on the next run.

  python3 ingest/career_lda.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, now_iso, read_json, write_json
from connections_lda import FILING_TYPES, compact, fetch_page

YEARS = tuple(range(1999, 2027))
RAWDIR = RAW / "lda-career"
PROGRESS = RAWDIR / "progress.json"


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


def crawl():
    progress = load_progress()
    for year in YEARS:
        for filing_type in FILING_TYPES:
            crawl_period(year, filing_type, progress)
    done = sum(1 for item in progress["periods"].values() if item.get("done"))
    print("lda career periods done", done, flush=True)


if __name__ == "__main__":
    crawl()
