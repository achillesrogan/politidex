"""LDA match rules used by connections_lda.py and the match-validation tests.

A verified excerpt only proves the text exists in the filing. These rules decide
whether that text actually refers to this member or this member's 119th-Congress bill.
Ambiguous matches are returned as 'review' (not published). Clear mismatches are 'reject'.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Iterable

# Case-sensitive bill prefixes. "customers. 2024" and "Nos. 34" must not become S. 2024 / S. 34.
# Longer forms first. Senate "S." cannot follow a letter (or "U.").
BILL_RE = re.compile(
    r"(?<![A-Za-z])(?P<label>"
    r"H\.?\s*J\.?\s*Res\.?\s*(?P<hjres>\d+)"
    r"|S\.?\s*J\.?\s*Res\.?\s*(?P<sjres>\d+)"
    r"|H\.?\s*Con\.?\s*Res\.?\s*(?P<hconres>\d+)"
    r"|S\.?\s*Con\.?\s*Res\.?\s*(?P<sconres>\d+)"
    r"|H\.?\s*Res\.?\s*(?P<hres>\d+)"
    r"|S\.?\s*Res\.?\s*(?P<sres>\d+)"
    r"|H\.?\s*R\.?\s*(?P<hr>\d+)"
    r"|(?<![Uu.])S\.\s*(?P<s>\d+)"
    r")(?!\s*/\s*\d)"
)
TYPE_FROM_GROUP = {
    "hjres": "HJRES", "sjres": "SJRES", "hconres": "HCONRES", "sconres": "SCONRES",
    "hres": "HRES", "sres": "SRES", "hr": "HR", "s": "S",
}
DISPLAY = {
    "HR": "H.R.", "S": "S.", "HJRES": "H.J.Res.", "SJRES": "S.J.Res.",
    "HCONRES": "H.Con.Res.", "SCONRES": "S.Con.Res.", "HRES": "H.Res.", "SRES": "S.Res.",
}
# Unambiguous prefixes can keep a year-like number if corroborated; bare "S." cannot.
UNAMBIGUOUS = {"HR", "HJRES", "SJRES", "HCONRES", "SCONRES", "HRES", "SRES"}
YEAR_LIKE = range(2000, 2031)

PRIOR_CONGRESS_RE = re.compile(
    r"(?i)\b(?:11[0-8](?:th|st|nd|rd)\s+Congress)\b"
    r"|\bP\.?\s*L\.?\s*11[0-8]-\d+"
    r"|\bPublic\s+Law\s+11[0-8]-\d+"
)

TITLE_SEN = re.compile(r"(?i)^(?:Senator|Sen\.)$")
TITLE_REP = re.compile(r"(?i)^(?:Representative|Rep\.)$")
TITLE_CMAN = re.compile(r"(?i)^Congressman$")
TITLE_CWOMAN = re.compile(r"(?i)^Congresswoman$")
TITLE_CPERSON = re.compile(r"(?i)^Congressperson$")
TITLE_HON = re.compile(r"(?i)^Hon\.$")
TITLE_ANY = r"(?:Senator|Sen\.|Representative|Rep\.|Congressman|Congresswoman|Congressperson|Hon\.)"

# A following capitalized word after title+surname means a different person's first+last.
FOLLOWING_NAME = r"(?!\s+[A-Z][a-zA-Z]+)"

PERIOD_RANGE = {
    "first_quarter": (1, 1, 3, 31),
    "second_quarter": (4, 1, 6, 30),
    "third_quarter": (7, 1, 9, 30),
    "fourth_quarter": (10, 1, 12, 31),
    "mid_year": (1, 1, 6, 30),
    "year_end": (7, 1, 12, 31),
}

STOPWORDS = {
    "act", "the", "of", "and", "to", "for", "a", "an", "in", "on", "by", "or", "with",
    "from", "this", "that", "bill", "resolution", "joint", "concurrent", "amendment",
    "amendments", "united", "states", "american", "america", "act's",
    "appropriations", "appropriation", "retirement", "health", "healthcare",
    "veterans", "veteran", "congressional", "congress", "disapproval", "national",
    "federal", "department", "program", "programs", "service", "services",
    "security", "energy", "education", "assistance", "authorization", "reauthorization",
    "code", "title", "section", "relating", "amend", "provide", "providing",
    "making", "fiscal", "year", "years", "certain", "purposes", "purpose",
    "including", "through", "public", "law", "laws", "house", "senate",
    "government", "office", "committee", "commission", "administration", "agency",
    "available", "further", "continuing", "emergency", "supplemental", "consolidated",
    "official", "support", "supporting", "express", "expressing", "recognize",
    "recognizing", "respect", "respecting", "people", "person", "persons",
    "child", "children", "family", "families", "worker", "workers", "patient",
    "patients", "care", "protection", "protect", "protecting", "improvement",
    "improve", "improving", "reform", "reforms", "access", "prevention",
    "research", "development", "community", "communities", "rural", "urban",
    "local", "state", "county", "city", "tax", "taxes", "credit", "credits",
    "fund", "funds", "funding", "grant", "grants", "loan", "loans", "insurance",
    "benefit", "benefits", "income", "defense", "military", "armed", "forces",
    "foreign", "affairs", "trade", "commerce", "justice", "immigration", "border",
    "homeland", "intelligence", "judiciary", "finance", "financial", "banking",
    "budget", "treasury", "interior", "labor", "transportation", "agriculture",
    "agricultural", "environmental", "environment", "housing", "atlantic",
    "pacific", "north", "south", "east", "west", "new", "old",
    # Common policy topic words: not enough, alone, to identify a bill
    "water", "waters", "liability", "chemical", "chemicals", "substance",
    "substances", "climate", "carbon", "infrastructure", "medicare", "medicaid",
    "opioid", "opioids", "fentanyl", "cannabis", "marijuana", "vaccine",
    "vaccines", "privacy", "cyber", "cybersecurity", "broadband",
    "semiconductor", "semiconductors", "aviation", "highway", "transit",
    "pollution", "waste", "nuclear", "renewable", "digital", "crypto",
    "cryptocurrency", "firearm", "firearms", "biosolids", "pfas", "pfoa",
    "pfos",
}
GENERIC_ACRONYMS = {
    "ACT", "THE", "AND", "FOR", "USA", "US", "USC", "HHS", "DOD", "DOJ", "DHS",
    "DOT", "EPA", "FBI", "CIA", "OMB", "CBO", "GAO", "CRS", "FY", "FYS", "III",
    "II", "IV", "IRA", "ARPA",
    # Agencies and common offices
    "FDA", "CDC", "NIH", "USDA", "HUD", "IRS", "SSA", "SEC", "FTC", "FCC",
    "NLRB", "OSHA", "CMS", "ICE", "CBP", "TSA", "FEMA", "NASA", "NOAA", "NSF",
    "DOE", "DOI", "DOL", "DOC", "VA", "SBA", "EEOC", "NSA", "ATF", "DEA",
    "CISA", "OPM", "GSA", "NTSB", "FERC", "NRC", "CFPB", "FDIC", "OCC",
    "CFTC", "OFAC", "USCIS", "USTR",
    # Common policy, chemical, health, and benefits topic acronyms
    "PFAS", "PFOA", "PFOS", "PCBS", "PCB", "GHG", "GHGS", "VOC", "VOCS",
    "COVID", "HIV", "AIDS", "RSV", "HPV", "MRSA", "PTSD", "ADHD", "OCD",
    "COPD", "HIPAA", "ACA", "CHIP", "SNAP", "WIC", "TANF", "SSI", "SSDI",
    "FAFSA", "EITC", "NEPA", "FOIA", "CERCLA", "RCRA", "TSCA", "FIFRA",
    "FMLA", "ERISA", "FLSA", "NLRA", "FISA", "CFIUS", "ITAR", "GDPR", "CCPA",
    "ESG", "DEI", "STEM", "LNG", "WHO", "NATO", "OECD", "IMF", "WTO",
    "USEPA",
}

def is_generic_acronym(token: str | None) -> bool:
    """True for agency names, Roman numerals, and common policy/topic acronyms."""
    if not token:
        return True
    t = token.strip()
    return t in GENERIC_ACRONYMS or t.lower() in STOPWORDS

FIRST_VARIANT_GROUPS = [
    {"robert", "rob", "bob", "bobby", "robbie"},
    {"michael", "mike", "mikey"},
    {"william", "will", "bill", "billy", "willie", "liam"},
    {"elizabeth", "liz", "beth", "betty", "eliza", "lizzy"},
    {"john", "jack", "johnny", "jon"},
    {"richard", "dick", "rick", "rich", "ricky"},
    {"james", "jim", "jimmy", "jamie"},
    {"thomas", "tom", "tommy"},
    {"charles", "chuck", "charlie", "chas"},
    {"joseph", "joe", "joey"},
    {"edward", "ed", "eddie", "ted", "teddy"},
    {"andrew", "andy", "drew"},
    {"christopher", "chris"},
    {"kimberly", "kim", "kimmy"},
    {"katherine", "kate", "kathy", "katie", "cathy", "catherine"},
    {"margaret", "maggie", "meg", "peggy", "marge"},
    {"deborah", "deb", "debbie"},
    {"jennifer", "jen", "jenny"},
    {"stephanie", "steph"},
    {"matthew", "matt"},
    {"anthony", "tony"},
    {"benjamin", "ben", "benny"},
    {"samuel", "sam", "sammy"},
    {"daniel", "dan", "danny"},
    {"jonathan", "jon", "jonny"},
    {"nicholas", "nick", "nicky"},
    {"patrick", "pat", "paddy"},
    {"timothy", "tim", "timmy"},
    {"gregory", "greg"},
    {"lawrence", "larry", "laurence"},
    {"alexander", "alex"},
    {"stephen", "steve", "steven"},
    {"ronald", "ron", "ronnie"},
    {"donald", "don", "donnie"},
    {"gerald", "gerry", "jerry"},
    {"peter", "pete"},
    {"walter", "walt"},
    {"francis", "frank", "frankie"},
    {"frederick", "fred", "freddy"},
    {"susan", "sue", "susie"},
    {"nancy", "nan"},
    {"patricia", "pat", "patty", "tricia"},
    {"barbara", "barb", "barbie"},
    {"virginia", "ginny", "ginger"},
    {"judith", "judy"},
    {"christine", "chris", "christy"},
    {"rebecca", "becky", "becca"},
    {"philip", "phil", "phillip"},
    {"george", "geo"},
    {"henry", "hank", "harry"},
    {"harold", "hal", "harry"},
    {"albert", "al", "bert"},
    {"eugene", "gene"},
    {"raymond", "ray"},
    {"kenneth", "ken", "kenny"},
    {"leonard", "len", "lenny", "leo"},
    {"bernard", "bernie"},
    {"maximilian", "max", "maxwell"},
]


@dataclass
class MemberRec:
    bioguide: str
    official: str
    first: str
    last: str
    firsts: tuple  # lowercased given-name variants
    last_lower: str
    chambers: frozenset  # {"sen", "rep"} from any official term
    gender: str  # "M", "F", or ""
    surname_collision: bool
    states: frozenset = field(default_factory=frozenset)
    term_years: tuple = ()  # ((start_year, end_year, chamber, state), ...)
    first_last_collisions: tuple = ()  # other legislators sharing a first+last variant


@dataclass
class BillHit:
    typ: str
    number: str
    label: str
    start: int
    end: int
    raw: str
    reject_reason: str | None = None


@dataclass
class PositionHit:
    bioguide: str
    official: str
    matched: str
    kind: str  # official, first_last, title_first_last, title_last, office_title_last, initial_last
    start: int
    end: int
    decision: str  # publish, review, reject
    reason: str




def first_variants(*names: str) -> set[str]:
    out = {n.strip().lower() for n in names if n and n.strip()}
    out -= {"", "jr", "sr", "ii", "iii", "iv"}
    grow = set(out)
    for g in FIRST_VARIANT_GROUPS:
        if grow & g:
            grow |= g
    return {x for x in grow if x}


def _term_years(terms) -> tuple:
    out = []
    for t in terms or []:
        typ = (t.get("type") or "")[:3]
        if typ not in ("sen", "rep"):
            continue
        try:
            start = int(str(t.get("start") or "")[:4])
        except ValueError:
            continue
        end_raw = str(t.get("end") or "")[:4]
        try:
            end = int(end_raw) if end_raw else start + 2
        except ValueError:
            end = start + 2
        out.append((start, end, typ, (t.get("state") or "").upper()))
    return tuple(out)


STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}
STATE_ABBR = set(STATE_NAMES.values())

_STATE_TAG_RE = re.compile(
    r"\(\s*(?:[DRI]\s*[-–]?\s*)?([A-Za-z.]{2,}(?:\.[A-Za-z]{1,2})?)\s*(?:[-–]\s*\d{1,2})?\s*\)"
    r"|(?<![A-Za-z])([DRI])\s*[-–]\s*([A-Z]{2})\b",
    re.I,
)
_OF_STATE_RE = re.compile(
    r"\bof\s+(" + "|".join(re.escape(n) for n in sorted(STATE_NAMES, key=len, reverse=True)) + r")\b",
    re.I,
)
_TITLE_BEFORE_RE = re.compile(
    r"(?i)(U\.?S\.?\s+Senator|US\s+Senator|Senator|Sen\.|Representative|Reps\.|Rep\.|"
    r"Congressman|Congresswoman|Congressperson|Hon\.)\s*$"
)
_YEAR_SPAN_RE = re.compile(
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(?:(\d{1,2})/)?(\d{4}|\d{2})"
    r"\s*[-–/]\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(?:(\d{1,2})/)?(\d{4}|\d{2})",
    re.I,
)
_SINGLE_YEAR_RE = re.compile(
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+)?(20\d{2}|19\d{2})",
    re.I,
)


def _norm_state_token(tok: str) -> str | None:
    s = re.sub(r"[^A-Za-z]", "", tok or "").upper()
    if s in STATE_ABBR:
        return s
    return STATE_NAMES.get((tok or "").lower().replace(".", " ").strip())


def state_tags(text: str) -> set[str]:
    found: set[str] = set()
    for m in _STATE_TAG_RE.finditer(text or ""):
        tok = m.group(1) or m.group(3) or ""
        st = _norm_state_token(tok)
        if st:
            found.add(st)
    for m in _OF_STATE_RE.finditer(text or ""):
        st = STATE_NAMES.get(m.group(1).lower())
        if st:
            found.add(st)
    return found


def years_in_text(text: str) -> list[tuple[int, int]]:
    spans = []
    used = set()
    for m in _YEAR_SPAN_RE.finditer(text or ""):
        a, b = m.group(2), m.group(4)
        if not a or not b:
            continue
        def yr(x):
            n = int(x)
            if n < 100:
                n = 2000 + n if n <= 40 else 1900 + n
            return n
        ya, yb = yr(a), yr(b)
        if yb < ya:
            yb = ya
        spans.append((ya, yb))
        used.add((m.start(), m.end()))
    for m in _SINGLE_YEAR_RE.finditer(text or ""):
        if any(a <= m.start() and m.end() <= b for a, b in used):
            continue
        y = int(m.group(1))
        spans.append((y, y))
    return spans


def years_overlap(spans: list[tuple[int, int]], terms: list[tuple[int, int]]) -> bool:
    for a, b in spans:
        for c, d in terms:
            if a <= d and c <= b:
                return True
    return False


def clause_around(text: str, start: int, end: int) -> str:
    """The semicolon- or slash-delimited clause that contains the match."""
    text = text or ""
    left = max(text.rfind(";", 0, start), text.rfind("//", 0, start))
    if left < 0:
        left = 0
    else:
        left = left + (2 if text[left:left+2] == "//" else 1)
    rights = [i for i in (text.find(";", end), text.find("//", end)) if i >= 0]
    right = min(rights) if rights else len(text)
    return text[left:right].strip()


def title_before(text: str, start: int) -> str | None:
    pre = (text or "")[:start]
    m = _TITLE_BEFORE_RE.search(pre)
    if not m:
        return None
    t = m.group(1)
    if re.match(r"(?i)reps?\.?", t):
        return "Rep."
    if re.match(r"(?i)(u\.?s\.?\s+senator|us\s+senator)", t):
        return "Senator"
    return t


def _collision_chambers(coll) -> set:
    return set(coll[1]) if len(coll) > 1 else set()


def _collision_states(coll) -> set:
    return set(coll[0]) if coll else set()


def _collision_years(coll) -> list[tuple[int, int]]:
    return [(a, b) for a, b, *_ in (coll[2] if len(coll) > 2 else ())]


def refine_position_decision(text: str, hit: "PositionHit", member: MemberRec) -> tuple[str, str]:
    """Apply title, chamber, state-tag, and service-year checks to every match kind."""
    decision, reason = hit.decision, hit.reason
    title_kinds_never_publish = hit.kind in ("title_last", "office_title_last", "initial_last")
    clause = clause_around(text or "", hit.start, hit.end)
    nearby = (text or "")[max(0, hit.start - 40):min(len(text or ""), hit.end + 30)]
    title = title_before(text or "", hit.start)
    if not title and hit.kind in ("title_first_last", "title_last", "office_title_last"):
        # group 1 is the title for those patterns
        m = re.match(r"(?i)(?:office of\s+)?(" + TITLE_ANY + r")", hit.matched or "")
        if m:
            title = m.group(1)
            if re.match(r"(?i)reps?\.?", title):
                title = "Rep."
    if title:
        ok, why = title_fits(title, member)
        if not ok:
            return "reject", why
    tags = state_tags(clause) or state_tags(nearby)
    if tags and member.states and not (tags & set(member.states)):
        return "reject", "state tag does not match this member's service"
    spans = years_in_text(clause)
    member_years = [(a, b) for a, b, *_ in member.term_years]
    others = member.first_last_collisions or ()
    if spans and member_years and not years_overlap(spans, member_years):
        return "reject", "service years in the excerpt do not overlap this member's terms"
    if title_kinds_never_publish:
        if decision == "reject":
            return decision, reason
        return "review", reason
    if not others:
        return decision, reason
    # First+last (or nickname) is shared with another legislator.
    if tags and member.states and (tags & set(member.states)):
        others_tagged = [o for o in others if tags & _collision_states(o)]
        if not others_tagged:
            return "publish", "state tag uniquely matches this member"
    if spans:
        this_ov = years_overlap(spans, member_years)
        others_ov = any(years_overlap(spans, _collision_years(o)) for o in others)
        if this_ov and not others_ov:
            return "publish", "service years uniquely match this member"
        if others_ov and this_ov:
            # still maybe unique chamber
            pass
        elif not this_ov:
            return "reject", "service years in the excerpt do not overlap this member's terms"
    if title:
        ok, why = title_fits(title, member)
        if ok:
            # chamber implied by title
            ch = None
            if TITLE_SEN.match(title) or re.match(r"(?i)^senator$", title):
                ch = "sen"
            elif TITLE_REP.match(title) or TITLE_CMAN.match(title) or TITLE_CWOMAN.match(title) or TITLE_CPERSON.match(title):
                ch = "rep"
            if ch:
                others_same = [o for o in others if ch in _collision_chambers(o)]
                if not others_same:
                    return "publish", "title chamber uniquely matches this member"
    return "review", "first and last name also matches another legislator; no unique state tag, service years, or chamber to distinguish them"


def attach_name_collisions(members: dict, everyone: dict) -> None:
    """everyone: bioguide -> legislator record (current + historical). Mutates members."""
    index: dict[tuple[str, str], list] = {}
    summaries = {}
    for bio, L in (everyone or {}).items():
        name = (L or {}).get("name") or {}
        last = (name.get("last") or "").strip().lower()
        first = (name.get("first") or "").strip()
        if not last or not first:
            continue
        terms = _term_years((L or {}).get("terms") or [])
        states = frozenset(st for *_, st in terms if st)
        chambers = frozenset(ch for _, _, ch, _ in terms)
        variants = first_variants(first, name.get("nickname") or "", (name.get("official_full") or "").split()[0] if name.get("official_full") else "")
        summaries[bio] = (states, chambers, terms, bio)
        for v in variants:
            index.setdefault((v, last), []).append(bio)
    for mem in members.values():
        keys = {(v, mem.last_lower) for v in first_variants(mem.first, *mem.firsts)}
        others = set()
        for k in keys:
            for bio in index.get(k, []):
                if bio != mem.bioguide:
                    others.add(bio)
        mem.first_last_collisions = tuple(summaries[b] for b in sorted(others) if b in summaries)


def period_end(filing_year, filing_period) -> date | None:
    try:
        year = int(filing_year)
    except (TypeError, ValueError):
        return None
    key = (filing_period or "").strip().lower().replace("-", "_").replace(" ", "_")
    rng = PERIOD_RANGE.get(key)
    if not rng:
        return None
    return date(year, rng[2], rng[3])



def title_words(title: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z']+", title or "")
    return [w for w in words if w.lower() not in STOPWORDS and len(w) >= 4]


def _looks_like_official_long_title(title: str) -> bool:
    return bool(re.match(
        r"(?i)^(to |a bill\b|a resolution\b|directing |expressing |supporting |recognizing |"
        r"providing |making |authorizing |establishing )",
        title or "",
    ))


@lru_cache(maxsize=None)
def load_cached_bill_titles(typ: str, number: str) -> list[dict]:
    typ = (typ or "").lower()
    number = str(number or "")
    path = Path(__file__).resolve().parents[1] / "data" / "raw" / "congress" / "bill-titles" / f"{typ}-{number}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    titles = data.get("titles")
    if isinstance(titles, dict):
        titles = titles.get("item") or titles.get("items") or []
    return titles if isinstance(titles, list) else []



@lru_cache(maxsize=1)
def _popular_short_title_map() -> dict:
    path = Path(__file__).resolve().parents[1] / "data" / "raw" / "congress" / "popular-short-titles.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_popular_short_titles(typ: str | None, number: str | None) -> list[tuple[str, set[str]]]:
    """High-consensus short titles attached to this bill number in LDA filings.

    Used only when Congress.gov has no formal short title (see
    data/raw/congress/popular-short-titles.json).
    """
    if not typ or not number:
        return []
    data = _popular_short_title_map()
    rec = data.get(f"{typ}-{number}") or data.get(f"{typ.upper()}-{number}") or {}
    out = []
    for item in rec.get("titles") or []:
        title = (item.get("title") or "").strip()
        acr = set(item.get("acronyms") or [])
        if title or acr:
            out.append((title, acr))
    return out


def extract_acronyms(titles: list[str]) -> set[str]:
    acr: set[str] = set()
    for t in titles or []:
        for m in re.findall(r"\b([A-Z]{3,8})(?:\s+Act)?\b", t or ""):
            if not is_generic_acronym(m):
                acr.add(m)
        for m in re.findall(r"\(([A-Z]{3,8})\)", t or ""):
            if not is_generic_acronym(m):
                acr.add(m)
    return acr


def bill_short_titles_and_acronyms(official: str | None, typ: str | None = None,
                                   number: str | None = None,
                                   extra_short: list[str] | None = None) -> tuple[list[str], set[str]]:
    shorts: list[str] = []
    if official and not _looks_like_official_long_title(official):
        shorts.append(official)
    for s in extra_short or []:
        if s and s not in shorts:
            shorts.append(s)
    if typ and number:
        for item in load_cached_bill_titles(typ, number):
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            kind = (item.get("titleType") or item.get("type") or "").lower()
            if not title:
                continue
            if "short" in kind or kind.startswith("display"):
                if title and not _looks_like_official_long_title(title) and title not in shorts:
                    shorts.append(title)
            elif official is None and "official" in kind:
                official = title
    acr = extract_acronyms(shorts + ([official] if official else []))
    # Popular names fill a gap only when Congress.gov has no formal short title.
    if not shorts:
        for title, more_acr in load_popular_short_titles(typ, number):
            if title and title not in shorts:
                shorts.append(title)
            acr |= {a for a in more_acr if not is_generic_acronym(a)}
    return shorts, acr


HOUSE_BILL_TYPES = {"HR", "HJRES", "HCONRES", "HRES"}
SENATE_BILL_TYPES = {"S", "SJRES", "SCONRES", "SRES"}

def _is_tight_companion_gap(gap: str) -> bool:
    """True when only punctuation or 'and/or' separates two bill numbers (H.R. 1492/S. 832)."""
    s = BILL_RE.sub(" ", gap or "")
    s = re.sub(r"(?i)\b(and|or|also|&)\b", " ", s)
    s = re.sub(r"[\s,;:/()|&.\-]+", "", s)
    return s == ""


def _are_companions(a: BillHit, b: BillHit) -> bool:
    return ((a.typ in HOUSE_BILL_TYPES and b.typ in SENATE_BILL_TYPES)
            or (a.typ in SENATE_BILL_TYPES and b.typ in HOUSE_BILL_TYPES))


def companion_cluster_bounds(text: str, hit: BillHit, all_hits: list | None = None) -> tuple[int, int]:
    """Start of the first number and end of the last number in a tight House/Senate cluster."""
    text = text or ""
    start, end = hit.start, hit.end
    earlier = sorted((h for h in (all_hits or []) if h.end <= start), key=lambda h: h.start, reverse=True)
    cursor = start
    for prv in earlier:
        gap = text[prv.end:cursor]
        if len(gap) <= 40 and _is_tight_companion_gap(gap) and _are_companions(hit, prv):
            start = prv.start
            cursor = prv.start
            continue
        break
    later = sorted((h for h in (all_hits or []) if h.start >= end), key=lambda h: h.start)
    cursor = end
    for nxt in later:
        gap = text[cursor:nxt.start]
        if len(gap) <= 40 and _is_tight_companion_gap(gap) and _are_companions(hit, nxt):
            end = nxt.end
            cursor = nxt.end
            continue
        break
    return start, end


_ACT_AT_END = re.compile(
    r"(?P<title>(?:[A-Z][A-Za-z0-9']+|the|and|for|of|to|a|an|\([A-Z]{2,10}\))"
    r"(?:\s+(?:[A-Z][A-Za-z0-9']+|the|and|for|of|to|a|an|\([A-Z]{2,10}\))){0,16}"
    r"\s+Act(?:\s+of\s+\d{4})?)\s*$",
    re.I,
)


def preceding_list_title(text: str, hit: BillHit, all_hits: list | None = None) -> str | None:
    """Return the short title immediately before a Title (number) or 'Act H.R. 123' list item.

    Filings that list 'Born-Alive Abortion Survivors Protection Act (H.R. 1061) -
    Protecting Sensitive Locations Act (S. 229)' attach each title to the number
    that follows it, not to the number that precedes it.
    """
    text = text or ""
    cluster_start, _ = companion_cluster_bounds(text, hit, all_hits)
    s = text[:cluster_start].rstrip()
    if s.endswith("("):
        s = s[:-1].rstrip()
    else:
        # Allow only light separators between Act and a bare number, not a period
        # (a period usually ends the previous sentence: 'RESULTS Act. H.R. 1244, Official Title').
        m = re.search(r"[,:\-–—\s]+$", s)
        if m:
            s = s[:m.start()].rstrip()
    m = _ACT_AT_END.search(s)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group("title")).strip()


def _token_soft_eq(obs: str, official: str) -> bool:
    a, b = obs.lower(), official.lower()
    if a == b:
        return True
    # Excerpt often starts mid-word: "ECTING" from "Protecting"
    if len(a) >= 4 and (b.endswith(a) or a.endswith(b)):
        return True
    return False


def preceding_title_matches(observed: str, official: str | None,
                            short_titles: list[str] | None = None,
                            acronyms: set[str] | None = None) -> bool:
    """True when the title before a list number is this bill's short title, allowing a truncated start."""
    if not observed:
        return False
    shorts = list(short_titles or [])
    if official and official not in shorts and not _looks_like_official_long_title(official):
        shorts.append(official)
    if distinctive_title_match(observed, official, shorts, acronyms):
        return True
    obs = _phrase_tokens(observed)
    if len(obs) < 2:
        # coined one-word / acronym titles
        if acronyms and any(not is_generic_acronym(a) and re.search(rf"\b{re.escape(a)}\b", observed) for a in acronyms):
            return True
        if len(obs) == 1 and any(len(_phrase_tokens(t)) == 1 and _token_soft_eq(obs[0], _phrase_tokens(t)[0]) for t in shorts if _phrase_tokens(t)):
            return True
        return False
    candidates = list(shorts)
    if official and official not in candidates:
        candidates.append(official)
    for title in candidates:
        off = _phrase_tokens(title)
        if len(off) < 2:
            continue
        for n in range(len(obs), 1, -1):
            suf = obs[-n:]
            if len(off) < n:
                continue
            chunk = off[-n:]
            if _token_soft_eq(suf[0], chunk[0]) and [t.lower() for t in suf[1:]] == [t.lower() for t in chunk[1:]]:
                return True
    return False


