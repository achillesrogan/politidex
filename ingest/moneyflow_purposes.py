"""Check that a stored purpose excerpt still appears on its source page.

A missing excerpt or a page that cannot be retrieved is flagged for re-review.
The script does not rewrite the quote.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PURPOSE_PATH = ROOT / "data" / "moneyflow" / "purposes.json"
UA = "Politidex-civic-research/0.1 (+https://politidex.icu; open-source non-profit)"
MAX_BYTES = 2_000_000


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


def host_of(url):
    """Https host with no userinfo and no non-default port, or None."""
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    if parsed.port not in (None, 443):
        return None
    return (parsed.hostname or "").lower() or None


def stored_hosts(data):
    hosts = set()
    for entry in data.get("committees") or []:
        host = host_of(((entry.get("source") or {}).get("source_url")) or "")
        if host:
            hosts.add(host)
    return hosts


class _StayOnHost(urllib.request.HTTPRedirectHandler):
    def __init__(self, host):
        super().__init__()
        self._host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if host_of(newurl) != self._host:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ManualReview(Exception):
    """The page was retrieved, but its text cannot be checked automatically."""


def pdf_bytes_to_text(raw):
    """Return extracted PDF text, or None when no extractor can read it."""
    exe = shutil.which("pdftotext")
    if exe:
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
                handle.write(raw)
                handle.flush()
                result = subprocess.run(
                    [exe, "-layout", handle.name, "-"],
                    check=False,
                    capture_output=True,
                )
            if result.returncode == 0:
                return result.stdout.decode("utf-8", errors="replace")
        except Exception:
            pass
    try:
        from io import BytesIO
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None


def bytes_to_document(raw, url):
    is_pdf = raw.startswith(b"%PDF") or url.lower().split("?", 1)[0].endswith(".pdf")
    if not is_pdf:
        return raw.decode("utf-8", errors="replace")
    text = pdf_bytes_to_text(raw)
    if text is None:
        raise ManualReview("PDF text extraction is not available")
    return text


def fetch(url, timeout=25, allow=None):
    host = host_of(url)
    if not host or (allow is not None and host not in allow):
        raise ValueError("host is not on the stored allowlist")
    opener = urllib.request.build_opener(_StayOnHost(host))
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            raise ValueError("redirect left the host") from None
        raise
    with response:
        final = host_of(response.geturl())
        if final != host:
            raise ValueError("redirect left the host")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("response exceeds 2000000 bytes")
    return bytes_to_document(raw, response.geturl() or url)


def review(fetch_page=None):
    """Return a list of flag strings. Empty means every stored excerpt was found."""
    data = json.loads(PURPOSE_PATH.read_text())
    allow = stored_hosts(data)

    def default_fetch(url):
        return fetch(url, allow=allow)

    fetch_page = fetch_page or default_fetch
    flags = []
    for entry in data.get("committees") or []:
        cid = entry.get("committee_id") or "?"
        if not entry.get("found"):
            continue
        source = entry.get("source") or {}
        url = source.get("source_url") or ""
        excerpt = source.get("excerpt") or ""
        host = host_of(url)
        if host not in allow or not excerpt:
            flags.append("%s: stored quote is missing an allowlisted https source or excerpt" % cid)
            continue
        try:
            page = fetch_page(url)
        except ManualReview as exc:
            flags.append("%s: manual re-verification: %s" % (cid, exc))
            continue
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
