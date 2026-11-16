"""Pure functions for the FEC money-flow graph.

The build reads official bulk files in ingest/moneyflow.py. This module does
not download files, call the OpenFEC API, or read an API key.

Honesty. A node shows reported money out of that account. An edge is a sum of
itemized rows, not a traced dollar. Child edges plus the explicit residual
bucket equal the committee's official total disbursements from the PAC and
party summary file, or the build raises ReconciliationError.

Privacy. Entity types IND and CAN are people and are summed into one residual
bucket with no names. A blank, unrecognized, or conflicting entity type is
summed into the other residual bucket. Street address, city, ZIP, employer,
occupation, memo text, treasurer, and candidate-id columns are not accepted
by these parsers.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date

CYCLE = 2026
TOP_PAYEES = 25
SOURCE_NAME = "Federal Election Commission"

# Standing note for the page and every node card. Checkpoint 2 renders this;
# the shards carry it so the wording has one source.
FUNGIBILITY_NOTE = (
    "Reported money out of this account. Money in an account is fungible, "
    "so this is not a record that a particular dollar went to a particular payee."
)

EDGE_KINDS = (
    "reported contribution",
    "reported transfer",
    "reported disbursement",
    "spent",
)
EDGE_KIND_SET = frozenset(EDGE_KINDS)

INDIVIDUAL_BUCKET_NAME = "reported assistance to individuals — not itemized"
OTHER_BUCKET_NAME = "other reported disbursements"

BULK = "https://www.fec.gov/files/bulk-downloads/2026/"
FILE_URLS = {
    "cm": BULK + "cm26.zip",
    "oth": BULK + "oth26.zip",
    "pas2": BULK + "pas226.zip",
    "oppexp": BULK + "oppexp26.zip",
    "webk": BULK + "webk26.zip",
    "webl": BULK + "webl26.zip",
    "weball": BULK + "weball26.zip",
}
# Inner member names in the official zips.
FILE_MEMBERS = {
    "cm": "cm.txt",
    "oth": "itoth.txt",
    "pas2": "itpas2.txt",
    "oppexp": "oppexp.txt",
    "webk": "webk26.txt",
    "webl": "webl26.txt",
    "weball": "weball26.txt",
}
DESC_URLS = {
    "cm": "https://www.fec.gov/campaign-finance-data/committee-master-file-description/",
    "oth": "https://www.fec.gov/campaign-finance-data/any-transaction-one-committee-another-file-description/",
    "pas2": "https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/",
    "oppexp": "https://www.fec.gov/campaign-finance-data/operating-expenditures-file-description/",
    "webk": "https://www.fec.gov/campaign-finance-data/pac-and-party-summary-file-description/",
    "webl": "https://www.fec.gov/campaign-finance-data/current-campaigns-house-and-senate-file-description/",
    "weball": "https://www.fec.gov/campaign-finance-data/all-candidates-file-description/",
    "txn": "https://www.fec.gov/campaign-finance-data/transaction-type-code-descriptions/",
    "category": "https://www.fec.gov/campaign-finance-data/disbursement-category-code-descriptions/",
    "committee_type": "https://www.fec.gov/campaign-finance-data/committee-type-code-descriptions/",
}

# Transaction types the OTH file description says are included, split by
# whether the official transaction-type description is money leaving the filer.
# Receipt types are not outflows. A code on neither list is not guessed.
OTH_INCLUDED = frozenset({
    "10J", "11J", "13", "15J", "15Z", "16C", "16F", "16G", "16R", "17R", "17Z",
    "18G", "18J", "18K", "18U", "19J", "20", "20C", "20F", "20G", "20R", "22H",
    "22Z", "23Y", "24A", "24C", "24E", "24F", "24G", "24H", "24K", "24N", "24P",
    "24R", "24U", "24Z", "29", "30F", "30G", "30J", "30K", "31F", "31G", "31J",
    "31K", "32F", "32G", "32J", "32K", "40", "40Z", "41", "41Z", "42", "42Z",
})
DISBURSEMENT_TYPES = frozenset({
    "20", "20C", "20F", "20G", "20R", "22H", "22Z", "23Y",
    "24A", "24C", "24E", "24F", "24G", "24H", "24K", "24N", "24P", "24R", "24U", "24Z",
    "29", "40", "40Z", "41", "41Z", "42", "42Z",
})
RECEIPT_TYPES = OTH_INCLUDED - DISBURSEMENT_TYPES
CONTRIBUTION_TYPES = frozenset({"24K", "24Z", "24P", "24U"})
TRANSFER_TYPES = frozenset({"24G"})
PAS2_TYPES = frozenset({"24A", "24C", "24E", "24F", "24H", "24K", "24N", "24P", "24R", "24Z"})

# Official descriptions, transaction-type-code-descriptions page.
TXN_DESC = {
    "20": "Nonfederal disbursement - nonfederal party \"soft money\" accounts (1991-2002)",
    "20C": "Loan repayment made to candidate",
    "20F": "Loan repayment made to banks",
    "20G": "Loan repayment made to individual",
    "20R": "Loan repayment made to registered filer",
    "22H": "Loan to candidate or committee",
    "22Z": "Contribution refund to candidate or committee",
    "23Y": "Inaugural donation refund",
    "24A": "Independent expenditure opposing election of candidate",
    "24C": "Coordinated party expenditure",
    "24E": "Independent expenditure advocating election of candidate",
    "24F": "Communication cost for candidate (only for Form 7 filer)",
    "24G": "Transfer out to affiliated committee",
    "24H": "Honorarium to candidate",
    "24K": "Contribution made to nonaffiliated committee",
    "24N": "Communication cost against candidate (only for Form 7 filer)",
    "24P": "Contribution made to possible federal candidate including in-kind contributions",
    "24R": "Election recount disbursement",
    "24U": "Contribution made to unregistered entity",
    "24Z": "In-kind contribution made to registered filer",
    "29": "Electioneering Communication disbursement or obligation",
    "40": "Convention Account disbursement",
    "40Z": "Convention Account refund to registered filer",
    "41": "Headquarters Account disbursement",
    "41Z": "Headquarters Account refund to registered filer",
    "42": "Recount Account disbursement",
    "42Z": "Recount Account refund to registered filer",
}

# Official disbursement category descriptions. Free-text PURPOSE is never copied.
CATEGORY_DESC = {
    "001": "Administrative/salary/overhead expenses (e.g., rent, staff salaries, postage, office supplies, equipment, furniture, ballot access fees, petition drives, party fees and legal and accounting expenses)",
    "002": "Travel expenses - including travel reimbursement expenses (e.g., costs of commercial carrier tickets; reimbursements for use of private vehicles, advance payments for use of corporate aircraft; lodging and meal expenses incurred during travel)",
    "003": "Solicitation and fundraising expenses (e.g., costs for direct mail solicitations and fundraising events including printing, mailing lists, consultant fees, call lists, invitations, catering costs and room rental)",
    "004": "Advertising expenses -including general public political advertising (e.g., purchases of radio/television broadcast/cable time, print advertisements and related production costs)",
    "005": "Polling expenses",
    "006": "Campaign materials (e.g., buttons, bumper stickers, brochures, mass mailings, pens, posters, balloons)",
    "007": "Campaign event expenses (e.g., costs associated with candidate appearances, campaign rallies, town meetings, phone banks, including catering costs, door to door get-out-the-vote efforts and driving voters to the polls)",
    "008": "Transfers (e.g., to other authorized committees of the same candidate)",
    "009": "Loan repayments (e.g., repayments of loans made/guaranteed by the candidate or other person)",
    "010": "Refunds of contributions (e.g., contribution refunds to individuals/ persons, political party committees or other political committees)",
    "011": "Political contributions (e.g., contributions to other federal candidates and committees, donations to nonfederal candidates and committees)",
    "012": "Donations (e.g., donations to charitable or civic organizations)",
    "101": "Expenses that are not allocable",
    "102": "Media expenditures",
    "103": "Expenditures for mass mailings and other campaign materials (e.g., buttons, bumper stickers, brochures, mass mailings, pens, posters, balloons)",
    "104": "Overhead expenditures of state offices and their facilities (e.g., rent, staff salaries, postage, office supplies, equipment, furniture, ballot access fees, petition drives, party fees and legal and accounting expenses)",
    "105": "Expenditures for special telephone programs",
    "106": "Public opinion poll expenditures",
    "107": "Fundraising expenditures (e.g., costs for direct mail solicitations & fundraising events including printing, mailing lists, consultant fees, call lists, invitations, catering costs and room rental)",
}

COMMITTEE_TYPE = {
    "C": "Communication cost",
    "D": "Delegate committee",
    "E": "Electioneering communication",
    "H": "House",
    "I": "Independent expenditor (person or group)",
    "N": "PAC - nonqualified",
    "O": "Independent expenditure-only (Super PACs)",
    "P": "Presidential",
    "Q": "PAC - qualified",
    "S": "Senate",
    "U": "Single-candidate independent expenditure",
    "V": "Hybrid PAC (with Non-Contribution Account) - Nonqualified",
    "W": "Hybrid PAC (with Non-Contribution Account) - Qualified",
    "X": "Party - nonqualified",
    "Y": "Party - qualified",
    "Z": "National party nonfederal account",
}
ORG_TYPE = {
    "C": "Corporation",
    "L": "Labor organization",
    "M": "Membership organization",
    "T": "Trade association",
    "V": "Cooperative",
    "W": "Corporation without capital stock",
}
DESIGNATION = {
    "A": "Authorized by a candidate",
    "B": "Lobbyist/Registrant PAC",
    "D": "Leadership PAC",
    "J": "Joint fundraiser",
    "P": "Principal campaign committee of a candidate",
    "U": "Unauthorized",
}

PERSON_ENTITY = frozenset({"IND", "CAN"})
COMMITTEE_ENTITY = frozenset({"CCM", "COM", "PAC", "PTY"})
MAJOR_PARTY = frozenset({"DEM", "REP"})
PAC_TYPES = frozenset({"Q", "V", "W"})
ORG_TYPES = frozenset({"C", "L", "M", "T", "V", "W"})
PARTY_COMMITTEE_TYPES = frozenset({"X", "Y", "Z"})
CANDIDATE_COMMITTEE_TYPES = frozenset({"H", "S", "P"})
AUTHORIZED_DESIGNATIONS = frozenset({"A", "P"})

COMMITTEE_ID = re.compile(r"^C[0-9]{8}$")
CANDIDATE_ID = re.compile(r"^[HSP][0-9A-Z]{8}$")
IMAGE_NUM = re.compile(r"^[0-9]{11}$|^[0-9]{18}$")
DIGITS = re.compile(r"^[0-9]+$")

FORBIDDEN_KEYS = frozenset({
    "city", "zip", "zip_code", "street", "street_1", "street_2", "address",
    "employer", "occupation", "memo_text", "treasurer", "cand_name",
    "candidate_name", "candidate_id", "api_key",
})
BANNED_PHRASES = ("funneled", "bought influence", "earmarked", "earmark")

CLAIM_KEYS = ("id", "text", "value", "excerpt", "source_name", "source_url", "check", "retrieved_at", "status")


class ReconciliationError(Exception):
    """Itemized non-memo disbursements do not fit under the official total."""

    def __init__(self, committee_id, official_cents, itemized_cents):
        self.committee_id = committee_id
        self.official_cents = official_cents
        self.itemized_cents = itemized_cents
        self.delta_cents = itemized_cents - official_cents
        super().__init__(
            "moneyflow reconciliation failed for %s: itemized non-memo disbursements %s "
            "exceed official total disbursements %s by %s. "
            "Child edges plus a residual bucket would need a negative plug, "
            "so no shard was written."
            % (committee_id, cents_to_decimal(itemized_cents), cents_to_decimal(official_cents),
               cents_to_decimal(self.delta_cents))
        )


def cents_to_decimal(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


def money_to_cents(raw):
    """Parse an FEC dollar field. Blank is missing (None), not zero."""
    from decimal import Decimal, ROUND_HALF_UP
    s = (raw or "").strip().replace(",", "").replace("$", "")
    if s == "":
        return None
    try:
        quant = (Decimal(s) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except Exception:
        return None
    return int(quant)


def parse_fec_date(raw):
    """MMDDYYYY or MM/DD/YYYY. Unparseable values are None, not guessed."""
    s = (raw or "").strip()
    if not s:
        return None
    try:
        if "/" in s:
            m, d, y = s.split("/")
            return date(int(y), int(m), int(d)).isoformat()
        if len(s) == 8 and s.isdigit():
            return date(int(s[4:8]), int(s[0:2]), int(s[2:4])).isoformat()
    except ValueError:
        return None
    return None


def in_cycle(iso):
    return bool(iso) and "2025-01-01" <= iso <= "2026-12-31"


def is_memo(code):
    return (code or "").strip().upper() == "X"


def txn_class(code):
    """'out', 'in', or 'unknown'. Unknown is not treated as a disbursement."""
    code = (code or "").strip().upper()
    if code in DISBURSEMENT_TYPES:
        return "out"
    if code in RECEIPT_TYPES:
        return "in"
    return "unknown"


def claim(text, value, excerpt, source_url, check, retrieved_at, *key_parts):
    """Same object shape as ingest/build.py claim records."""
    parts = key_parts if key_parts else (text, source_url, json.dumps(check, sort_keys=True))
    digest = hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:14]
    obj = {
        "id": "c_" + digest,
        "text": text,
        "value": value,
        "excerpt": excerpt,
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "check": check,
        "retrieved_at": retrieved_at,
        "status": "unverified",
    }
    missing = [k for k in CLAIM_KEYS if k not in obj or obj[k] in ("", None)]
    if missing:
        raise RuntimeError("claim missing %s" % ",".join(missing))
    return obj


def image_url(image):
    image = (image or "").strip()
    if IMAGE_NUM.match(image):
        return "https://docquery.fec.gov/cgi-bin/fecimg/?" + image
    return None


def committee_url(committee_id):
    return "https://www.fec.gov/data/committee/%s/?cycle=%d&tab=spending" % (committee_id, CYCLE)


def _norm_name(name):
    return " ".join((name or "").upper().split())


def _digest(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def business_key(name):
    return "business:" + _digest(_norm_name(name))


def named_committee_key(kind, name):
    return "named:%s:%s" % (kind, _digest(kind + "|" + _norm_name(name)))


def kind_from_codes(committee_type, designation):
    if committee_type in PARTY_COMMITTEE_TYPES:
        return "party"
    if committee_type in CANDIDATE_COMMITTEE_TYPES or designation in AUTHORIZED_DESIGNATIONS:
        return "candidate_committee"
    return "committee"


def kind_from_entity(entity):
    if entity == "PTY":
        return "party"
    if entity == "CCM":
        return "candidate_committee"
    return "committee"


def edge_kind_for(txn_type, category, node_kind):
    if node_kind == "residual":
        return "reported disbursement"
    if txn_type:
        if txn_type in CONTRIBUTION_TYPES:
            return "reported contribution"
        if txn_type in TRANSFER_TYPES:
            return "reported transfer"
        if node_kind == "business":
            return "spent"
        return "reported disbursement"
    if category == "008":
        return "reported transfer"
    if category == "011":
        return "reported contribution"
    if node_kind == "business":
        return "spent"
    return "reported disbursement"


def _clean_name(name):
    name = " ".join((name or "").split())
    if not name or len(name) > 200:
        return None
    return name


def classify_payee(entity, other_id, name, txn_type, category, master):
    """Decide the payee. People and unclear rows carry no name and no address.

    master maps committee id -> dict with name, committee_type, designation.
    A candidate id in OTHER_ID is not a recipient (independent-expenditure rows
    use that column for the candidate the expenditure is about).
    """
    entity = (entity or "").strip().upper()
    other_id = (other_id or "").strip().upper()
    txn_type = (txn_type or "").strip().upper() or None
    category = (category or "").strip() or None
    other_is_committee = bool(COMMITTEE_ID.match(other_id))
    # Candidate ids identify a person. They are never copied onto a node.
    if CANDIDATE_ID.match(other_id):
        other_id_for_link = ""
    else:
        other_id_for_link = other_id if other_is_committee else ""

    if entity in PERSON_ENTITY:
        return _bucket("individuals", txn_type, category)

    if entity == "ORG":
        if other_id_for_link and other_id_for_link in master:
            return _bucket("unclear", txn_type, category)
        cleaned = _clean_name(name)
        if not cleaned:
            return _bucket("unclear", txn_type, category)
        node_kind = "business"
        return {
            "bucket": None,
            "payee_key": business_key(cleaned),
            "edge_kind": edge_kind_for(txn_type, category, node_kind),
            "node_kind": node_kind,
            "name": cleaned,
            "official_id": None,
            "terminal": True,
            "purpose_code": txn_type or category,
        }

    if entity in COMMITTEE_ENTITY:
        return _committee_payee(entity, other_id_for_link, name, txn_type, category, master)

    # Blank or unrecognized entity type: do not guess from the name or from OTHER_ID.
    return _bucket("unclear", txn_type, category)


def _bucket(bucket, txn_type, category):
    return {
        "bucket": bucket,
        "payee_key": "residual:" + bucket,
        "edge_kind": "reported disbursement",
        "node_kind": "residual",
        "name": None,
        "official_id": None,
        "terminal": True,
        "purpose_code": txn_type or category,
    }


def _committee_payee(entity, committee_id, name, txn_type, category, master):
    info = master.get(committee_id) if committee_id else None
    if info:
        node_kind = kind_from_codes(info.get("committee_type") or "", info.get("designation") or "")
        display = _clean_name(info.get("name")) or _clean_name(name)
        key = "committee:" + committee_id
        official_id = committee_id
    elif committee_id:
        node_kind = kind_from_entity(entity)
        display = _clean_name(name)
        key = "committee:" + committee_id
        official_id = committee_id
    else:
        display = _clean_name(name)
        if not display:
            return _bucket("unclear", txn_type, category)
        node_kind = kind_from_entity(entity)
        key = named_committee_key(node_kind, display)
        official_id = None
    return {
        "bucket": None,
        "payee_key": key,
        "edge_kind": edge_kind_for(txn_type, category, node_kind),
        "node_kind": node_kind,
        "name": display,
        "official_id": official_id,
        "terminal": False,
        "purpose_code": txn_type or category,
    }


def parse_master_line(line):
    """Committee master columns used here. Treasurer, street, city, ZIP, and candidate id are not read."""
    c = line.rstrip("\r\n").split("|")
    if len(c) < 15:
        return None
    cid = c[0].strip()
    if not COMMITTEE_ID.match(cid):
        return None
    state = c[6].strip().upper()
    connected = c[13].strip()
    return {
        "committee_id": cid,
        "name": c[1].strip(),
        "designation": c[8].strip(),
        "committee_type": c[9].strip(),
        "party": c[10].strip(),
        "org_type": c[12].strip(),
        "connected_organization": connected or None,
        "state": state if len(state) == 2 and state.isalpha() else None,
    }


def parse_webk_line(line):
    """PAC and party summary. Individual-contribution and refund columns are not read."""
    c = line.rstrip("\r\n").split("|")
    if len(c) < 27:
        return None
    cid = c[0].strip()
    if not COMMITTEE_ID.match(cid):
        return None
    return {
        "committee_id": cid,
        "name": c[1].strip(),
        "committee_type": c[2].strip(),
        "designation": c[3].strip(),
        "receipts_cents": money_to_cents(c[5]),
        "disbursements_cents": money_to_cents(c[12]),
        "coverage_end": parse_fec_date(c[26]),
    }


def oth_parts(line):
    """Positional fields for itoth. Address, employer, occupation, and memo text are not returned."""
    c = line.rstrip("\r\n").split("|")
    if len(c) < 21:
        return None
    return {
        "committee_id": c[0].strip(),
        "image": c[4].strip(),
        "txn_type": c[5].strip().upper(),
        "entity": c[6].strip().upper(),
        "name": c[7].strip(),
        "date": parse_fec_date(c[13]),
        "amount_cents": money_to_cents(c[14]),
        "other_id": c[15].strip().upper(),
        "file_num": c[17].strip(),
        "memo": c[18].strip(),
        "sub_id": c[20].strip(),
    }


def pas2_parts(line):
    """Positional fields for itpas2. The candidate-id column is not returned."""
    c = line.rstrip("\r\n").split("|")
    if len(c) < 22:
        return None
    return {
        "committee_id": c[0].strip(),
        "image": c[4].strip(),
        "txn_type": c[5].strip().upper(),
        "entity": c[6].strip().upper(),
        "name": c[7].strip(),
        "date": parse_fec_date(c[13]),
        "amount_cents": money_to_cents(c[14]),
        "other_id": c[15].strip().upper(),
        "file_num": c[18].strip(),
        "memo": c[19].strip(),
        "sub_id": c[21].strip(),
    }


def oppexp_parts(line):
    """Positional fields for oppexp. City, state, ZIP, free-text purpose, and memo text are not returned."""
    c = line.rstrip("\r\n").split("|")
    if len(c) < 22:
        return None
    return {
        "committee_id": c[0].strip(),
        "image": c[4].strip(),
        "txn_type": None,
        "entity": c[20].strip().upper(),
        "name": c[8].strip(),
        "date": parse_fec_date(c[12]),
        "amount_cents": money_to_cents(c[13]),
        "other_id": "",
        "category": c[16].strip(),
        "file_num": c[22].strip() if len(c) > 22 else "",
        "memo": c[18].strip(),
        "sub_id": c[21].strip(),
    }


def over_official(itemized_cents, official_cents):
    """True when positive itemized dollars do not fit under the official total.

    A negative official total with no itemized rows is a residual, not an overage.
    """
    return itemized_cents > official_cents and itemized_cents > 0


def select_pilot(rows):
    """Neutral pilot set.

    rows are dicts: committee_id, name, party, committee_type, designation,
    org_type, disbursements_cents, itemized_count, type_conflict, reconciled.

    Major-party side: the three largest party-qualified (type Y) committees
    for DEM and for REP, by official total disbursements, among rows that
    reconciled. No-party side: for each FEC interest-group category, the
    largest designation-U PAC of type Q, V, or W whose party code is blank,
    that reconciled, and that has at least one itemized non-memo disbursement.
    Party code UNK and third-party codes are not treated as nonpartisan.
    """
    chosen = []
    eligible = [r for r in rows if r.get("reconciled") and not r.get("type_conflict") and r.get("disbursements_cents") is not None]
    for party in ("DEM", "REP"):
        pool = [r for r in eligible if r.get("committee_type") == "Y" and r.get("party") == party]
        pool.sort(key=lambda r: (-r["disbursements_cents"], r["committee_id"]))
        for r in pool[:3]:
            chosen.append({
                "committee_id": r["committee_id"],
                "rule": "party-qualified-top3",
                "reason": (
                    "One of the three party-qualified committees (committee type Y) "
                    "with party code %s and the largest official total disbursements."
                    % party
                ),
            })
    for org in ("C", "L", "M", "T", "V", "W"):
        pool = [
            r for r in eligible
            if r.get("party", "") == ""
            and r.get("designation") == "U"
            and r.get("committee_type") in PAC_TYPES
            and r.get("org_type") == org
            and r.get("itemized_count", 0) > 0
        ]
        pool.sort(key=lambda r: (-r["disbursements_cents"], r["committee_id"]))
        if not pool:
            continue
        r = pool[0]
        label = ORG_TYPE.get(org, org)
        chosen.append({
            "committee_id": r["committee_id"],
            "rule": "org-type-largest-no-party",
            "reason": (
                "Largest PAC (committee type Q, V, or W), designation U, blank party code, "
                "interest-group category %s (%s), with at least one itemized non-memo disbursement, "
                "by official total disbursements."
                % (org, label)
            ),
        })
    return chosen


def _purpose_text(code):
    if not code:
        return None
    if code in TXN_DESC:
        return TXN_DESC[code]
    if code in CATEGORY_DESC:
        return CATEGORY_DESC[code]
    return None


def _file_urls(sources):
    return [FILE_URLS[s] for s in sorted(sources or []) if s in FILE_URLS]


def build_shard(committee, records, retrieved_at, summaries, top_n=TOP_PAYEES):
    """Build one committee shard. records are aggregated payee dicts for this filer only.

    committee: id, name, committee_type, designation, party, org_type,
    connected_organization, state, receipts_cents, disbursements_cents, coverage_end,
    type_conflict, summary_committee_type.
    """
    official = committee["disbursements_cents"]
    if official is None:
        raise ReconciliationError(committee["committee_id"], 0, 0)
    named, individuals, unclear = [], 0, 0
    ind_count = unclear_count = 0
    ind_sources, unclear_sources = set(), set()
    itemized = 0
    for rec in records:
        amt = int(rec["amount_cents"])
        itemized += amt
        bucket = rec.get("bucket")
        if bucket == "individuals":
            individuals += amt
            ind_count += int(rec["count"])
            ind_sources.update(rec.get("sources") or [])
        elif bucket == "unclear":
            unclear += amt
            unclear_count += int(rec["count"])
            unclear_sources.update(rec.get("sources") or [])
        else:
            named.append(rec)
    if over_official(itemized, official):
        raise ReconciliationError(committee["committee_id"], official, itemized)
    gap = official - itemized
    named.sort(key=lambda r: (-int(r["amount_cents"]), r["payee_key"], r["edge_kind"]))
    top = named[:top_n]
    tail = named[top_n:]
    tail_cents = sum(int(r["amount_cents"]) for r in tail)
    other_cents = tail_cents + unclear + gap
    cid = committee["committee_id"]
    children = []
    for rec in top:
        children.append(_named_child(cid, rec, retrieved_at, summaries))
    if individuals != 0:
        children.append(_residual_child(
            cid, "individuals", INDIVIDUAL_BUCKET_NAME, individuals, ind_count,
            ind_sources, retrieved_at, {
                "entity_types": ["IND", "CAN"],
                "payee_names_stored": False,
                "amount_cents": individuals,
                "transaction_count": ind_count,
            },
            "Itemized rows with entity type IND or CAN filed by %s (%s). "
            "The payee name is not stored. Memo code X is excluded. Sum %s across %d rows."
            % (committee["name"], cid, cents_to_decimal(individuals), ind_count),
        ))
    if other_cents != 0:
        children.append(_residual_child(
            cid, "other", OTHER_BUCKET_NAME, other_cents, unclear_count + sum(int(r["count"]) for r in tail),
            unclear_sources, retrieved_at, {
                "payees_below_top_cents": tail_cents,
                "entity_type_unclear_cents": unclear,
                "entity_type_unclear_count": unclear_count,
                "not_in_itemized_files_cents": gap,
                "top_n": top_n,
                "payee_names_stored": False,
                "amount_cents": other_cents,
            },
            "Remainder of reported disbursements for %s (%s) in the %d cycle: "
            "itemized payees below the top %d (%s), rows whose entity type was missing, unrecognized, "
            "or in conflict (%s), and the difference between official total disbursements and "
            "itemized non-memo disbursements in the ingested files (%s). Sum %s. No payee names from the remainder are stored."
            % (committee["name"], cid, CYCLE, top_n, cents_to_decimal(tail_cents),
               cents_to_decimal(unclear), cents_to_decimal(gap), cents_to_decimal(other_cents)),
        ))
    child_sum = sum(int(ch["edge"]["amount_cents"]) for ch in children)
    if child_sum != official:
        raise RuntimeError(
            "shard %s child edges %s do not equal official total %s"
            % (cid, cents_to_decimal(child_sum), cents_to_decimal(official))
        )
    root = _root_node(committee, retrieved_at)
    shard = {
        "schema": "politidex.moneyflow.shard.v1",
        "cycle": CYCLE,
        "fungibility_note": FUNGIBILITY_NOTE,
        "node": root,
        "children": children,
        "reconciliation": {
            "official_total_out": cents_to_decimal(official),
            "official_total_out_cents": official,
            "itemized_cents": itemized,
            "individuals_cents": individuals,
            "unclear_entity_cents": unclear,
            "below_top_cents": tail_cents,
            "not_in_itemized_files_cents": gap,
            "other_bucket_cents": other_cents,
            "child_edge_cents": child_sum,
            "ok": child_sum == official and not over_official(itemized, official),
            "tolerance_cents": 0,
        },
    }
    problems = public_problems(shard)
    if problems:
        raise RuntimeError("shard %s failed the public-record check: %s" % (cid, "; ".join(problems[:8])))
    return shard


def _root_kind(committee):
    if committee.get("type_conflict"):
        return "committee"
    return kind_from_codes(committee.get("committee_type") or "", committee.get("designation") or "")


def _root_node(committee, retrieved_at):
    cid = committee["committee_id"]
    official = committee["disbursements_cents"]
    receipts = committee.get("receipts_cents")
    text = (
        "%s (%s) reported receipts of %s and total disbursements of %s "
        "in the %d cycle, coverage end %s, in the FEC PAC and party summary file."
        % (committee["name"], cid,
           cents_to_decimal(receipts) if receipts is not None else "not reported",
           cents_to_decimal(official), CYCLE, committee.get("coverage_end") or "not reported")
    )
    check = {
        "kind": "fec-committee-summary",
        "file_url": FILE_URLS["webk"],
        "description_url": DESC_URLS["webk"],
        "cycle": CYCLE,
        "committee_id": cid,
        "fields": {
            "TTL_RECEIPTS": receipts,
            "TTL_DISB": official,
            "CVG_END_DT": committee.get("coverage_end"),
        },
        "image_number": None,
        "sub_id": None,
        "filing_id": None,
    }
    if committee.get("type_conflict"):
        check["committee_type_master"] = committee.get("committee_type")
        check["committee_type_summary"] = committee.get("summary_committee_type")
    node = {
        "id": "committee:" + cid,
        "kind": _root_kind(committee),
        "official_id": cid,
        "name": committee["name"],
        "terminal": False,
        "terminal_label": None,
        "period": {"cycle": CYCLE, "coverage_end": committee.get("coverage_end")},
        "reported_in": cents_to_decimal(receipts) if receipts is not None else None,
        "reported_out": cents_to_decimal(official),
        "official_total_out": cents_to_decimal(official),
        "party": committee.get("party") or None,
        "committee_type": committee.get("committee_type") or None,
        "committee_type_label": COMMITTEE_TYPE.get(committee.get("committee_type") or ""),
        "designation": committee.get("designation") or None,
        "designation_label": DESIGNATION.get(committee.get("designation") or ""),
        "org_type": committee.get("org_type") or None,
        "org_type_label": ORG_TYPE.get(committee.get("org_type") or ""),
        "connected_organization": committee.get("connected_organization"),
        "state": committee.get("state"),
        "source": claim(
            text, {"TTL_DISB": official, "TTL_RECEIPTS": receipts}, text,
            committee_url(cid), check, retrieved_at, "root", cid, official, receipts,
        ),
    }
    return node


def _named_child(parent_id, rec, retrieved_at, summaries):
    official_id = rec.get("official_id")
    summary = summaries.get(official_id) if official_id else None
    their_total = summary.get("disbursements_cents") if summary else None
    their_receipts = summary.get("receipts_cents") if summary else None
    their_coverage = summary.get("coverage_end") if summary else None
    name = rec.get("name") or official_id
    node_id = rec["payee_key"]
    kind = rec["node_kind"]
    terminal = bool(rec.get("terminal")) or kind == "business"
    amount = int(rec["amount_cents"])
    count = int(rec["count"])
    purpose = _purpose_text(rec.get("purpose_code"))
    purpose_code = rec.get("purpose_code") if purpose else None
    sample_image = rec.get("image") if IMAGE_NUM.match(rec.get("image") or "") else None
    sample_sub = rec.get("sub_id") if DIGITS.match(rec.get("sub_id") or "") else None
    sample_file = rec.get("file_num") if DIGITS.match(rec.get("file_num") or "") else None
    sources = sorted(rec.get("sources") or [])
    file_urls = _file_urls(sources)
    src_url = image_url(sample_image) or (file_urls[0] if file_urls else FILE_URLS["oth"])
    kind_word = rec["edge_kind"]
    excerpt = (
        "Filer %s, %d cycle: %d itemized rows, memo code X excluded, sum %s, "
        "payee %s. Purpose code %s. Sample image %s, sub_id %s."
        % (parent_id, CYCLE, count, cents_to_decimal(amount), name,
           purpose_code or "mixed or blank", sample_image or "none", sample_sub or "none")
    )
    edge_check = {
        "kind": "fec-itemized-disbursement",
        "cycle": CYCLE,
        "committee_id": parent_id,
        "amount_cents": amount,
        "transaction_count": count,
        "memo_code_x_excluded": True,
        "file_urls": file_urls,
        "description_urls": [DESC_URLS[s] for s in sources if s in DESC_URLS],
        "transaction_type_or_category": purpose_code,
        "sample_image_number": sample_image,
        "sample_sub_id": sample_sub,
        "sample_filing_id": sample_file,
        "edge_kind": kind_word,
    }
    edge = {
        "id": "edge:" + hashlib.sha1((parent_id + "|" + node_id + "|" + kind_word).encode()).hexdigest()[:16],
        "from": "committee:" + parent_id,
        "to": node_id,
        "kind": kind_word,
        "amount": cents_to_decimal(amount),
        "amount_cents": amount,
        "count": count,
        "purpose": purpose,
        "purpose_code": purpose_code,
        "source": claim(
            "%s from %s to %s, sum %s, %d itemized rows."
            % (kind_word.capitalize(), parent_id, name, cents_to_decimal(amount), count),
            amount, excerpt, src_url, edge_check, retrieved_at,
            "edge", parent_id, node_id, kind_word, amount, count,
        ),
    }
    if summary and their_total is not None:
        node_source_url = committee_url(official_id)
        node_text = (
            "%s (%s) has official total disbursements %s in the %d cycle, coverage end %s."
            % (summary.get("name") or name, official_id, cents_to_decimal(their_total),
               CYCLE, their_coverage or "not reported")
        )
        node_check = {
            "kind": "fec-committee-summary",
            "file_url": FILE_URLS["webk"],
            "description_url": DESC_URLS["webk"],
            "cycle": CYCLE,
            "committee_id": official_id,
            "fields": {"TTL_DISB": their_total, "TTL_RECEIPTS": their_receipts, "CVG_END_DT": their_coverage},
            "image_number": None,
            "sub_id": None,
            "filing_id": None,
        }
        node_value = {"TTL_DISB": their_total, "TTL_RECEIPTS": their_receipts}
    else:
        node_source_url = src_url
        node_text = "Payee %s as reported on itemized disbursements filed by %s." % (name, parent_id)
        node_check = dict(edge_check)
        node_check["kind"] = "fec-itemized-payee"
        node_value = {"reported_name": name, "official_id": official_id}
    node = {
        "id": node_id,
        "kind": kind,
        "official_id": official_id,
        "name": name,
        "terminal": terminal,
        "terminal_label": "Spent" if terminal and kind == "business" else None,
        "period": {"cycle": CYCLE, "coverage_end": their_coverage},
        "reported_in": cents_to_decimal(their_receipts) if their_receipts is not None else None,
        "reported_out": cents_to_decimal(their_total) if their_total is not None else None,
        "official_total_out": cents_to_decimal(their_total) if their_total is not None else None,
        "source": claim(node_text, node_value, node_text if summary else excerpt, node_source_url, node_check, retrieved_at,
                        "node", node_id, parent_id, their_total if their_total is not None else amount),
    }
    return {"node": node, "edge": edge}


def _residual_child(parent_id, bucket, label, amount, count, sources, retrieved_at, extra_check, excerpt):
    node_id = "residual:%s:%s" % (parent_id, bucket)
    file_urls = _file_urls(sources) or [FILE_URLS["webk"]]
    check = {
        "kind": "fec-residual-bucket",
        "cycle": CYCLE,
        "committee_id": parent_id,
        "bucket": bucket,
        "file_urls": file_urls,
        "description_urls": [DESC_URLS["webk"], DESC_URLS["oppexp"], DESC_URLS["oth"]],
        "memo_code_x_excluded": True,
        "image_number": None,
        "sub_id": None,
        "filing_id": None,
        "payee_names_stored": False,
    }
    check.update(extra_check)
    src = claim(
        "%s for %s, sum %s." % (label, parent_id, cents_to_decimal(amount)),
        amount, excerpt, file_urls[0], check, retrieved_at,
        "residual", parent_id, bucket, amount,
    )
    node = {
        "id": node_id,
        "kind": "residual",
        "official_id": None,
        "name": label,
        "terminal": True,
        "terminal_label": None,
        "period": {"cycle": CYCLE, "coverage_end": None},
        "reported_in": None,
        "reported_out": None,
        "official_total_out": None,
        "source": src,
    }
    edge = {
        "id": "edge:" + hashlib.sha1((parent_id + "|" + node_id).encode()).hexdigest()[:16],
        "from": "committee:" + parent_id,
        "to": node_id,
        "kind": "reported disbursement",
        "amount": cents_to_decimal(amount),
        "amount_cents": amount,
        "count": count,
        "purpose": None,
        "purpose_code": None,
        "source": src,
    }
    return {"node": node, "edge": edge}


def public_problems(obj, banned_substrings=()):
    """Return human-readable problems. Does not include the offending private value."""
    problems = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k.lower() in FORBIDDEN_KEYS:
                    problems.append("%s: forbidden key %s" % (path, k))
                walk(v, path + "." + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (path, i))
        elif isinstance(node, str):
            low = node.lower()
            for phrase in BANNED_PHRASES:
                if phrase in low:
                    problems.append("%s: banned wording" % path)
                    break
            for secret in ("api_key=", "data_gov_api_key", "demo_key"):
                if secret in low:
                    problems.append("%s: secret-like token" % path)
                    break
            for needle in banned_substrings:
                if needle and needle in node:
                    problems.append("%s: private string present" % path)
                    break
    walk(obj, "$")
    return problems


def wording_document():
    return {
        "fungibility_note": FUNGIBILITY_NOTE,
        "edge_kinds": list(EDGE_KINDS),
        "individual_bucket_name": INDIVIDUAL_BUCKET_NAME,
        "other_bucket_name": OTHER_BUCKET_NAME,
        "terminal_vendor_label": "Spent",
        "top_payees": TOP_PAYEES,
        "cycle": CYCLE,
    }
