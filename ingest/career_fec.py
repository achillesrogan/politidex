"""Offline FEC committee and PAC files from the 1979-80 cycle forward.

Downloads only committee master (cm), PAC and party summary (webk), and
committee-to-candidate (pas2) zips from www.fec.gov. Individual-contribution
files are refused. This script is not part of npm run build.

  python3 ingest/career_fec.py
  python3 ingest/career_fec.py --cycle 1980
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, RAW, ROOT, UA, now_iso, write_json

CYCLES = tuple(range(1980, 2028, 2))
KINDS = ("cm", "webk", "pas2")
ALLOW_HOSTS = frozenset({"www.fec.gov", "fec.gov"})
# FEC bulk URLs redirect to this government bucket. No other host is followed.
ALLOW_REDIRECT_SUFFIX = ".s3-us-gov-west-1.amazonaws.com"
MAX_BYTES = {"cm": 25_000_000, "webk": 40_000_000, "pas2": 200_000_000}
DESC = {
    "cm": "https://www.fec.gov/campaign-finance-data/committee-master-file-description/",
    "webk": "https://www.fec.gov/campaign-finance-data/pac-and-party-summary-file-description/",
    "pas2": "https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/",
}
OUT = BUILD / "career-fec"


def bulk_url(cycle, kind):
    """Official fec.gov URL. Individual-contribution names are rejected."""
    if kind not in KINDS:
        raise ValueError("only cm, webk, and pas2 are downloaded")
    cycle = int(cycle)
    if cycle < 1980 or cycle > 2026 or cycle % 2:
        raise ValueError("cycle must be an even year from 1980 through 2026")
    name = "%s%02d.zip" % (kind, cycle % 100)
    if "indiv" in name or name.startswith("itcont"):
        raise ValueError("individual contribution files are not part of this ingest")
    return "https://www.fec.gov/files/bulk-downloads/%d/%s" % (cycle, name)


def host_allowed(host, redirected):
    host = (host or "").lower().rstrip(".")
    if host in ALLOW_HOSTS:
        return True
    return bool(redirected) and host.endswith(ALLOW_REDIRECT_SUFFIX)


def pas2_candidate(line):
    """Committee-to-candidate row. Street, ZIP, employer, and occupation are dropped."""
    parts = line.rstrip("\r\n").split("|")
    if len(parts) < 22:
        return None
    committee_id = parts[0].strip()
    candidate_id = parts[16].strip()
    if not committee_id or not candidate_id:
        return None
    return {
        "committee_id": committee_id,
        "candidate_id": candidate_id,
        "transaction_type": parts[5].strip().upper(),
        "date": parts[13].strip(),
        "amount": parts[14].strip(),
        "amendment": parts[1].strip().upper(),
    }


def _download(url, dest, kind):
    cap = MAX_BYTES[kind]
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    # Only the fec.gov URL is printed. The redirect target is not.
    print("get", url, flush=True)
    with urllib.request.urlopen(req, timeout=120) as response:
        final = urlparse(response.geturl())
        redirected = final.netloc.lower().rstrip(".") not in ALLOW_HOSTS
        if not host_allowed(final.netloc, redirected):
            raise SystemExit("refusing a download whose host is not allowlisted")
        tmp = dest.with_suffix(dest.suffix + ".partial")
        n = 0
        with open(tmp, "wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                n += len(chunk)
                if n > cap:
                    tmp.unlink(missing_ok=True)
                    raise SystemExit("refusing %s; larger than %d bytes" % (dest.name, cap))
                out.write(chunk)
        tmp.replace(dest)
    return n


def fetch(cycles=None):
    cycles = tuple(cycles or CYCLES)
    saved = []
    for cycle in cycles:
        for kind in KINDS:
            url = bulk_url(cycle, kind)
            dest = RAW / "career-fec" / Path(url).name
            if "indiv" in dest.name:
                raise SystemExit("refusing an individual contribution file")
            if not dest.exists():
                _download(url, dest, kind)
            saved.append({"cycle": cycle, "kind": kind, "url": url, "bytes": dest.stat().st_size})
    write_json(OUT / "files.json", {
        "retrieved_at": now_iso(),
        "source": "Federal Election Commission bulk files",
        "begins": "1980",
        "cycle": "1979-80",
        "files": ["cm", "webk", "pas2"],
        "excludes": "individual contribution files",
        "descriptions": DESC,
        "downloaded": saved,
    })
    print("fec career files", len(saved), flush=True)
    write_derived(saved)


def _zip_rows(path):
    import zipfile
    if not path.exists():
        return None
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if not names:
            return 0
        count = 0
        with archive.open(names[0]) as handle:
            for _line in handle:
                count += 1
        return count


def write_derived(saved):
    """Counts only. The zip files stay in data/raw and are not committed."""
    cycles = {}
    for item in saved:
        row = cycles.setdefault(item["cycle"], {"cycle": item["cycle"], "files": {}})
        dest = RAW / "career-fec" / Path(item["url"]).name
        row["files"][item["kind"]] = {
            "url": item["url"],
            "description_url": DESC[item["kind"]],
            "bytes": item["bytes"],
            "rows": _zip_rows(dest),
        }
    derived = {
        "retrieved_at": now_iso(),
        "source_name": "Federal Election Commission",
        "source_url": "https://www.fec.gov/files/bulk-downloads/",
        "begins": 1980,
        "cycle": "1979-80",
        "files": ["cm", "webk", "pas2"],
        "excludes": "individual contribution files",
        "cycles": [cycles[year] for year in sorted(cycles)],
    }
    write_json(ROOT / "data" / "career" / "fec.json", derived)
    print("wrote data/career/fec.json", flush=True)


def member_committees(fec_to_bioguide, retrieved_at=None):
    """Committees whose filed candidate id maps to one bioguide.

    The map is candidate id to bioguide. A candidate id that maps to more than
    one bioguide is omitted. Individual contribution files are not read.
    """
    import zipfile
    chosen = {}
    for cand, bio in fec_to_bioguide.items():
        if not cand or not bio:
            continue
        chosen.setdefault(cand, set()).add(bio)
    usable = {cand: next(iter(bios)) for cand, bios in chosen.items() if len(bios) == 1}
    found = {}
    for year in range(1980, 2028, 2):
        path = RAW / "career-fec" / ("cm%02d.zip" % (year % 100))
        if not path.exists():
            continue
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if not names:
                continue
            with archive.open(names[0]) as handle:
                for raw in handle:
                    parts = raw.decode("latin-1").rstrip("\r\n").split("|")
                    if len(parts) < 15:
                        continue
                    cand = parts[14].strip()
                    bio = usable.get(cand)
                    if not bio:
                        continue
                    committee_id = parts[0].strip()
                    if not committee_id.startswith("C"):
                        continue
                    key = (bio, committee_id)
                    row = found.get(key)
                    if row is None:
                        row = {
                            "committee_id": committee_id,
                            "name": parts[1].strip(),
                            "candidate_id": cand,
                            "designation": parts[8].strip(),
                            "cycles": [],
                        }
                        found[key] = row
                    if year not in row["cycles"]:
                        row["cycles"].append(year)
                    name = parts[1].strip()
                    if len(name) > len(row["name"]):
                        row["name"] = name
    members = {}
    for (bio, _cid), row in found.items():
        members.setdefault(bio, []).append(row)
    for rows in members.values():
        rows.sort(key=lambda item: (item["cycles"][0], item["committee_id"]))
    derived = {
        "retrieved_at": retrieved_at or now_iso(),
        "source_name": "Federal Election Commission",
        "source_url": "https://www.fec.gov/files/bulk-downloads/",
        "begins": 1980,
        "excludes": "individual contribution files",
        "note": "A committee is listed when its filed candidate id is an FEC id for that bioguide. The public committee page is https://www.fec.gov/data/committee/{id}/.",
        "members": members,
    }
    path = ROOT / "data" / "career" / "fec-members.json"
    path.write_text(json.dumps(derived, separators=(",", ":"), ensure_ascii=False))
    print("wrote", path, len(members), "members", flush=True)
    return derived


if __name__ == "__main__":
    chosen = None
    if "--cycle" in sys.argv:
        chosen = [int(sys.argv[sys.argv.index("--cycle") + 1])]
    fetch(chosen)
