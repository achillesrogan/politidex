"""Checkpointed crawl of official LDA quarterly filings, then local matching.

Source: Senate Office of Public Records LDA API, https://lda.gov/api/v1/filings/
Human filing URL: https://lda.gov/filings/public/filing/{uuid}/print/

Quarterly reports (and amendments) for filing years 2025 and 2026 are paged
at the API's maximum page_size of 25. Progress is saved under data/raw/lda/.

Matching (run after or during a crawl):
  * Bill numbers in lobbying_activities[].description against 119th Congress
    bills each current member sponsored or cosponsored (Congress.gov).
  * Covered-position text that names a current member (first and last name, or
    a chamber-appropriate title plus first and last name). Title plus surname
    only is never published: clear mismatches are dropped, and the rest go to
    data/review/. Last name alone is not enough.
  * Bill numbers use case-sensitive prefixes and are published only when the
    excerpt is corroborated as a 119th-Congress bill (short-title word or a
    filing period on or after the bill's introduction). Prior-Congress citations
    and ambiguous year-like numbers are rejected.

The Senate Office of Public Records cannot vouch for the accuracy of this
data after retrieval. Politidex does not use the Senate seal.

Usage:
  python ingest/connections_lda.py --crawl
  python ingest/connections_lda.py --match
"""
from __future__ import annotations
import json, re, sys, time, collections, urllib.parse
import concurrent.futures as cf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import lda_match as M

RAWLDA = RAW / "lda"
PROGRESS = RAWLDA / "progress.json"
MATCH_OUT = BUILD / "connections-lda.json"

API = "https://lda.gov/api/v1/filings/"
PRINT = "https://lda.gov/filings/public/filing/{uuid}/print/"
PAGE_SIZE = 25

# Activity-bearing quarterly types (skip "no activity" Y types).
FILING_TYPES = [
    "Q1", "1T", "1A",
    "Q2", "2T", "2A",
    "Q3", "3T", "3A",
    "Q4", "4T", "4A",
]
YEARS = (2025, 2026)

BILL_RE = M.BILL_RE
TYPE_FROM_GROUP = M.TYPE_FROM_GROUP
DISPLAY = M.DISPLAY

def compact(row):
    """Drop addresses and phones; keep the fields used for matching and cites."""
    acts = []
    for a in row.get("lobbying_activities") or []:
        lobbyists = []
        for lb in a.get("lobbyists") or []:
            pos = (lb.get("covered_position") or "").strip()
            who = lb.get("lobbyist") or {}
            name = " ".join(x for x in (who.get("first_name"), who.get("last_name")) if x).strip()
            lobbyists.append({"name": name, "covered_position": pos})
        acts.append({
            "general_issue_code": a.get("general_issue_code"),
            "general_issue_code_display": a.get("general_issue_code_display"),
            "description": a.get("description") or "",
            "lobbyists": lobbyists,
        })
    reg = row.get("registrant") or {}
    cli = row.get("client") or {}
    uuid = row.get("filing_uuid")
    return {
        "filing_uuid": uuid,
        "api_url": row.get("url") or (f"{API}{uuid}/" if uuid else None),
        "document_url": row.get("filing_document_url") or (PRINT.format(uuid=uuid) if uuid else None),
        "filing_type": row.get("filing_type"),
        "filing_type_display": row.get("filing_type_display"),
        "filing_year": row.get("filing_year"),
        "filing_period": row.get("filing_period"),
        "dt_posted": row.get("dt_posted"),
        "registrant_id": reg.get("id"),
        "registrant_name": (reg.get("name") or "").strip(),
        "client_id": cli.get("id") or cli.get("client_id"),
        "client_name": (cli.get("name") or "").strip(),
        "lobbying_activities": acts,
    }

def period_key(year, ftype):
    return f"{year}-{ftype}"

def jsonl_path(year, ftype):
    return RAWLDA / f"{year}-{ftype}.jsonl"

def load_progress():
    if PROGRESS.exists():
        return read_json(PROGRESS)
    return {"periods": {}, "started": now_iso()}

def save_progress(p):
    p["checkpoint"] = now_iso()
    if _progress_lock:
        with _progress_lock:
            write_json(PROGRESS, p)
    else:
        write_json(PROGRESS, p)

def fetch_page(year, ftype, page):
    q = urllib.parse.urlencode({
        "filing_year": year, "filing_type": ftype,
        "page_size": PAGE_SIZE, "page": page,
    })
    url = API + "?" + q
    st, b = fetch(url, timeout=90, retries=4)
    if st != 200 or not b:
        return st, None
    try:
        return st, json.loads(b)
    except json.JSONDecodeError:
        return st, None

