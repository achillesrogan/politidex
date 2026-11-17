"""Build the committee website map and proposed summaries from official pages only.

Senate rows come from https://www.senate.gov/committees/.
House and joint rows come from https://clerk.house.gov/committees and each
Clerk committee profile. A website is stored only after a live 200 response.
History and jurisdiction sentences are copied from ingest/committee_history.py
only when those sentences are still on the cited page. Nothing is written from
memory. Every summary starts as review_status "proposed".
"""
import html as H
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import UA, now_iso
from committee_history import RECORDS, norm

ROOT = Path(__file__).resolve().parent.parent
OUT_SITES = ROOT / "data" / "committees" / "sites.json"
OUT_SUMMARIES = ROOT / "data" / "committees" / "summaries.json"
SENATE_LIST = "https://www.senate.gov/committees/"
CLERK_LIST = "https://clerk.house.gov/committees"
HOUSE_LIST = "https://www.house.gov/committees"
RETRIEVED = now_iso()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read(2_000_000)
            time.sleep(0.25)
            return res.status, res.geturl(), body
    except urllib.error.HTTPError as exc:
        time.sleep(0.25)
        return exc.code, url, b""
    except Exception:
        time.sleep(0.25)
        return 0, url, b""


def text_of(fragment):
    cleaned = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", H.unescape(cleaned)).strip()


def abs_url(href):
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return "https://www.senate.gov" + href
    return href


def official_final(url):
    candidates = [url]
    if url.startswith("http://"):
        candidates.insert(0, "https://" + url[len("http://"):])
    for cand in candidates:
        status, final, _ = get(cand)
        if status != 200:
            continue
        parsed = urllib.parse.urlparse(final)
        host = parsed.hostname or ""
        if parsed.scheme == "https" and host.endswith(".gov"):
            return final.split("#")[0]
    return None


def senate_rows(page):
    rows = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, flags=re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S | re.I)
        if len(cells) < 4 or "committee_memberships_" not in cells[3]:
            continue
        site = re.search(r'href="(https?://[^"]+)"[^>]*>([^<]+)</a>', cells[0], flags=re.I)
        code = re.search(r"committee_memberships_([A-Z0-9]+)\.htm", cells[3])
        members = re.search(r"(\d+)", text_of(cells[3]))
        if not site or not code:
            continue
        def person(cell):
            value = text_of(cell)
            return "" if value in {"", "--", "—", "None"} else value

        parent = {
            "code": code.group(1),
            "name": text_of(site.group(2)),
            "chamber": "senate",
            "listed_website": site.group(1),
            "chair": person(cells[1]),
            "ranking": person(cells[2]),
            "members": members.group(1) if members else "",
            "parent": None,
        }
        rows.append(parent)
        if len(cells) > 4:
            for href, name in re.findall(r'href="([^"]+)"[^>]*>([^<]+)</a>', cells[4], flags=re.I):
                sub = re.search(r"#([A-Z0-9]+)$", href)
                if not sub:
                    continue
                rows.append({
                    "code": sub.group(1),
                    "name": text_of(name),
                    "chamber": "senate",
                    "listed_website": "",
                    "chair": "",
                    "ranking": "",
                    "members": "",
                    "parent": parent["code"],
                })
    return rows


def clerk_codes(page):
    found = []
    seen = set()
    for code, title in re.findall(r'href="/committees/([A-Z0-9]{4})"[^>]*title="([^"]+)"', page):
        if code in seen:
            continue
        seen.add(code)
        title = H.unescape(title)
        chamber = "joint" if title.startswith("Joint ") else "house"
        found.append((code, title, chamber))
    return found


def role_after(item):
    tail = item.split("</a>", 1)[-1]
    tail = tail.split('<span class="name"', 1)[0]
    return text_of(tail)


def member_name(item):
    span = re.search(r"<span[^>]*>\s*([^<]+)</span>", item)
    return text_of(span.group(1) if span else "")