def title_window(text: str, hit: BillHit, all_hits: list | None = None) -> str:
    """Text between this bill number (or its companion cluster) and the next unrelated bill number.

    A tightly bound companion citation (H.R. 1492/S. 832 or H.R. 1492 & S. 832)
    is skipped so a shared short title after the pair stays in the window.
    """
    text = text or ""
    _, cluster_end = companion_cluster_bounds(text, hit, all_hits)
    later_hits = sorted((h for h in (all_hits or []) if h.start >= cluster_end), key=lambda h: h.start)
    end = len(text)
    for nxt in later_hits:
        end = nxt.start
        break
    window = text[cluster_end:end]
    if len(window) > 500:
        window = window[:500]
    return window


def leading_local_titles(window: str) -> tuple[list[str], set[str]]:
    """Distinctive short titles or acronyms attached immediately after the bill number."""
    s = window or ""
    # repeatedly strip leading punctuation, 'the/and/or', and companion bill citations
    while s:
        s = s.lstrip(" \t\n\r,;:/()&.'\"-")
        s = re.sub(r"^(?:and|or|the|aka|known as)\s+", "", s, flags=re.I)
        m = BILL_RE.match(s)
        if m:
            s = s[m.end():]
            continue
        break
    titles: list[str] = []
    acr: set[str] = set()
    # quoted title
    m = re.match(r"[\"']([^\"']{3,120})[\"']", s)
    if m:
        titles.append(m.group(1).strip())
    # Ensuring Pathways to Innovative Cures (EPIC) Act of 2025
    m = re.match(
        r"((?:[A-Z][A-Za-z0-9']+\s+){0,12}(?:[A-Z]{2,8}|[A-Z][A-Za-z0-9']+)(?:\s+Act)?(?:\s+of\s+\d{4})?)",
        s,
    )
    if m:
        titles.append(m.group(1).strip())
    for a in re.findall(r"\b([A-Z]{3,8})(?:\s+Act(?:\s+of\s+\d{4})?)?\b", s[:160]):
        if not is_generic_acronym(a):
            acr.add(a)
    for a in re.findall(r"\(([A-Z]{3,8})\)", s[:160]):
        if not is_generic_acronym(a):
            acr.add(a)
    # drop titles that have no distinctive content
    kept = []
    for title in titles:
        words = _phrase_tokens(title)
        if len(words) >= 2 or (len(words) == 1 and (len(words[0]) >= 4 and words[0].lower() not in STOPWORDS)):
            kept.append(title)
            acr |= extract_acronyms([title])
    return kept, acr


