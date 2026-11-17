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
# Linkage files exist from 2000. Earlier cycles use the candidate master.
CCL_FROM = 2000
ALLOW_HOSTS = frozenset({"www.fec.gov", "fec.gov"})
CROSSWALK_HOSTS = frozenset({"unitedstates.github.io"})
# FEC bulk URLs redirect to this government bucket. No other host is followed.
ALLOW_REDIRECT_SUFFIX = ".s3-us-gov-west-1.amazonaws.com"
MAX_BYTES = {
    "cm": 25_000_000, "webk": 40_000_000, "pas2": 200_000_000,
    "ccl": 25_000_000, "cn": 25_000_000,
}
DESC = {
    "cm": "https://www.fec.gov/campaign-finance-data/committee-master-file-description/",
    "webk": "https://www.fec.gov/campaign-finance-data/pac-and-party-summary-file-description/",
    "pas2": "https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/",
    "ccl": "https://www.fec.gov/campaign-finance-data/candidate-committee-linkage-file-description/",
    "cn": "https://www.fec.gov/campaign-finance-data/candidate-master-file-description/",
}
CROSSWALK_URLS = {
    "legislators-current.json": "https://unitedstates.github.io/congress-legislators/legislators-current.json",
    "legislators-historical.json": "https://unitedstates.github.io/congress-legislators/legislators-historical.json",
}
OUT = BUILD / "career-fec"


def bulk_url(cycle, kind):
    """Official fec.gov URL. Individual-contribution names are rejected."""
    if kind not in MAX_BYTES:
        raise ValueError("only cm, webk, pas2, ccl, and cn are downloaded")
    cycle = int(cycle)
    if cycle < 1980 or cycle > 2026 or cycle % 2:
        raise ValueError("cycle must be an even year from 1980 through 2026")
    if kind == "ccl" and cycle < CCL_FROM:
        raise ValueError("the linkage file is published from the 2000 cycle")
    name = "%s%02d.zip" % (kind, cycle % 100)
    if "indiv" in name or name.startswith("itcont"):
        raise ValueError("individual contribution files are not part of this ingest")
    return "https://www.fec.gov/files/bulk-downloads/%d/%s" % (cycle, name)


def required_bulk(cycles):
    """cm, webk, and pas2 every cycle; ccl from 2000; cn before 2000."""
    items = []
    for cycle in cycles:
        for kind in KINDS:
            items.append((cycle, kind))
        items.append((cycle, "ccl" if cycle >= CCL_FROM else "cn"))
    return items


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


