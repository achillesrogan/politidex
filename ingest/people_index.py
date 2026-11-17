"""Index of reported individual donors for the 2026 cycle.

The money-flow graph still does not read individual-contribution files.
This module is the separate, owner-approved donor index.

A person is published only when itemized rows that substantively match
aggregate to at least $10,000.00. Name alone never links two rows. A match
needs the same last name, first name, and full middle-name field, plus the
same city, state, employer, and occupation, all non-empty. Anything short of
that is listed for review and is not published.

Published records show name, city, and state. Street and ZIP are not stored.
There is no bulk export and no contact field.

indiv26.zip was 2,602,361,290 bytes compressed on 2026-11-15. This checkpoint
does not download it. Build from a local file later with build_index().
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from moneyflow_lib import in_cycle, is_memo, parse_fec_date

THRESHOLD_CENTS = 1_000_000  # $10,000.00
FILE_URL = "https://www.fec.gov/files/bulk-downloads/2026/indiv26.zip"
FILE_BYTES = 2602361290
DESCRIPTION_URL = "https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/"
NOTICE = (
    "Contributor information may not be sold or used for the purpose of "
    "soliciting contributions or for commercial purposes (52 U.S.C. § 30111(a)(4))."
)
OFFICIAL_ROLES = frozenset({
    "treasurer", "assistant treasurer", "custodian of records", "designated agent",
    "officer", "director", "chair", "president", "secretary",
})
BUSINESS_METHODS = frozenset({"company_domain", "sec_edgar", "state_registry"})
_SUFFIXES = frozenset({"JR", "SR", "II", "III", "IV"})
_HIDDEN = frozenset({
    "zip", "zip_code", "street", "street_1", "street_2", "address",
    "phone", "email", "employer_address",
})


def money_to_cents(raw):
    s = (raw or "").strip().replace(",", "").replace("$", "")
    if s == "":
        return None
    try:
        quant = (Decimal(s) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except Exception:
        return None
    return int(quant)


def cents_to_decimal(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


def _norm(value):
    return " ".join((value or "").upper().replace(".", " ").split())


def parse_person_name(raw):
    """LAST, FIRST [MIDDLE...]. A missing comma is not treated as a person name."""
    text = _norm(raw)
    if "," not in text:
        return None
    last, given = text.split(",", 1)
    last = last.strip()
    tokens = [tok for tok in given.split() if tok not in _SUFFIXES]
    if not last or not tokens:
        return None
    return {"last": last, "first": tokens[0], "middle": " ".join(tokens[1:])}


def parse_indiv_line(line):
    """One itcont row. ZIP is read only so it can be dropped. Street is not a column."""
    parts = line.rstrip("\r\n").split("|")
    if len(parts) < 21:
        return None
    amount = money_to_cents(parts[14])
    if amount is None:
        return None
    return {
        "committee_id": parts[0].strip(),
        "image": parts[4].strip(),
        "txn_type": parts[5].strip().upper(),
        "entity": parts[6].strip().upper(),
        "name": parts[7].strip(),
        "city": _norm(parts[8]),
        "state": _norm(parts[9]),
        "employer": _norm(parts[11]),
        "occupation": _norm(parts[12]),
        "date": parse_fec_date(parts[13]),
        "amount_cents": amount,
        "tran_id": parts[16].strip(),
        "memo": parts[18].strip().upper(),
        "sub_id": parts[20].strip(),
    }


def _identity(row):
    name = parse_person_name(row.get("name"))
    if not name:
        return None
    city, state = row.get("city") or "", row.get("state") or ""
    employer, occupation = row.get("employer") or "", row.get("occupation") or ""
    if not all((name["last"], name["first"], city, state, employer, occupation)):
        return None
    return (name["last"], name["first"], name["middle"], city, state, employer, occupation)


def _source(row, retrieved_at):
    image = row.get("image") or ""
    url = ("https://docquery.fec.gov/cgi-bin/fecimg/?" + image) if image else DESCRIPTION_URL
    excerpt = "FEC individual contribution %s %s %s on %s, sub_id %s." % (
        row.get("committee_id") or "",
        cents_to_decimal(row.get("amount_cents") or 0),
        row.get("name") or "",
        row.get("date") or "undated",
        row.get("sub_id") or "none",
    )
    return {
        "source_name": "Federal Election Commission",
        "source_url": url,
        "retrieved_at": retrieved_at,
        "excerpt": excerpt,
        "image_number": image or None,
        "sub_id": row.get("sub_id") or None,
    }


def _eligible(row):
    if row.get("entity") != "IND":
        return False
    if is_memo(row.get("memo")):
        return False
    if not in_cycle(row.get("date")):
        return False
    return True


def _dedupe_key(row):
    tran = row.get("tran_id") or ""
    if not tran:
        return None
    return (row.get("committee_id"), tran, row.get("date"), row.get("amount_cents"))


def _public_gift(row, retrieved_at):
    return {
        "date": row.get("date"),
        "amount": cents_to_decimal(row["amount_cents"]),
        "amount_cents": row["amount_cents"],
        "committee_id": row.get("committee_id"),
        "source": _source(row, retrieved_at),
    }


def _display_name(key):
    last, first, middle = key[0], key[1], key[2]
    given = first if not middle else first + " " + middle
    return "%s, %s" % (last, given)


def to_public(person):
    """Drop street, ZIP, phone, and email if a caller attached them."""
    out = {}
    for key, value in person.items():
        if key.lower() in _HIDDEN:
            continue
        out[key] = value
    return out


def build_index(rows, retrieved_at):
    """Aggregate eligible rows. Published people are those at or above $10,000.00."""
    seen = set()
    groups = {}
    weak = []
    for row in rows:
        if not _eligible(row):
            continue
        marker = _dedupe_key(row)
        if marker is not None:
            if marker in seen:
                continue
            seen.add(marker)
        ident = _identity(row)
        if ident is None:
            name = parse_person_name(row.get("name"))
            if name:
                weak.append((name, row, "missing city, state, employer, or occupation"))
            continue
        groups.setdefault(ident, []).append(row)

    published = []
    unlinked = []
    below = 0
    by_bare = {}
    for ident, members in groups.items():
        by_bare.setdefault((ident[0], ident[1]), []).append((ident, members))
    for name, row, reason in weak:
        by_bare.setdefault((name["last"], name["first"]), []).append((None, [(row, reason)]))

    for (last, first), clusters in sorted(by_bare.items()):
        strong = [(ident, members) for ident, members in clusters if ident is not None]
        if len(strong) > 1 or any(ident is None for ident, _ in clusters):
            unlinked.append({
                "name": "%s, %s" % (last, first),
                "reason": "Same first and last name were not linked. Middle name, city, state, employer, or occupation did not all agree.",
                "clusters": _cluster_summaries(clusters),
            })
        for ident, members in strong:
            total = sum(item["amount_cents"] for item in members)
            if total < THRESHOLD_CENTS:
                below += len(members)
                continue
            gifts = [_public_gift(item, retrieved_at) for item in sorted(members, key=lambda r: (r.get("date") or "", r.get("sub_id") or ""))]
            person = {
                "id": "p_" + hashlib.sha1("|".join(ident).encode("utf-8")).hexdigest()[:16],
                "name": _display_name(ident),
                "city": ident[3],
                "state": ident[4],
                "employer": ident[5],
                "occupation": ident[6],
                "amount": cents_to_decimal(total),
                "amount_cents": total,
                "contributions": gifts,
                "identity_source": gifts[0]["source"],
                "qualification": "Itemized FEC contributions in the 2026 cycle aggregate to at least $10,000.00 for this reported name, middle name, city, state, employer, and occupation.",
            }
            published.append(to_public(person))
    published.sort(key=lambda person: (-person["amount_cents"], person["name"], person["id"]))
    return {
        "notice": NOTICE,
        "threshold_cents": THRESHOLD_CENTS,
        "published": published,
        "unlinked": unlinked,
        "below_threshold_rows": below,
    }


def _cluster_summaries(clusters):
    out = []
    for ident, members in clusters:
        if ident is None:
            row, reason = members[0]
            out.append({
                "middle": parse_person_name(row.get("name")).get("middle"),
                "city": row.get("city"),
                "state": row.get("state"),
                "employer": row.get("employer"),
                "occupation": row.get("occupation"),
                "rows": 1,
                "reason": reason,
            })
            continue
        out.append({
            "middle": ident[2],
            "city": ident[3],
            "state": ident[4],
            "employer": ident[5],
            "occupation": ident[6],
            "rows": len(members),
            "amount": cents_to_decimal(sum(item["amount_cents"] for item in members)),
        })
    return out


def verify_index(rows, published, retrieved_at):
    """Rebuild and require the same published ids and totals."""
    fresh = build_index(rows, retrieved_at)
    got = {(person["id"], person["amount_cents"]) for person in fresh["published"]}
    expected = {(person["id"], person["amount_cents"]) for person in published}
    return got == expected


def business_website(name, candidate_url, verification):
    """Link a business only when an official source verifies the host."""
    if not name or not candidate_url or not verification:
        return None
    source = verification.get("source") or {}
    if not all(source.get(key) for key in ("source_name", "source_url", "retrieved_at", "excerpt")):
        return None
    method = verification.get("method")
    if method not in BUSINESS_METHODS:
        return None
    try:
        from urllib.parse import urlparse
        host = urlparse(candidate_url).hostname or ""
    except Exception:
        return None
    if urlparse_scheme(candidate_url) != "https":
        return None
    expected = (verification.get("host") or "").lower()
    if method == "company_domain" and host.lower() != expected:
        return None
    if method == "sec_edgar" and host.lower() != "www.sec.gov":
        return None
    if method == "state_registry" and host.lower() != expected:
        return None
    return {
        "name": name,
        "url": candidate_url,
        "method": method,
        "source": source,
    }


def urlparse_scheme(url):
    from urllib.parse import urlparse
    return (urlparse(url).scheme or "").lower()


def link_officer_donations(officer, donations, retrieved_at):
    """Link donations only when the officer source and the donor identity agree."""
    source = officer.get("source") or {}
    role = _norm(officer.get("role")).lower()
    if role not in OFFICIAL_ROLES:
        return None
    if not all(source.get(key) for key in ("source_name", "source_url", "retrieved_at", "excerpt")):
        return None
    officer_row = {
        "name": officer.get("name"),
        "city": _norm(officer.get("city")),
        "state": _norm(officer.get("state")),
        "employer": _norm(officer.get("employer")),
        "occupation": _norm(officer.get("occupation")),
        "entity": "IND",
        "memo": "",
        "date": "2026-01-01",
        "amount_cents": 0,
    }
    ident = _identity(officer_row)
    if ident is None:
        return {"linked": False, "reason": "Officer identity is not substantiated.", "gifts": []}
    gifts = []
    for row in donations:
        if not _eligible(row):
            continue
        if _identity(row) == ident:
            gifts.append(_public_gift(row, retrieved_at))
    if not gifts:
        return {"linked": False, "reason": "No donation row agreed on middle name, city, state, employer, and occupation.", "gifts": []}
    return {
        "linked": True,
        "name": _display_name(ident),
        "role": role,
        "officer_source": source,
        "gifts": gifts,
    }


def scope_report():
    return {
        "schema": "politidex.people.review.v1",
        "status": "not_run",
        "published_people": [],
        "threshold": "10000.00",
        "indiv_zip_bytes": FILE_BYTES,
        "indiv_zip_last_modified": "Sun, 15 Nov 2026 17:10:23 GMT",
        "file_url": FILE_URL,
        "description_url": DESCRIPTION_URL,
        "notice": NOTICE,
        "reason": (
            "The 2026 individual-contributions file is 2,602,361,290 bytes compressed. "
            "This checkpoint does not download it and does not publish any real person. "
            "Business-site, SEC, IRS Form 990, and state-registry lookups are not run. "
            "The qualification rules are implemented and covered by synthetic tests."
        ),
    }


def main():
    print(json.dumps(scope_report(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