def clerk_profile(code, title, chamber, page):
    website = ""
    site = re.search(r"Website:\s*<a[^>]*href=(?:\"|')?(https?://[^\"'\s>]+)", page, flags=re.I)
    if site:
        website = site.group(1)
    chair = ""
    ranking = ""
    for item in re.findall(r'<li class="row".*?</li>', page, flags=re.S | re.I):
        role = role_after(item)
        name = member_name(item)
        if name and re.search(r"\bChair\b", role) and "Vice" not in role and "Ranking" not in role and not chair:
            chair = name
        if name and re.search(r"Ranking Member", role) and not ranking:
            ranking = name
    ratio = ""
    ratio_m = re.search(r"Ratio\s+(\d+\s*/\s*\d+)", page)
    if ratio_m:
        ratio = re.sub(r"\s+", " ", ratio_m.group(1))
    subs = []
    block = re.search(r'<section class="subcommittees">(.*?)</section>', page, flags=re.S | re.I)
    if block:
        for href, name in re.findall(r'href="(/committees/[A-Z0-9]{4})"[^>]*>([^<]+)</a>', block.group(1)):
            subs.append((href.rsplit("/", 1)[-1], text_of(name)))
    return {
        "code": code,
        "name": title,
        "chamber": chamber,
        "listed_website": website,
        "chair": chair,
        "ranking": ranking,
        "members": "",
        "ratio": ratio,
        "parent": None,
        "subs": subs,
    }


def roster_facts(row, source_url, source_name):
    facts = []
    if row.get("chair") or row.get("ranking") or row.get("members"):
        parts = []
        excerpt_parts = []
        if row.get("chair"):
            parts.append(f"Chair: {row['chair']}")
            excerpt_parts.append(row["chair"])
        if row.get("ranking"):
            parts.append(f"Ranking Member: {row['ranking']}")
            excerpt_parts.append(row["ranking"])
        if row.get("members"):
            parts.append(f"Total Members: {row['members']}")
            excerpt_parts.append(row["members"])
        facts.append({
            "kind": "roster",
            "text": ". ".join(parts) + ".",
            "source_name": source_name,
            "source_url": source_url,
            "retrieved_at": RETRIEVED,
            "excerpt": " ".join(excerpt_parts),
        })
    if row.get("ratio"):
        facts.append({
            "kind": "roster",
            "text": f"Ratio: {row['ratio']}.",
            "source_name": source_name,
            "source_url": source_url,
            "retrieved_at": RETRIEVED,
            "excerpt": f"Ratio {row['ratio']}",
        })
    if row.get("subcommittee_count"):
        facts.append({
            "kind": "roster",
            "text": f"Subcommittees listed: {row['subcommittee_count']}.",
            "source_name": source_name,
            "source_url": source_url,
            "retrieved_at": RETRIEVED,
            "excerpt": "Subcommittees",
        })
    return facts


def history_facts():
    pages = {}
    out = {}
    for rec in RECORDS:
        kept = []
        for fact in rec["facts"]:
            url = fact["source_url"]
            if url not in pages:
                status, _, body = get(url)
                pages[url] = norm(body.decode("utf-8", "replace")) if status == 200 else ""
            page = pages[url]
            if page and all(needle in page for needle in fact["needles"]):
                kept.append({
                    "kind": fact["kind"],
                    "text": fact["text"],
                    "source_name": fact["source_name"],
                    "source_url": url,
                    "retrieved_at": RETRIEVED,
                    "excerpt": fact["excerpt"],
                })
        if kept:
            out[rec["code"]] = kept
    return out


