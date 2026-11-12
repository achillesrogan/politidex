"""Cache Congress.gov short/official titles for 119th bills mentioned in LDA filings.

Usage: python3 ingest/fetch_bill_titles.py
Never prints API keys. Resumes from data/raw/congress/bill-titles/.
"""
from __future__ import annotations
import json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from congress import get
import lda_match as M
from connections_lda import load_member_bills, iter_filings

OUT = RAW / "congress" / "bill-titles"
MENTIONED = OUT / "_mentioned.json"
TYPE_PATH = {
    "HR": "hr", "S": "s", "HJRES": "hjres", "SJRES": "sjres",
    "HCONRES": "hconres", "SCONRES": "sconres", "HRES": "hres", "SRES": "sres",
}
TYPE_PRIORITY = {k: i for i, k in enumerate(["HR", "S", "HJRES", "SJRES", "HRES", "SRES", "HCONRES", "SCONRES"])}


def mentioned_bills():
    if MENTIONED.exists():
        return [tuple(x) for x in json.loads(MENTIONED.read_text())]
    people, bills = load_member_bills()
    found = set()
    for row in iter_filings():
        for act in row.get("lobbying_activities") or []:
            desc = act.get("description") or ""
            if not desc:
                continue
            for hit in M.parse_bill_mentions(desc):
                if (hit.typ, hit.number) in bills:
                    found.add((hit.typ, hit.number))
    items = sorted(found)
    OUT.mkdir(parents=True, exist_ok=True)
    MENTIONED.write_text(json.dumps(items))
    return items


def cache_path(typ, num):
    return OUT / f"{typ.lower()}-{num}.json"


def fetch_one(typ, num):
    path = f"/bill/119/{TYPE_PATH[typ]}/{num}/titles?format=json"
    rel = f"bill-titles/{typ.lower()}-{num}.json"
    d = get(path, rel)
    return typ, num, d is not None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    items = mentioned_bills()
    items = sorted(items, key=lambda tn: (TYPE_PRIORITY.get(tn[0], 99), int(tn[1]) if str(tn[1]).isdigit() else 10**9, tn[1]))
    todo = [(t, n) for t, n in items if not cache_path(t, n).exists()]
    print(f"mentioned {len(items)}; already cached {len(items)-len(todo)}; to fetch {len(todo)}", flush=True)
    ok = fail = 0
    workers = 3
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_one, t, n) for t, n in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            typ, num, success = fut.result()
            if success:
                ok += 1
            else:
                fail += 1
                print(f"fail {typ} {num} ({fail} failed, {i}/{len(todo)})", flush=True)
            if i % 100 == 0 or typ == "HR" and num == "1492":
                print(f"progress {i}/{len(todo)} ok {ok} fail {fail}", flush=True)
    print(f"done fetched_ok {ok} fail {fail} cached_total {len(list(OUT.glob('*.json')))}", flush=True)


if __name__ == "__main__":
    main()