def _download_crosswalk():
    """Public-domain bioguide-to-FEC-id index. A missing file stops the run."""
    for name, url in CROSSWALK_URLS.items():
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        print("get", url, flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as response:
            host = urlparse(response.geturl()).netloc.lower().rstrip(".")
            if host not in CROSSWALK_HOSTS:
                raise SystemExit("refusing a crosswalk download from %s" % host)
            dest.write_bytes(response.read())
        if not dest.exists() or dest.stat().st_size < 1000:
            raise SystemExit("missing %s after download" % name)


def fetch(cycles=None):
    cycles = tuple(cycles or CYCLES)
    saved = []
    for cycle, kind in required_bulk(cycles):
        url = bulk_url(cycle, kind)
        dest = RAW / "career-fec" / Path(url).name
        if "indiv" in dest.name:
            raise SystemExit("refusing an individual contribution file")
        if not dest.exists() or dest.stat().st_size < 100:
            _download(url, dest, kind)
        if not dest.exists() or dest.stat().st_size < 100:
            raise SystemExit("missing %s" % dest.name)
        saved.append({"cycle": cycle, "kind": kind, "url": url, "bytes": dest.stat().st_size})
    _download_crosswalk()
    for name in CROSSWALK_URLS:
        path = RAW / name
        if not path.exists() or path.stat().st_size < 1000:
            raise SystemExit("missing %s" % name)
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
        if item["kind"] not in KINDS:
            continue
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


# Principal, authorized, and joint fundraising. Unauthorized (U) and leadership (D) stay out.
KEEP_DESIGNATIONS = frozenset({"P", "A", "J"})
CROSSWALK = {
    "source_name": "unitedstates/congress-legislators",
    "source_url": "https://github.com/unitedstates/congress-legislators",
    "files": [
        "https://unitedstates.github.io/congress-legislators/legislators-current.json",
        "https://unitedstates.github.io/congress-legislators/legislators-historical.json",
    ],
    "license": "CC0 1.0",
    "note": "The FEC candidate master has no bioguide field. This public-domain index is the bioguide-to-FEC-candidate-id crosswalk.",
}
def _zip_rows_split(path):
    import zipfile
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if not names:
            return
        with archive.open(names[0]) as handle:
            for raw in handle:
                yield raw.decode("latin-1").rstrip("\r\n").split("|")


def load_bioguide_fec_ids(current_path=None, historical_path=None):
    """FEC candidate id to bioguide, from the public-domain legislators index."""
    current_path = Path(current_path or (RAW / "legislators-current.json"))
    historical_path = Path(historical_path or (RAW / "legislators-historical.json"))
    if not current_path.exists() or not historical_path.exists():
        return None
    mapping = {}
    for path in (current_path, historical_path):
        people = json.loads(path.read_text())
        if isinstance(people, dict):
            people = people.get("persons") or people.get("people") or []
        for person in people:
            bio = (person.get("id") or {}).get("bioguide")
            for fec in (person.get("id") or {}).get("fec") or []:
                if bio and fec:
                    mapping.setdefault(fec, set()).add(bio)
    return {fec: next(iter(bios)) for fec, bios in mapping.items() if len(bios) == 1}


def _require(path, strict):
    if path.exists() and path.stat().st_size > 100:
        return True
    if strict:
        raise SystemExit("missing %s; the committee history was not written" % path.name)
    return False


def current_bioguides(path=None):
    path = Path(path or (RAW / "legislators-current.json"))
    if not path.exists():
        return None
    people = json.loads(path.read_text())
    return {person["id"]["bioguide"] for person in people if (person.get("id") or {}).get("bioguide")}


def _principal_committees(cn_path):
    """Candidate id to the committee the candidate master names as CAND_PCC."""
    principals = {}
    for parts in _zip_rows_split(cn_path):
        if len(parts) < 10:
            continue
        cand = parts[0].strip()
        pcc = parts[9].strip()
        if cand and pcc.startswith("C"):
            principals[cand] = pcc
    return principals


def member_committees(fec_to_bioguide, retrieved_at=None, root=None, write=True, strict=False, only_bioguides=None):
    """P, A, and J committees, name and designation kept as filed in each cycle.

    From 2000, a row is kept only when that cycle's linkage file and committee
    master both name the same candidate, committee, and designation. Before
    2000, only a principal row is kept, and only when that cycle's candidate
    master names the committee as CAND_PCC. A missing required file stops a
    strict run. Individual contribution files are not read.
    """
    usable = {}
    for cand, bios in fec_to_bioguide.items():
        if isinstance(bios, str):
            bios = {bios}
        if cand and len(bios) == 1:
            usable[cand] = next(iter(bios))
    raw_root = Path(root) if root is not None else RAW / "career-fec"
    grouped = {}
    for year in range(1980, 2028, 2):
        cm_path = raw_root / ("cm%02d.zip" % (year % 100))
        if not _require(cm_path, strict):
            continue
        master = {}
        for parts in _zip_rows_split(cm_path):
            if len(parts) < 15:
                continue
            committee_id = parts[0].strip()
            if not committee_id.startswith("C"):
                continue
            master[committee_id] = {
                "name": parts[1].strip(),
                "designation": parts[8].strip().upper(),
                "candidate_id": parts[14].strip(),
            }
        ccl_path = raw_root / ("ccl%02d.zip" % (year % 100))
        cn_path = raw_root / ("cn%02d.zip" % (year % 100))
        if year >= CCL_FROM:
            if not _require(ccl_path, strict):
                continue
            for parts in _zip_rows_split(ccl_path):
                if len(parts) < 6:
                    continue
                if parts[2].strip() != str(year):
                    continue
                cand = parts[0].strip()
                committee_id = parts[3].strip()
                designation = parts[5].strip().upper()
                if designation not in KEEP_DESIGNATIONS:
                    continue
                bio = usable.get(cand)
                filed = master.get(committee_id)
                if not bio or not filed:
                    continue
                if filed["candidate_id"] != cand or filed["designation"] != designation:
                    continue
                key = (bio, committee_id, filed["name"], designation, cand)
                grouped.setdefault(key, set()).add(year)
        else:
            if not _require(cn_path, strict):
                continue
            principals = _principal_committees(cn_path)
            for committee_id, filed in master.items():
                cand = filed["candidate_id"]
                bio = usable.get(cand)
                if not bio or filed["designation"] != "P":
                    continue
                if principals.get(cand) != committee_id:
                    continue
                key = (bio, committee_id, filed["name"], "P", cand)
                grouped.setdefault(key, set()).add(year)
    if strict and not grouped:
        raise SystemExit("committee history is empty; required FEC files did not produce any rows")
    keep = only_bioguides
    if keep is None and write and root is None:
        keep = current_bioguides()
        if strict and not keep:
            raise SystemExit("missing legislators-current.json; current members were not selected")
    members = {}
    for (bio, committee_id, name, designation, cand), cycles in grouped.items():
        if keep is not None and bio not in keep:
            continue
        members.setdefault(bio, []).append({
            "committee_id": committee_id,
            "name": name,
            "candidate_id": cand,
            "designation": designation,
            "cycles": sorted(cycles),
        })
    for rows in members.values():
        rows.sort(key=lambda item: (item["cycles"][0], item["committee_id"], item["name"]))
    derived = {
        "retrieved_at": retrieved_at or now_iso(),
        "source_name": "Federal Election Commission",
        "source_url": "https://www.fec.gov/files/bulk-downloads/",
        "begins": 1980,
        "excludes": "individual contribution files",
        "designations": "P principal, A authorized, J joint fundraising. U and D are omitted.",
        "linkage": "From 2000, the candidate-committee linkage file and the committee master must agree on candidate, committee, and designation. Before 2000, a principal row is kept only when that cycle's candidate master names the committee as CAND_PCC. Authorized and joint-fundraising rows before 2000 are omitted.",
        "id_crosswalk": CROSSWALK,
        "members": members,
    }
    if write:
        path = ROOT / "data" / "career" / "fec-members.json"
        path.write_text(json.dumps(derived, separators=(",", ":"), ensure_ascii=False))
        print("wrote", path, len(members), "members", flush=True)
    return derived


if __name__ == "__main__":
    chosen = None
    if "--cycle" in sys.argv:
        chosen = [int(sys.argv[sys.argv.index("--cycle") + 1])]
    fetch(chosen)
    ids = load_bioguide_fec_ids()
    if not ids:
        raise SystemExit("missing legislators-current.json or legislators-historical.json")
    fec = json.loads((ROOT / "data" / "career" / "fec.json").read_text())
    member_committees(ids, retrieved_at=fec.get("retrieved_at"), strict=True)