def main():
    status, _, body = get(SENATE_LIST)
    if status != 200:
        raise SystemExit(f"senate list status {status}")
    senate = senate_rows(body.decode("utf-8", "replace"))
    status, _, body = get(CLERK_LIST)
    if status != 200:
        raise SystemExit(f"clerk list status {status}")
    clerk_html = body.decode("utf-8", "replace")
    house = []
    sub_rows = []
    for code, title, chamber in clerk_codes(clerk_html):
        st, _, page_b = get(f"https://clerk.house.gov/committees/{code}")
        if st != 200:
            continue
        profile = clerk_profile(code, title, chamber, page_b.decode("utf-8", "replace"))
        profile["subcommittee_count"] = len(profile["subs"])
        house.append(profile)
        for sub_code, sub_name in profile["subs"]:
            sub_rows.append({"code": sub_code, "name": sub_name, "chamber": chamber, "parent": code, "listed_website": ""})

    committees = {}
    summaries = {}

    def add(row, source_url, source_name):
        website = official_final(row["listed_website"]) if row.get("listed_website") else None
        committees[row["code"]] = {
            "code": row["code"],
            "name": row["name"],
            "chamber": row["chamber"],
            "parent": row.get("parent"),
            "website": website,
            "website_source_url": source_url if website else None,
            "website_retrieved_at": RETRIEVED if website else None,
        }
        facts = roster_facts(row, source_url, source_name)
        if facts:
            summaries[row["code"]] = {"review_status": "proposed", "facts": facts}

    for row in senate:
        if row["parent"]:
            committees[row["code"]] = {
                "code": row["code"],
                "name": row["name"],
                "chamber": "senate",
                "parent": row["parent"],
                "website": None,
                "website_source_url": None,
                "website_retrieved_at": None,
            }
            continue
        add(row, SENATE_LIST, "U.S. Senate committee list")
    for row in house:
        add(row, f"https://clerk.house.gov/committees/{row['code']}", "Office of the Clerk, U.S. House")
    for row in sub_rows:
        if row["code"] in committees:
            continue
        committees[row["code"]] = {
            "code": row["code"],
            "name": row["name"],
            "chamber": row["chamber"],
            "parent": row["parent"],
            "website": None,
            "website_source_url": None,
            "website_retrieved_at": None,
        }

    status, _, house_body = get(HOUSE_LIST)
    if status == 200:
        def short_name(name):
            key = re.sub(r"[^a-z0-9]+", " ", H.unescape(name).lower()).strip()
            return re.sub(r"^(joint |permanent select |select )?committee on (the )?", "", key)

        listed = {}
        for href, name in re.findall(r'<a href="(https?://[^"]+)"[^>]*>([^<]+)</a>', house_body.decode("utf-8", "replace"), flags=re.I):
            listed[short_name(name)] = href
        for row in committees.values():
            if row.get("website"):
                continue
            href = listed.get(short_name(row["name"]))
            if not href:
                continue
            final = official_final(href)
            if not final:
                continue
            row["website"] = final
            row["website_source_url"] = HOUSE_LIST
            row["website_retrieved_at"] = RETRIEVED

    for code, facts in history_facts().items():
        entry = summaries.setdefault(code, {"review_status": "proposed", "facts": []})
        entry["review_status"] = "proposed"
        entry["facts"].extend(facts)

    sites = {
        "retrieved_at": RETRIEVED,
        "sources": [
            {"name": "U.S. Senate committee list", "url": SENATE_LIST, "retrieved_at": RETRIEVED},
            {"name": "Office of the Clerk, U.S. House committee profiles", "url": CLERK_LIST, "retrieved_at": RETRIEVED},
            {"name": "U.S. House committee list", "url": HOUSE_LIST, "retrieved_at": RETRIEVED},
        ],
        "note": "Websites were requested and kept only when the response was HTTPS 200 on a .gov host. Subcommittee rows without their own official website have website null.",
        "committees": committees,
    }
    summary_doc = {
        "retrieved_at": RETRIEVED,
        "review_note": "Every entry is proposed. The site renders a sentence only after review_status is approved. Bill-referral counts are omitted because no Congress.gov API key was available in this environment.",
        "committees": summaries,
    }
    OUT_SITES.parent.mkdir(parents=True, exist_ok=True)
    OUT_SITES.write_text(json.dumps(sites, indent=1, ensure_ascii=False) + "\n")
    OUT_SUMMARIES.write_text(json.dumps(summary_doc, indent=1, ensure_ascii=False) + "\n")
    live = sum(1 for row in committees.values() if row.get("website"))
    print(f"committees {len(committees)} with a live website {live}; summaries {len(summaries)}")


if __name__ == "__main__":
    main()