def crawl_period(year, ftype, progress, delay=0.05):
    key = period_key(year, ftype)
    info = progress["periods"].setdefault(key, {"year": year, "filing_type": ftype, "next_page": 1, "count": None, "pages": None, "written": 0, "done": False})
    if info.get("done"):
        print(f"skip complete {key}", flush=True)
        return info
    outp = jsonl_path(year, ftype)
    outp.parent.mkdir(parents=True, exist_ok=True)
    page = int(info.get("next_page") or 1)
    # First page tells us the count.
    while True:
        st, data = fetch_page(year, ftype, page)
        if data is None:
            print(f"HTTP {st} {key} page {page}; will resume", flush=True)
            info["next_page"] = page
            save_progress(progress)
            time.sleep(5)
            # retry same page a few times then stop this period for later resume
            for _ in range(4):
                time.sleep(8)
                st, data = fetch_page(year, ftype, page)
                if data is not None:
                    break
            if data is None:
                info["error"] = f"HTTP {st} on page {page}"
                save_progress(progress)
                return info
        results = data.get("results") or []
        count = data.get("count")
        info["count"] = count
        pages = ((count or 0) + PAGE_SIZE - 1) // PAGE_SIZE if count else page
        info["pages"] = pages
        if not results and page > 1:
            info["done"] = True
            info["next_page"] = page
            save_progress(progress)
            break
        with outp.open("a", encoding="utf-8") as f:
            for row in results:
                f.write(json.dumps(compact(row), ensure_ascii=False) + "\n")
                info["written"] = info.get("written", 0) + 1
        if page % 20 == 1 or page >= pages:
            print(f"{key} page {page}/{pages} written {info['written']}", flush=True)
            info["next_page"] = page + 1
            save_progress(progress)
        if not data.get("next") or page >= pages:
            info["done"] = True
            info["next_page"] = page + 1
            save_progress(progress)
            break
        page += 1
        if delay:
            time.sleep(delay)
    return info

_progress_lock = None

def crawl():
    global _progress_lock
    import threading
    _progress_lock = threading.Lock()
    progress = load_progress()
    jobs = [(y, t) for y in YEARS for t in FILING_TYPES]
    print("periods", len(jobs), "already done", sum(1 for j in jobs if progress["periods"].get(period_key(*j), {}).get("done")), flush=True)
    # Periods write to separate jsonl files, so a few can run in parallel.
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda jt: crawl_period(jt[0], jt[1], progress), jobs))
    done = sum(1 for v in progress["periods"].values() if v.get("done"))
    written = sum(v.get("written") or 0 for v in progress["periods"].values())
    print(json.dumps({"done_periods": done, "written": written, "checkpoint": progress.get("checkpoint")}, indent=1))