def official_long_title_phrase_match(window: str, official: str | None) -> bool:
    """Match a distinctive multi-word phrase from a long official title, in the local window only."""
    if not window or not official or not _looks_like_official_long_title(official):
        return False
    t = re.sub(r"(?i)^(a bill |an act |to |for the purpose of )+", "", official).strip()
    t = re.sub(r"(?i),?\s+and for other purposes\.?$", "", t).strip()
    words = re.findall(r"[A-Za-z0-9']+", t)
    # need at least 4 consecutive official-title words in the window
    for n in range(min(len(words), 8), 3, -1):
        for i in range(0, len(words) - n + 1):
            chunk = words[i:i + n]
            # skip chunks that are almost all stopwords
            content = [w for w in chunk if w.lower() not in STOPWORDS and len(w) >= 4]
            if len(content) < 3:
                continue
            pat = r"\b" + r"[\s,:'-]+".join(re.escape(w) for w in chunk) + r"\b"
            if re.search(pat, window, re.I):
                return True
    return False


def is_bare_number_list(window: str) -> bool:
    s = BILL_RE.sub(" ", window or "")
    s = re.sub(r"(?i)\b(and|or|plus|also|including|the|of|for|to)\b", " ", s)
    s = re.sub(r"[0-9,;:/.\-()#]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return len(s) < 4


def _phrase_tokens(title: str) -> list[str]:
    """Tokens for a phrase search: keep mid-title words such as Local; drop only weak ends."""
    t = re.sub(r"(?i)\s+act(?:\s+of\s+\d{4})?$", "", title or "").strip()
    t = re.sub(r"(?i)^the\s+", "", t)
    words = re.findall(r"[A-Za-z0-9']+", t)
    weak = {"the", "a", "an", "of", "and", "to", "for"}
    while words and words[0].lower() in weak:
        words.pop(0)
    while words and words[-1].lower() in weak:
        words.pop()
    return words


def distinctive_title_match(window: str, official: str | None,
                            short_titles: list[str] | None = None,
                            acronyms: set[str] | None = None) -> bool:
    """Require a distinctive multi-word short-title phrase or an acronym in the local window."""
    if not window:
        return False
    shorts = list(short_titles or [])
    if official and official not in shorts and not _looks_like_official_long_title(official):
        shorts.append(official)
    for a in (acronyms or extract_acronyms(shorts)):
        if not a or is_generic_acronym(a):
            continue
        if re.search(rf"\b{re.escape(a)}\b", window):
            return True
    for title in shorts:
        words = _phrase_tokens(title)
        if len(words) < 2:
            continue
        pat = r"\b" + r"[\s,:'-]+".join(re.escape(w) for w in words) + r"(?:\s+Act)?\b"
        if re.search(pat, window, re.I):
            return True
    # A coined one-word short title (EPIC Act) after dropping Act
    for title in shorts:
        words = _phrase_tokens(title)
        if len(words) == 1 and len(words[0]) >= 4 and words[0].lower() not in STOPWORDS:
            if re.search(rf'\\b{re.escape(words[0])}\\b', window, re.I):
                return True
    if official_long_title_phrase_match(window, official):
        return True
    return False


def short_title_corroborated(excerpt: str, title: str,
                             short_titles: list[str] | None = None,
                             acronyms: set[str] | None = None) -> bool:
    """Back-compat wrapper: distinctive match against the given excerpt."""
    return distinctive_title_match(excerpt or "", title, short_titles, acronyms)


def parse_bill_mentions(text: str) -> list[BillHit]:
    hits = []
    for m in BILL_RE.finditer(text or ""):
        typ = next((TYPE_FROM_GROUP[g] for g, v in m.groupdict().items()
                    if g in TYPE_FROM_GROUP and v), None)
        num = next((v for g, v in m.groupdict().items()
                    if g in TYPE_FROM_GROUP and v), None)
        if not typ or not num:
            continue
        reason = None
        n = int(num)
        # "Res. 89/25" and similar trailing slash dates
        after = (text or "")[m.end():m.end() + 8]
        if re.match(r"\s*/\s*\d", after):
            reason = "number followed by a slash date or fraction"
        hits.append(BillHit(
            typ=typ, number=str(n), label=f"{DISPLAY[typ]} {n}",
            start=m.start(), end=m.end(), raw=m.group("label"),
            reject_reason=reason,
        ))
    return hits


def nearby_prior_congress(text: str, start: int, end: int, window: int = 180) -> bool:
    a = max(0, start - window)
    b = min(len(text or ""), end + window)
    return bool(PRIOR_CONGRESS_RE.search((text or "")[a:b]))


def decide_bill(hit: BillHit, description: str, bill_title: str | None,
                introduced: str | None, filing_year, filing_period,
                short_titles: list[str] | None = None,
                acronyms: set[str] | None = None,
                all_hits: list | None = None) -> tuple[str, str]:
    """Return (publish|review|reject, reason) for one bill mention against a 119th bill.

    A filing period that ends before the bill was introduced is always rejected.
    Date is a veto only — it never justifies publishing. Publish only when the
    text immediately before the number in a Title (number) list, or the window
    between this bill number and the next, contains a distinctive multi-word
    short title or a Congress.gov acronym. Bare number lists do not publish.
    """
    if hit.reject_reason:
        return "reject", hit.reject_reason
    if nearby_prior_congress(description or "", hit.start, hit.end):
        return "reject", "excerpt cites a 110th–118th Congress law or public law"
    intro = None
    if introduced:
        try:
            intro = date.fromisoformat(introduced[:10])
        except ValueError:
            intro = None
    end = period_end(filing_year, filing_period)
    if intro and end and end < intro:
        return "reject", "filing period ends before the bill was introduced"
    window = title_window(description or "", hit, all_hits)
    shorts, acr = bill_short_titles_and_acronyms(bill_title, hit.typ, hit.number, short_titles)
    if acronyms:
        acr |= {a for a in acronyms if not is_generic_acronym(a)}
    year_like = int(hit.number) in YEAR_LIKE and hit.typ not in UNAMBIGUOUS
    # Title (number) lists attach the title that precedes the number, not the next item.
    prev_title = preceding_list_title(description or "", hit, all_hits)
    if prev_title:
        if preceding_title_matches(prev_title, bill_title, shorts, acr):
            title_ok = True
        else:
            if year_like:
                return "reject", "year-like number with an ambiguous S. prefix"
            return "review", "preceding title in a Title (number) list does not match this bill"
    else:
        title_ok = distinctive_title_match(window, bill_title, shorts, acr)
    if year_like and not title_ok:
        return "reject", "year-like number with an ambiguous S. prefix"
    if is_bare_number_list(window) and not title_ok:
        return "review", "bare bill-number list with no distinctive short title or acronym"
    if title_ok:
        return "publish", "distinctive short title or acronym in the local window"
    return "review", "no distinctive short title or acronym in the local window"



def _different_act_title(excerpt: str, bill_title: str) -> bool:
    acts = re.findall(r"\b([A-Z][A-Za-z0-9'’]+(?:\s+[A-Z][A-Za-z0-9'’]+){0,10}\s+Act)\b", excerpt or "")
    if not acts:
        return False
    tw = {w.lower() for w in title_words(bill_title)}
    for a in acts:
        aw = {w.lower() for w in title_words(a)}
        if tw and aw and (tw & aw):
            return False
    return True


def title_fits(title: str, member: MemberRec) -> tuple[bool, str]:
    t = (title or "").strip()
    if TITLE_HON.match(t) or TITLE_CPERSON.match(t):
        return True, "neutral title"
    if TITLE_SEN.match(t):
        if "sen" in member.chambers:
            return True, "senate service"
        return False, "Senator/Sen. title but member has no Senate service"
    if TITLE_REP.match(t):
        if "rep" in member.chambers:
            return True, "house service"
        return False, "Representative/Rep. title but member has no House service"
    if TITLE_CMAN.match(t):
        if "rep" not in member.chambers:
            return False, "Congressman title but member has no House service"
        if member.gender == "F":
            return False, "Congressman title does not fit a woman member"
        if member.gender and member.gender != "M":
            return False, "Congressman title does not fit member gender"
        return True, "house service and gender"
    if TITLE_CWOMAN.match(t):
        if "rep" not in member.chambers:
            return False, "Congresswoman title but member has no House service"
        if member.gender == "M":
            return False, "Congresswoman title does not fit a man member"
        if member.gender and member.gender != "F":
            return False, "Congresswoman title does not fit member gender"
        return True, "house service and gender"
    return False, "unrecognized title"


def _kinds_for(member: MemberRec) -> list[tuple[str, re.Pattern]]:
    """Stronger kinds first. title_last uses a negative lookahead for a following given name."""
    last = re.escape(member.last)
    firsts = [re.escape(f) for f in sorted(member.firsts, key=len, reverse=True) if f]
    first_alt = "(?:" + "|".join(firsts) + ")" if firsts else re.escape(member.first)
    official = re.escape(member.official)
    title = TITLE_ANY
    pats = [
        ("official", re.compile(rf"(?i){official}")),
        ("title_first_last", re.compile(rf"(?i)({title})\s+({first_alt})\s+({last})")),
        ("first_last", re.compile(rf"(?i)({first_alt})\s+({last})")),
        ("office_title_last", re.compile(rf"(?i)Office of\s+({title})\s+({last}){FOLLOWING_NAME}")),
        ("title_last", re.compile(rf"(?i)({title})\s+({last}){FOLLOWING_NAME}")),
        ("initial_last", re.compile(rf"(?i)\b({re.escape(member.first[0])})\.?\s+({last}){FOLLOWING_NAME}")),
    ]
    return pats


def find_position_hits(text: str, member: MemberRec) -> list[PositionHit]:
    hits = []
    seen_spans = set()
    for kind, pat in _kinds_for(member):
        for m in pat.finditer(text or ""):
            span = (m.start(), m.end())
            # Prefer the stronger kind if it covers the same last-name span.
            if any(a <= m.start() and m.end() <= b for a, b in seen_spans):
                continue
            matched = m.group(0)
            decision, reason = "publish", kind
            if kind in ("title_last", "office_title_last"):
                title = m.group(1)
                ok, why = title_fits(title, member)
                if not ok:
                    decision, reason = "reject", why
                elif member.surname_collision:
                    decision, reason = "review", "title plus surname only; last name also appears in legislators-historical"
                else:
                    decision, reason = "review", "title plus surname only; not first-name corroborated"
            elif kind == "title_first_last":
                title = m.group(1)
                ok, why = title_fits(title, member)
                if not ok:
                    decision, reason = "reject", why
                else:
                    decision, reason = "publish", "title plus first and last name"
            elif kind == "initial_last":
                if member.surname_collision:
                    decision, reason = "review", "initial plus surname with a historical or current surname collision"
                else:
                    decision, reason = "review", "initial plus surname only"
            elif kind in ("official", "first_last"):
                decision, reason = "publish", kind
            seen_spans.add(span)
            hit = PositionHit(
                bioguide=member.bioguide, official=member.official, matched=matched,
                kind=kind, start=m.start(), end=m.end(), decision=decision, reason=reason,
            )
            hit.decision, hit.reason = refine_position_decision(text or "", hit, member)
            hits.append(hit)
    return hits


def last_probe(last_names: Iterable[str]) -> re.Pattern:
    parts = sorted({n for n in last_names if n}, key=len, reverse=True)
    return re.compile(r"(?i)\b(" + "|".join(re.escape(x) for x in parts) + r")\b")


def member_from_legislator(bio, official, L, people_name, collision: bool) -> MemberRec:
    name = (L or {}).get("name") or {}
    first = (name.get("first") or (people_name or official).split()[0]).strip()
    last = (name.get("last") or official.split()[-1]).strip()
    official_full = name.get("official_full") or official
    firsts = {first.lower()}
    if name.get("nickname"):
        firsts.add(str(name["nickname"]).lower())
    if official_full:
        firsts.add(official_full.split()[0].lower())
    if people_name:
        firsts.add(people_name.split()[0].lower())
    firsts = {f for f in firsts if f and " " not in f}
    terms = _term_years((L or {}).get("terms") or [])
    chambers = frozenset(ch for _, _, ch, _ in terms)
    states = frozenset(st for *_, st in terms if st)
    gender = ((L or {}).get("bio") or {}).get("gender") or ""
    firsts |= first_variants(first, name.get("nickname") or "", official_full.split()[0] if official_full else "", (people_name or "").split()[0] if people_name else "")
    firsts = {f for f in firsts if f and " " not in f}
    return MemberRec(
        bioguide=bio, official=official_full or official, first=first, last=last,
        firsts=tuple(sorted(firsts)), last_lower=last.lower(),
        chambers=chambers, gender=gender, surname_collision=collision,
        states=states, term_years=terms,
    )


# Self-registered individual LDA registrants (the compact crawl dropped registrant type).
# A registrant is labeled individual only when its name equals a lobbyist name on a
# filing and the name itself looks like a person — never because it equals the client name.
_ORG_NAME_TOKENS = {
    "INC", "INCORPORATED", "LLC", "LLP", "LTD", "CORP", "CORPORATION", "COMPANY",
    "ASSOCIATION", "ASSOC", "GROUP", "FUND", "COMMITTEE", "UNIVERSITY", "COLLEGE",
    "BANK", "HOSPITAL", "ALLIANCE", "COUNCIL", "FOUNDATION", "SOCIETY", "AGENCY",
    "DEPARTMENT", "BOARD", "BOARDS", "FEDERATION", "UNION", "COALITION", "INSTITUTE",
    "PARTNERS", "PLLC", "TRUST", "AUTHORITY", "COMMISSION", "BUREAU", "INDUSTRIES",
    "SOLUTIONS", "TECHNOLOGIES", "COMMUNICATIONS", "INSURANCE", "CAPITAL", "ADVISORS",
    "ADVISORY", "MANAGEMENT", "CONSULTING", "CONSULTANTS", "STRATEGIES", "STRATEGY",
    "PARTNERSHIP", "VENTURES", "ENTERPRISE", "ENTERPRISES", "NETWORK", "NETWORKS",
    "HOLDINGS", "LABORATORIES", "PHARMACEUTICALS", "CHAMBER", "COOPERATIVE", "LEAGUE",
    "CLUB", "CLUBS", "CENTER", "CENTRE", "CAMPAIGN", "INTERNATIONAL", "NATIONAL",
    "AMERICAN", "SERVICES", "SYSTEM", "SYSTEMS", "HEALTHCARE", "ADVOCACY", "ADVOCATES",
    "COMPANIES", "ASSOCIATES", "PAC", "PC", "PA", "LP",
    "CITIZEN", "CITIZENS", "UNITED", "ACTION", "INITIATIVE", "PROJECT", "VOICES", "WORKS",
    "ORGANIZATION", "ORGANIZATIONS", "ORGANISATION", "ORGANISATIONS",
    "FINANCIAL", "FINANCE", "DAIRY", "ORGANIC", "INNOVATION", "INNOVATIONS",
    "STANDARD", "CAUSE", "PROSPERITY", "PATIENT", "PATIENTS", "HELICOPTERS",
    "EXCHANGE", "ENERGY", "ELECTRIC", "MOTORS", "GLOBAL", "MEDIA", "BRANDS",
    "LOGISTICS", "AIRLINES", "AIRLINE", "HOTELS", "HOTEL", "MARKETS", "MARKET",
    "CITY", "COUNTY", "STATE", "PORT", "TRIBE", "NATION", "NATIONS", "PUEBLO",
    "HEALTH", "SCIENCES", "SCIENCE", "SPACE", "PUBLICATIONS", "CONSERVANCY",
    "CONFERENCE", "INVESTMENTS", "INVESTMENT", "PRODUCTS", "PRODUCT",
    "AMERICA", "AMERICAS", "AIRPORT", "DIAGNOSTICS", "THERAPEUTICS",
    "BIOSOLUTIONS", "AVIATION", "FOODS", "AIRCRAFT", "MATERIALS", "ACADEMY",
    "MINISTRIES", "MINISTRY", "CONTRACTORS", "CONTRACTOR", "AFFILIATES",
    "AFFILIATE", "BROADCASTING", "CORPORATE", "NEWSPAPERS", "NEWSPAPER",
    "HOSPITALS", "GROUPS", "COMMISSIONS", "FUNDS", "LIMITED", "PHARMA",
    "THERAPEUTICS", "BIOSCIENCES", "ROUNDTABLE", "CHARITIES", "CHARITY",
    "MUTUAL", "TELEMATICS", "MACHINES", "FELLOWSHIP", "LABS", "LAW",
    "CONSERVANCY", "FORUM", "DEPOT", "WILDLIFE", "RIGHTS",
}
_PERSON_CONNECTORS = {"OF", "AND", "FOR", "THE", "DBA", "AKA", "FKA"}
_PERSON_PLACE_FIRST = {"CITY", "COUNTY", "STATE", "PORT", "TOWN", "TOWNSHIP", "VILLAGE", "TRIBE", "NATION", "PUEBLO", "MR", "MS", "MRS"}

_SUFFIX_TOKENS = {"JR", "SR", "II", "III", "IV"}
_PERSON_NAME_RE = re.compile(
    r"^[A-Za-z][A-Za-z'.\-]{1,30}"
    r"(?:,\s+[A-Za-z][A-Za-z'.\-]{1,30}(?:\s+[A-Za-z]\.?)?(?:\s+(?:Jr|Sr|II|III|IV)\.?)?"
    r"|(?:\s+[A-Za-z]\.?)?(?:\s+[A-Za-z][A-Za-z'.\-]{1,30}){1,2}(?:\s+(?:Jr|Sr|II|III|IV)\.?)?)$"
)


def norm_person_name(s: str | None) -> str:
    s = re.sub(r"[^A-Za-z,\s]", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip().upper()
    if "," in s:
        last, first = [x.strip() for x in s.split(",", 1)]
        s = f"{first} {last}".strip()
    s = re.sub(r"\b(JR|SR|II|III|IV)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def looks_like_person_name(s: str | None) -> bool:
    raw = re.sub(r"\s+", " ", (s or "")).strip()
    if not raw or re.search(r"\d", raw):
        return False
    if not _PERSON_NAME_RE.match(raw):
        return False
    toks = [t for t in re.findall(r"[A-Za-z]+", raw.upper()) if t not in _SUFFIX_TOKENS]
    if any(t in _ORG_NAME_TOKENS or t in _PERSON_CONNECTORS for t in toks):
        return False
    if toks and toks[0] in _PERSON_PLACE_FIRST:
        return False
    last_deny = {"USA", "US", "CO", "PBC", "ACB", "LLC", "LTD", "INC", "LIST", "SERVICE",
                 "HOUSE", "AIR", "SMA", "NRDS", "ATOMICS", "DYNAMICS", "PAPERBOARD",
                 "INVENTOR", "AUSTRALIA", "JERSEY", "NEVADA", "CALIFORNIA", "FLORIDA",
                 "TEXAS", "ARMORED", "SPEAKS", "CARBON", "FLYING"}
    if toks and toks[-1] in last_deny:
        return False
    # Need at least two name words of 2+ letters (initials alone are not enough).
    if sum(1 for t in toks if len(t) >= 2) < 2:
        return False
    return True


def _person_core(s: str | None) -> tuple[str, str] | None:
    """(first, last) after dropping middle initials and suffixes."""
    n = norm_person_name(s)
    toks = [t for t in n.split() if len(t) > 1]
    if len(toks) < 2:
        return None
    return toks[0], toks[-1]


def names_match_person(a: str | None, b: str | None) -> bool:
    """Match person names allowing a dropped middle initial and first-name variants (Kim/Kimberly)."""
    if not a or not b:
        return False
    if norm_person_name(a) == norm_person_name(b):
        return True
    ca, cb = _person_core(a), _person_core(b)
    if not ca or not cb:
        return False
    if ca[1] != cb[1]:
        return False
    return bool(first_variants(ca[0]) & first_variants(cb[0]))


def is_individual_registrant(registrant_name: str | None, lobbyist_name: str | None = None) -> bool:
    """True only when the registrant name is a person name and matches the lobbyist name."""
    if not looks_like_person_name(registrant_name):
        return False
    return names_match_person(registrant_name, lobbyist_name)


def load_individual_registrant_ids(raw_dir=None) -> set:
    """Registrant IDs whose name equals a lobbyist name on an official filing and looks like a person."""
    from pathlib import Path
    raw_dir = Path(raw_dir) if raw_dir else Path(__file__).resolve().parents[1] / "data" / "raw" / "lda"
    ids: set = set()
    if not raw_dir.exists():
        return ids
    for fp in sorted(raw_dir.glob("*.jsonl")):
        with fp.open() as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                rn = o.get("registrant_name") or ""
                rid = o.get("registrant_id")
                if rid is None or not looks_like_person_name(rn):
                    continue
                nr = norm_person_name(rn)
                for act in o.get("lobbying_activities") or []:
                    for lb in act.get("lobbyists") or []:
                        if names_match_person(rn, lb.get("name") or ""):
                            ids.add(rid)
                            ids.add(str(rid))
                            break
                    else:
                        continue
                    break
    return ids
