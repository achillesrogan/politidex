"""Derive high-consensus short titles from LDA text when Congress.gov has none.

Usage: python3 ingest/build_popular_bill_titles.py
Writes data/raw/congress/popular-short-titles.json
"""
from __future__ import annotations
import json, sys, collections, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import lda_match as M
from connections_lda import load_member_bills, iter_filings

OUT = RAW / "congress" / "popular-short-titles.json"
MIN_COUNT = 5
MIN_SHARE = 0.6



def _acceptable(title: str, acr) -> bool:
    words = M._phrase_tokens(title)
    if any(a for a in acr if a and a not in M.GENERIC_ACRONYMS):
        return True
    content = [w for w in words if w.lower() not in M.STOPWORDS and len(w) >= 3]
    if len(content) >= 2:
        return True
    if len(content) == 1 and content[0].isupper() and 3 <= len(content[0]) <= 8:
        return True
    return False


def norm_title(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "").strip())
    t = re.sub(r"(?i)\s+act(?:\s+of\s+\d{4})?$", " Act", t).strip()
    return t


def main():
    people, bills = load_member_bills()
    attached = collections.defaultdict(list)  # key -> list of (title, acr_frozenset)
    mentions = collections.Counter()
    for row in iter_filings():
        for act in row.get("lobbying_activities") or []:
            desc = act.get("description") or ""
            if not desc:
                continue
            hits = M.parse_bill_mentions(desc)
            if not hits:
                continue
            for hit in hits:
                if (hit.typ, hit.number) not in bills:
                    continue
                key = f"{hit.typ}-{hit.number}"
                mentions[key] += 1
                window = M.title_window(desc, hit, hits)
                titles, acr = M.leading_local_titles(window)
                # ignore quoted official long titles
                titles = [x for x in titles if not M._looks_like_official_long_title(x)]
                if titles or acr:
                    attached[key].append((tuple(norm_title(x) for x in titles if x), frozenset(acr)))

    out = {}
    for key, recs in attached.items():
        n_att = len(recs)
        if n_att < MIN_COUNT:
            continue
        # If Congress.gov already has a real short title, skip
        typ, num = key.split("-", 1)
        official_shorts, official_acr = M.bill_short_titles_and_acronyms(None, typ, num)
        # bill_short would also load popular if present; clear and check cache only
        official_shorts = []
        official_acr = set()
        for item in M.load_cached_bill_titles(typ, num):
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            kind = (item.get("titleType") or item.get("type") or "").lower()
            if not title:
                continue
            if ("short" in kind or kind.startswith("display")) and not M._looks_like_official_long_title(title):
                official_shorts.append(title)
            official_acr |= M.extract_acronyms([title])
        if official_shorts:
            continue

        title_counts = collections.Counter()
        acr_counts = collections.Counter()
        for titles, acr in recs:
            for t in titles:
                if t:
                    title_counts[t.lower()] += 1
            for a in acr:
                acr_counts[a] += 1
        titles_out = []
        # prefer a dominant acronym
        if acr_counts:
            a, c = acr_counts.most_common(1)[0]
            if c >= MIN_COUNT and c / n_att >= MIN_SHARE:
                # pick the most common full title containing that acronym, else "A Act"
                candidates = [(t, n) for t, n in title_counts.items() if a.lower() in t.lower()]
                best = max(candidates, key=lambda x: x[1])[0] if candidates else f"{a} Act"
                # recover original casing from recs
                display = None
                for ts, _a in recs:
                    for t in ts:
                        if t.lower() == (best if isinstance(best, str) else "") or a in t:
                            display = t
                            break
                    if display:
                        break
                titles_out.append({"title": display or f"{a} Act", "acronyms": [a], "count": c, "attached": n_att, "mentions": mentions[key]})
        if not titles_out and title_counts:
            t, c = title_counts.most_common(1)[0]
            if c >= MIN_COUNT and c / n_att >= MIN_SHARE:
                display = None
                for ts, _a in recs:
                    for x in ts:
                        if x.lower() == t:
                            display = x
                            break
                    if display:
                        break
                titles_out.append({"title": display or t, "acronyms": sorted(M.extract_acronyms([display or t])), "count": c, "attached": n_att, "mentions": mentions[key]})
        titles_out = [item for item in titles_out if _acceptable(item.get("title") or "", item.get("acronyms") or [])]
        if titles_out:
            out[key] = {"titles": titles_out}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"wrote {len(out)} bills to {OUT}", flush=True)
    # show EPIC / 1492 if present
    for k in ("HR-1492", "S-832"):
        print(k, out.get(k))


if __name__ == "__main__":
    main()