def iter_filings():
    if not RAWLDA.exists():
        return
    for p in sorted(RAWLDA.glob("*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

def load_member_bills():
    """(type, number) -> {'sponsor': set(bioguide), 'cosponsor': set(bioguide)} plus name index."""
    people = {p["bioguide"]: p for p in read_json(BUILD / "site" / "people.json")["people"] if p.get("bioguide")}
    bills = collections.defaultdict(lambda: {"sponsor": set(), "cosponsor": set(), "title": None, "introduced": None})
    for kind, field, role in (
        ("sponsored", "sponsoredLegislation", "sponsor"),
        ("cosponsored", "cosponsoredLegislation", "cosponsor"),
    ):
        d = RAW / "congress" / kind
        if not d.exists():
            continue
        for fp in d.glob("*.json"):
            bio = fp.stem
            if bio not in people:
                continue
            data = read_json(fp)
            for it in data.get(field) or []:
                if it.get("congress") != 119:
                    continue
                typ = (it.get("type") or "").upper()
                num = str(it.get("number") or "").strip()
                if not typ or not num:
                    continue
                rec = bills[(typ, num)]
                rec[role].add(bio)
                if it.get("title") and not rec["title"]:
                    rec["title"] = it["title"]
                intro = it.get("introducedDate")
                if intro and (not rec["introduced"] or intro < rec["introduced"]):
                    rec["introduced"] = intro
    return people, bills

def name_index(people):
    """Current members plus official service, gender, and historical surname collisions."""
    current = {p["id"]["bioguide"]: p for p in read_json(RAW / "legislators-current.json")}
    historical_path = RAW / "legislators-historical.json"
    historical = {p["id"]["bioguide"]: p for p in read_json(historical_path)} if historical_path.exists() else {}
    last_owners = collections.defaultdict(set)
    for bio, L in {**historical, **current}.items():
        last = ((L.get("name") or {}).get("last") or "").strip().lower()
        if last:
            last_owners[last].add(bio)
    members = {}
    for bio, ppl in people.items():
        L = current.get(bio) or historical.get(bio) or {}
        official = (L.get("name") or {}).get("official_full") or ppl["name"]
        last = ((L.get("name") or {}).get("last") or official.split()[-1]).strip().lower()
        collision = len(last_owners.get(last) or []) > 1
        members[bio] = M.member_from_legislator(bio, official, L, ppl["name"], collision)
    M.attach_name_collisions(members, {**historical, **current})
    by_last = collections.defaultdict(list)
    for mem in members.values():
        by_last[mem.last_lower].append(mem)
    probe = M.last_probe(by_last.keys())
    return members, by_last, probe

def excerpt_around(text, start, end, width=180):
    """Return a whitespace-normalized slice that appears in the source text.
    No added ellipses — the verifier requires an exact excerpt match."""
    a = max(0, start - 40)
    b = min(len(text), end + width)
    return re.sub(r"\s+", " ", text[a:b]).strip()

def _cap(rows, keyfn, preferfn, limit):
    """Dedupe then keep up to `limit` rows per bioguide, preferred first."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r["bioguide"]].append(r)
    out = []
    raw = 0
    for bio, items in by.items():
        raw += len(items)
        seen = set()
        kept = []
        for r in sorted(items, key=preferfn):
            k = keyfn(r)
            if k in seen:
                continue
            seen.add(k)
            kept.append(r)
            if len(kept) >= limit:
                break
        out.extend(kept)
    return out, raw

def match():
    people, bills = load_member_bills()
    members, by_last, last_probe = name_index(people)
    lobbying = []
    revolving = []
    review_bills = []
    review_pos = []
    rejected_bills = collections.Counter()
    rejected_pos = collections.Counter()
    seen_lb = set()
    seen_rd = set()
    n_filings = 0
    n_with_bill = 0
    n_with_pos = 0
    for row in iter_filings():
        n_filings += 1
        uuid = row.get("filing_uuid")
        acts = row.get("lobbying_activities") or []
        found_bill = False
        found_pos = False
        for act in acts:
            desc = act.get("description") or ""
            if desc:
                bill_hits = M.parse_bill_mentions(desc)
                for hit in bill_hits:
                    rec = bills.get((hit.typ, hit.number))
                    if not rec:
                        if hit.reject_reason:
                            rejected_bills[hit.reject_reason] += 1
                        continue
                    decision, reason = M.decide_bill(
                        hit, desc, rec.get("title"), rec.get("introduced"),
                        row.get("filing_year"), row.get("filing_period"),
                        all_hits=bill_hits,
                    )
                    excerpt = excerpt_around(desc, hit.start, hit.end)
                    base = {
                        "bill_type": hit.typ, "bill_number": hit.number, "bill_label": hit.label,
                        "bill_title": rec.get("title"), "introduced": rec.get("introduced"),
                        "filing_uuid": uuid, "api_url": row.get("api_url"),
                        "document_url": row.get("document_url"),
                        "filing_type": row.get("filing_type"),
                        "filing_type_display": row.get("filing_type_display"),
                        "filing_year": row.get("filing_year"),
                        "filing_period": row.get("filing_period"),
                        "dt_posted": row.get("dt_posted"),
                        "registrant_id": row.get("registrant_id"),
                        "registrant_name": row.get("registrant_name"),
                        "client_id": row.get("client_id"),
                        "client_name": row.get("client_name"),
                        "general_issue_code": act.get("general_issue_code"),
                        "general_issue_code_display": act.get("general_issue_code_display"),
                        "excerpt": excerpt, "decision": decision, "decision_reason": reason,
                    }
                    if decision == "reject":
                        rejected_bills[reason] += 1
                        continue
                    found_bill = True
                    for role in ("sponsor", "cosponsor"):
                        for bio in rec[role]:
                            key = (bio, hit.typ, hit.number, row.get("client_id"), row.get("registrant_id"), role)
                            if key in seen_lb:
                                continue
                            seen_lb.add(key)
                            item = {
                                **base,
                                "bioguide": bio,
                                "member_name": people[bio]["name"],
                                "member_slug": people[bio]["slug"],
                                "role": role,
                            }
                            if decision == "review":
                                review_bills.append(item)
                            else:
                                lobbying.append(item)
            for lb in act.get("lobbyists") or []:
                pos = (lb.get("covered_position") or "").strip()
                if not pos:
                    continue
                hits = last_probe.findall(pos)
                if not hits:
                    continue
                tried = set()
                for last in hits:
                    for mem in by_last.get(last.lower(), []):
                        if mem.bioguide in tried:
                            continue
                        tried.add(mem.bioguide)
                        pos_hits = M.find_position_hits(pos, mem)
                        if not pos_hits:
                            continue
                        # Strongest remaining hit (already ordered)
                        h = pos_hits[0]
                        excerpt = pos if len(pos) <= 280 else excerpt_around(pos, h.start, h.end, width=200)
                        if mem.last not in excerpt and mem.official not in excerpt:
                            continue
                        key = (mem.bioguide, row.get("registrant_id"), lb.get("name"), pos)
                        if key in seen_rd:
                            continue
                        seen_rd.add(key)
                        item = {
                            "bioguide": mem.bioguide,
                            "member_name": people[mem.bioguide]["name"],
                            "member_slug": people[mem.bioguide]["slug"],
                            "lobbyist_name": lb.get("name"),
                            "covered_position": pos,
                            "excerpt": excerpt,
                            "matched": h.matched,
                            "match_kind": h.kind,
                            "decision": h.decision,
                            "decision_reason": h.reason,
                            "filing_uuid": uuid,
                            "api_url": row.get("api_url"),
                            "document_url": row.get("document_url"),
                            "filing_type": row.get("filing_type"),
                            "filing_year": row.get("filing_year"),
                            "dt_posted": row.get("dt_posted"),
                            "registrant_id": row.get("registrant_id"),
                            "registrant_name": row.get("registrant_name"),
                            "client_id": row.get("client_id"),
                            "client_name": row.get("client_name"),
                        }
                        if h.decision == "reject":
                            rejected_pos[h.reason] += 1
                            continue
                        found_pos = True
                        if h.decision == "review":
                            review_pos.append(item)
                        else:
                            revolving.append(item)
        if found_bill:
            n_with_bill += 1
        if found_pos:
            n_with_pos += 1
        if n_filings % 20000 == 0:
            print("scanned", n_filings, "lobbying_published_so_far", len(lobbying),
                  "revolving_published_so_far", len(revolving), flush=True)
    lobbying, raw_lb = _cap(
        lobbying,
        keyfn=lambda r: (r["client_id"], r["bill_type"], r["bill_number"], r["registrant_id"], r["role"]),
        preferfn=lambda r: (0 if r["role"] == "sponsor" else 1, r.get("dt_posted") or ""),
        limit=40,
    )
    revolving, raw_rd = _cap(
        revolving,
        keyfn=lambda r: (r.get("lobbyist_name"), r["covered_position"], r["registrant_id"]),
        preferfn=lambda r: r.get("dt_posted") or "",
        limit=20,
    )
    review_dir = ROOT / "data" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    write_json(review_dir / "lda-bill-queue.json", {
        "generated_at": now_iso(),
        "count": len(review_bills),
        "note": "Bill mentions that parsed as a current member's 119th-Congress bill but were not corroborated. Not published.",
        "rows": review_bills,
    })
    write_json(review_dir / "lda-covered-position-queue.json", {
        "generated_at": now_iso(),
        "count": len(review_pos),
        "note": "Covered-position matches that are ambiguous (typically title plus surname only). Not published.",
        "rows": review_pos,
    })
    write_json(review_dir / "lda-rejected-summary.json", {
        "generated_at": now_iso(),
        "bills": dict(rejected_bills),
        "covered_positions": dict(rejected_pos),
    })
    progress = load_progress() if PROGRESS.exists() else {}
    out = {
        "retrieved_at": now_iso(),
        "source": {
            "api": API,
            "document_pattern": PRINT,
            "note": "The Senate Office of Public Records cannot vouch for the accuracy of this data after retrieval. Politidex does not use the Senate seal.",
        },
        "coverage": {
            "filings_scanned": n_filings,
            "filings_with_matched_bills": n_with_bill,
            "filings_with_matched_covered_positions": n_with_pos,
            "lobbying_matches_unique": raw_lb,
            "lobbying_matches_published": len(lobbying),
            "lobbying_matches_review": len(review_bills),
            "revolving_matches_unique": raw_rd,
            "revolving_matches_published": len(revolving),
            "revolving_matches_review": len(review_pos),
            "rejected_bills": dict(rejected_bills),
            "rejected_positions": dict(rejected_pos),
            "crawl": {
                "periods_done": sum(1 for v in (progress.get("periods") or {}).values() if v.get("done")),
                "periods_total": len(YEARS) * len(FILING_TYPES),
                "written": sum((v.get("written") or 0) for v in (progress.get("periods") or {}).values()),
                "checkpoint": progress.get("checkpoint"),
            },
        },
        "lobbying": lobbying,
        "revolving": revolving,
    }
    write_json(MATCH_OUT, out)
    print(json.dumps(out["coverage"], indent=1))

def main():
    if "--match" in sys.argv and "--crawl" not in sys.argv:
        match()
        return
    if "--crawl" in sys.argv or len(sys.argv) == 1:
        crawl()
    if "--match" in sys.argv:
        match()

if __name__ == "__main__":
    main()
