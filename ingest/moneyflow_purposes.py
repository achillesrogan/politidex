"""Check that a stored purpose excerpt still appears on its source page.

A missing excerpt or a page that cannot be retrieved is flagged for re-review.
The script does not rewrite the quote.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PURPOSE_PATH = ROOT / "data" / "moneyflow" / "purposes.json"
UA = "Politidex-civic-research/0.1 (+https://politidex.icu; open-source non-profit)"


def normalize_document(text):
    text = html.unescape(text or "")
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip()


def excerpt_in_document(excerpt, document):
    needle = normalize_document(excerpt)
    if not needle:
        return False
    return needle in normalize_document(document)


def fetch(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def review(fetch_page=fetch):
    """Return a list of flag strings. Empty means every stored excerpt was found."""
    data = json.loads(PURPOSE_PATH.read_text())
    flags = []
    for entry in data.get("committees") or []:
        cid = entry.get("committee_id") or "?"
        if not entry.get("found"):
            continue
        source = entry.get("source") or {}
        url = source.get("source_url") or ""
        excerpt = source.get("excerpt") or ""
        if not url.startswith("https://") or not excerpt:
            flags.append("%s: stored quote is missing an https source or excerpt" % cid)
            continue
        try:
            page = fetch_page(url)
        except Exception as exc:
            flags.append("%s: could not retrieve %s (%s)" % (cid, url, type(exc).__name__))
            continue
        if not excerpt_in_document(excerpt, page):
            flags.append("%s: excerpt no longer appears at %s" % (cid, url))
    return flags


def main():
    flags = review()
    if flags:
        print("purpose check flagged for re-review:")
        for line in flags:
            print(line)
        return 1
    print("purpose check: every stored excerpt is still on its source page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
