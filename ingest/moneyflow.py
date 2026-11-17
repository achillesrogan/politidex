"""Offline ingest of the current FEC cycle into a money-flow graph.

Reads official bulk files only. Does not call the OpenFEC API and does not
read DATA_GOV_API_KEY or any other key. Individual-contribution files (indiv*)
are not downloaded.

Usage (from the repository root):
  python3 ingest/moneyflow.py fetch
  python3 ingest/moneyflow.py build

fetch writes zips under data/raw/fec/moneyflow/ (gitignored).
build writes the pilot shards and the size projection under data/moneyflow/
and refuses to write a shard whose child edges do not match the official total.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, UA, now_iso, write_json
from moneyflow_lib import (
    COMMITTEE_ID, CYCLE, DESC_URLS, FILE_MEMBERS, FILE_URLS, FUNGIBILITY_NOTE,
    ReconciliationError, build_shard, cents_to_decimal, classify_payee,
    in_cycle, is_memo, oth_parts, oppexp_parts, over_official,
    parse_master_line, parse_webk_line, pas2_parts, public_problems,
    select_pilot, txn_class, wording_document,
)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = RAW / "fec" / "moneyflow"
OUT_DIR = ROOT / "data" / "moneyflow"
PILOT_DIR = OUT_DIR / "pilot" / "shards"

# Registered national-committee ids used only to confirm the summary column
# layout. Amounts are not hardcoded.
LAYOUT_CANARIES = (
    ("C00010603", "DEMOCRATIC NATIONAL COMMITTEE"),
    ("C00003418", "REPUBLICAN NATIONAL COMMITTEE"),
)


class Acc:
    __slots__ = (
        "amount", "count", "purpose", "name", "official_id", "node_kind",
        "terminal", "bucket", "image", "sub_id", "file_num", "sample_amt",
        "sources", "payee_key", "edge_kind",
    )

    def __init__(self, payee_key, edge_kind):
        self.payee_key = payee_key
        self.edge_kind = edge_kind
        self.amount = 0
        self.count = 0
        self.purpose = None
        self.name = None
        self.official_id = None
        self.node_kind = None
        self.terminal = False
        self.bucket = None
        self.image = None
        self.sub_id = None
        self.file_num = None
        self.sample_amt = None
        self.sources = set()

    def add(self, amount, classified, image, sub_id, file_num, source):
        self.amount += amount
        self.count += 1
        self.sources.add(source)
        code = classified.get("purpose_code")
        if self.count == 1:
            self.purpose = code
            self.node_kind = classified["node_kind"]
            self.terminal = classified["terminal"]
            self.bucket = classified["bucket"]
            self.official_id = classified["official_id"]
        elif code != self.purpose:
            self.purpose = None
        if classified["bucket"]:
            return
        if self.sample_amt is None or amount > self.sample_amt:
            self.sample_amt = amount
            self.name = classified["name"]
            self.official_id = classified["official_id"]
            self.image = image or None
            self.sub_id = sub_id or None
            self.file_num = file_num or None

    def as_dict(self):
        return {
            "payee_key": self.payee_key,
            "edge_kind": self.edge_kind,
            "amount_cents": self.amount,
            "count": self.count,
            "purpose_code": self.purpose,
            "name": self.name,
            "official_id": self.official_id,
            "node_kind": self.node_kind,
            "terminal": self.terminal,
            "bucket": self.bucket,
            "image": self.image,
            "sub_id": self.sub_id,
            "file_num": self.file_num,
            "sources": sorted(self.sources),
        }


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url, dest):
    import urllib.request
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    h = hashlib.sha256()
    n = 0
    last_modified = None
    # The redirect target is not printed or stored. Only the fec.gov URL is kept.
    with urllib.request.urlopen(req, timeout=120) as r:
        last_modified = r.headers.get("Last-Modified")
        tmp = dest.with_suffix(dest.suffix + ".partial")
        with open(tmp, "wb") as out:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                n += len(chunk)
        tmp.replace(dest)
    return {"bytes": n, "sha256": h.hexdigest(), "last_modified": last_modified}


def fetch(refresh=False):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    saved = {}
    for key, url in FILE_URLS.items():
        dest = RAW_DIR / Path(url).name
        if dest.exists() and not refresh:
            print("have", dest.name, dest.stat().st_size)
            saved[key] = {"url": url, "bytes": dest.stat().st_size, "sha256": _sha256(dest), "last_modified": None}
            continue
        print("get", url)
        meta = _download(url, dest)
        meta["url"] = url
        saved[key] = meta
        print(" ", dest.name, meta["bytes"], meta.get("last_modified") or "")
    write_json(RAW_DIR / "sources.json", {"retrieved_at": now_iso(), "files": saved})
    print("fetched", len(saved))


def _open_member(key):
    path = RAW_DIR / Path(FILE_URLS[key]).name
    if not path.exists():
        raise SystemExit("missing %s; run: python3 ingest/moneyflow.py fetch" % path.name)
    if "indiv" in path.name.lower():
        raise SystemExit("refusing to read an individual-contribution file")
    z = zipfile.ZipFile(path)
    member = FILE_MEMBERS[key]
    if member not in z.namelist():
        z.close()
        raise SystemExit("%s does not contain %s" % (path.name, member))
    return path, z, z.open(member)


def _count_candidate_rows(key):
    """Count data rows by the first field only. Candidate names are not decoded."""
    path, z, fh = _open_member(key)
    n = 0
    try:
        for line in fh:
            bar = line.find(b"|")
            first = line[:bar] if bar >= 0 else line.strip()
            if len(first) == 9 and first[:1] in b"HSP":
                n += 1
    finally:
        fh.close()
        z.close()
    return n


def _load_master():
    path, z, fh = _open_member("cm")
    master = {}
    try:
        for raw in fh:
            row = parse_master_line(raw.decode("latin-1"))
            if row:
                master[row["committee_id"]] = row
    finally:
        fh.close()
        z.close()
    return master


def _load_summaries(master):
    path, z, fh = _open_member("webk")
    summaries = {}
    duplicate_ids = []
    missing_total = []
    try:
        for raw in fh:
            row = parse_webk_line(raw.decode("latin-1"))
            if not row:
                continue
            cid = row["committee_id"]
            if cid in summaries:
                duplicate_ids.append(cid)
                continue
            m = master.get(cid) or {}
            summary_type = row["committee_type"]
            master_type = m.get("committee_type") or ""
            conflict = bool(master_type and summary_type and master_type != summary_type)
            summaries[cid] = {
                "committee_id": cid,
                "name": (m.get("name") or row["name"] or cid),
                "summary_name": row["name"],
                "committee_type": master_type or summary_type,
                "summary_committee_type": summary_type,
                "designation": m.get("designation") or row["designation"],
                "party": m.get("party") or "",
                "org_type": m.get("org_type") or "",
                "connected_organization": m.get("connected_organization"),
                "state": m.get("state"),
                "filing_frequency": m.get("filing_frequency"),
                "receipts_cents": row["receipts_cents"],
                "disbursements_cents": row["disbursements_cents"],
                "coverage_end": row["coverage_end"],
                "type_conflict": conflict,
            }
    finally:
        fh.close()
        z.close()
    for cid in duplicate_ids:
        summaries.pop(cid, None)
    for cid, row in summaries.items():
        if row["disbursements_cents"] is None:
            missing_total.append(cid)
    for cid in missing_total:
        summaries.pop(cid, None)
    return summaries, sorted(set(duplicate_ids)), missing_total


def _check_layout(summaries):
    for cid, needle in LAYOUT_CANARIES:
        row = summaries.get(cid)
        if not row or needle not in (row.get("summary_name") or "").upper():
            raise SystemExit(
                "PAC and party summary layout check failed for %s. "
                "The file does not match the FEC column description, so no shards were written."
                % cid
            )
        if not row["disbursements_cents"] or row["disbursements_cents"] <= 0:
            raise SystemExit("summary total disbursements for %s was not a positive amount" % cid)


def _add(agg, seen, stats, parts, source, master, webk_ids, category=None):
    cid = parts["committee_id"]
    if cid not in webk_ids:
        stats["rows_filer_not_in_pac_party_summary"] += 1
        return
    kind = "out" if source == "oppexp" else txn_class(parts.get("txn_type") or "")
    if source != "oppexp" and kind == "unknown":
        stats["unknown_types"][parts.get("txn_type") or ""] = stats["unknown_types"].get(parts.get("txn_type") or "", 0) + 1
        return
    if source != "oppexp" and kind == "in":
        stats["receipt_rows"] += 1
        return
    if is_memo(parts["memo"]):
        stats["memo_rows"] += 1
        if parts["amount_cents"]:
            stats["memo_cents"] += parts["amount_cents"]
        # Keep the id so a later file cannot add a row the any-transaction file marked memo.
        if parts["sub_id"]:
            seen.add(parts["sub_id"])
        return
    amount = parts["amount_cents"]
    if amount is None:
        stats["bad_amount_rows"] += 1
        return
    if amount == 0:
        stats["zero_amount_rows"] += 1
        return
    if parts["date"] and not in_cycle(parts["date"]):
        stats["out_of_cycle_rows"] += 1
        stats["out_of_cycle_cents"] += amount
    sub = parts["sub_id"]
    if sub:
        if sub in seen:
            stats["duplicate_sub_id"] += 1
            if source == "pas2":
                stats["pas2_already_in_oth"] += 1
            return
        seen.add(sub)
    else:
        stats["missing_sub_id"] += 1
    classified = classify_payee(
        parts["entity"], parts["other_id"], parts["name"],
        parts.get("txn_type"), category if category is not None else parts.get("category"),
        master, parts.get("purpose") or "",
    )
    # classify_payee must not be handed through to storage when it is a person bucket:
    # the name field on a bucket result is None.
    key = (classified["payee_key"], classified["edge_kind"])
    bucket = agg[cid]
    rec = bucket.get(key)
    if rec is None:
        rec = Acc(classified["payee_key"], classified["edge_kind"])
        bucket[key] = rec
    rec.add(amount, classified, parts["image"], sub, parts["file_num"], source)
    stats["aggregated_rows"] += 1
    stats["aggregated_cents"] += amount


def _scan(master, webk_ids):
    agg = {cid: {} for cid in webk_ids}
    seen = set()
    stats = {
        "memo_rows": 0, "memo_cents": 0, "receipt_rows": 0, "bad_amount_rows": 0,
        "zero_amount_rows": 0, "out_of_cycle_rows": 0, "out_of_cycle_cents": 0,
        "duplicate_sub_id": 0, "pas2_already_in_oth": 0, "missing_sub_id": 0,
        "aggregated_rows": 0, "aggregated_cents": 0,
        "rows_filer_not_in_pac_party_summary": 0,
        "unknown_types": {},
        "rows_read": {},
    }
    specs = (
        ("oth", oth_parts),
        ("pas2", pas2_parts),
        ("oppexp", oppexp_parts),
    )
    for source, parser in specs:
        path, z, fh = _open_member(source)
        n = 0
        try:
            for raw in fh:
                n += 1
                parts = parser(raw.decode("latin-1"))
                if not parts or not COMMITTEE_ID.match(parts["committee_id"]):
                    stats["bad_amount_rows"] += 0
                    stats.setdefault("short_rows", 0)
                    stats["short_rows"] = stats.get("short_rows", 0) + 1
                    continue
                _add(agg, seen, stats, parts, source, master, webk_ids)
                if n % 2000000 == 0:
                    print(" ", source, n, flush=True)
        finally:
            fh.close()
            z.close()
        stats["rows_read"][source] = n
        print(source, n, "rows", flush=True)
    if stats["unknown_types"]:
        listed = ", ".join("%s=%d" % (k or "(blank)", v) for k, v in sorted(stats["unknown_types"].items()))
        raise SystemExit(
            "unlisted transaction types in the OTH or PAS2 file (%s). "
            "They were not classified. No shards were written. "
            "Add a code only from the FEC transaction-type list."
            % listed
        )
    return agg, stats


def _committee_view(row, records):
    itemized = sum(int(r["amount_cents"]) for r in records)
    count = sum(int(r["count"]) for r in records)
    official = row["disbursements_cents"]
    return {
        "committee_id": row["committee_id"],
        "name": row["name"],
        "party": row["party"],
        "committee_type": row["committee_type"],
        "designation": row["designation"],
        "org_type": row["org_type"],
        "disbursements_cents": official,
        "itemized_count": count,
        "itemized_cents": itemized,
        "type_conflict": row["type_conflict"],
        "reconciled": official is not None and not over_official(itemized, official),
    }


def _file_meta():
    files = {}
    sidecar = RAW_DIR / "sources.json"
    saved = {}
    if sidecar.exists():
        saved = json.loads(sidecar.read_text()).get("files") or {}
    for key, url in FILE_URLS.items():
        path = RAW_DIR / Path(url).name
        entry = {
            "url": url,
            "description_url": DESC_URLS[key],
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "last_modified": (saved.get(key) or {}).get("last_modified"),
        }
        files[key] = entry
    return files


def build():
    retrieved_at = now_iso()
    print("load master", flush=True)
    master = _load_master()
    summaries, duplicate_ids, missing_total = _load_summaries(master)
    _check_layout(summaries)
    print("committees", len(summaries), "master", len(master), flush=True)
    webl_rows = _count_candidate_rows("webl")
    weball_rows = _count_candidate_rows("weball")
    print("scan disbursements", flush=True)
    agg, stats = _scan(master, set(summaries))
    views = []
    failures = []
    for cid, row in summaries.items():
        records = [rec.as_dict() for rec in agg[cid].values()]
        view = _committee_view(row, records)
        views.append(view)
        if not view["reconciled"]:
            delta = view["itemized_cents"] - row["disbursements_cents"]
            failures.append({
                "committee_id": cid,
                "name": row["name"],
                "official_total_out": cents_to_decimal(row["disbursements_cents"]),
                "itemized_disbursements": cents_to_decimal(view["itemized_cents"]),
                "itemized_minus_official": cents_to_decimal(delta),
                "itemized_minus_official_cents": delta,
                "reason": "Itemized non-memo disbursements exceed the official total disbursements in the PAC and party summary file.",
            })
    failures.sort(key=lambda r: (-r["itemized_minus_official_cents"], r["committee_id"]))
    chosen = select_pilot(views)
    chosen_ids = [c["committee_id"] for c in chosen]
    print("pilot", len(chosen_ids), "failures", len(failures), flush=True)

    PILOT_DIR.mkdir(parents=True, exist_ok=True)
    for old in PILOT_DIR.glob("*.json"):
        old.unlink()

    pilot_committees = []
    pilot_bytes = 0
    projected_bytes = 0
    projected_gzip = 0
    projected_committees = 0
    zero_committees = 0
    for view in views:
        if not view["reconciled"]:
            continue
        if view["disbursements_cents"] == 0 and view["itemized_cents"] == 0:
            zero_committees += 1
            continue
        cid = view["committee_id"]
        records = [rec.as_dict() for rec in agg[cid].values()]
        try:
            shard = build_shard(summaries[cid], records, retrieved_at, summaries, master=master)
        except ReconciliationError as exc:
            raise SystemExit(str(exc))
        encoded = json.dumps(shard, indent=1, ensure_ascii=False).encode("utf-8")
        projected_bytes += len(encoded)
        projected_gzip += len(gzip.compress(encoded, compresslevel=6))
        projected_committees += 1
        if cid in chosen_ids:
            path = PILOT_DIR / (cid + ".json")
            path.write_bytes(encoded)
            pilot_bytes += path.stat().st_size
            reason = next(c["reason"] for c in chosen if c["committee_id"] == cid)
            rule = next(c["rule"] for c in chosen if c["committee_id"] == cid)
            recn = shard["reconciliation"]
            pilot_committees.append({
                "committee_id": cid,
                "name": summaries[cid]["name"],
                "party": summaries[cid]["party"] or None,
                "committee_type": summaries[cid]["committee_type"],
                "designation": summaries[cid]["designation"],
                "org_type": summaries[cid]["org_type"] or None,
                "selection_rule": rule,
                "selection_reason": reason,
                "shard": "data/moneyflow/pilot/shards/%s.json" % cid,
                "shard_bytes": path.stat().st_size,
                "official_total_out": recn["official_total_out"],
                "child_edge_sum": cents_to_decimal(recn["child_edge_cents"]),
                "residual_other": cents_to_decimal(recn["other_bucket_cents"]),
                "individuals_bucket": cents_to_decimal(recn["individuals_cents"]),
                "not_in_itemized_files": cents_to_decimal(recn["not_in_itemized_files_cents"]),
                "coverage_end": summaries[cid]["coverage_end"],
                "reconciliation_ok": recn["ok"] is True and recn["child_edge_cents"] == recn["official_total_out_cents"],
            })
            if not pilot_committees[-1]["reconciliation_ok"]:
                raise SystemExit("pilot shard %s did not reconcile" % cid)

    missing_pilot = [cid for cid in chosen_ids if cid not in {p["committee_id"] for p in pilot_committees}]
    if missing_pilot:
        raise SystemExit("pilot committees were not written: %s" % ", ".join(missing_pilot))

    order = {cid: i for i, cid in enumerate(chosen_ids)}
    pilot_committees.sort(key=lambda p: order[p["committee_id"]])
    wording = wording_document()
    write_json(OUT_DIR / "wording.json", wording)
    manifest = {
        "schema": "politidex.moneyflow.manifest.v1",
        "cycle": CYCLE,
        "retrieved_at": retrieved_at,
        "fungibility_note": FUNGIBILITY_NOTE,
        "wording": wording,
        "not_in_web_bundle": False,
        "api": "No OpenFEC request is made. No API key is read.",
        "individual_contributions": "indiv* files are not downloaded or parsed.",
        "files": _file_meta(),
        "candidate_summary_files": {
            "used_as_committee_official_totals": False,
            "webl_data_rows": webl_rows,
            "weball_data_rows": weball_rows,
            "election_result_columns_read": False,
            "reason": (
                "The current-campaigns file and the all-candidates file are one row per candidate, "
                "have no committee id, and the FEC description says a candidate with more than one "
                "authorized committee is combined and can double-count transfers between those committees. "
                "Candidate names and election-result columns are not read."
            ),
        },
        "memo_code": (
            "Rows with memo code X are excluded from edge amounts. "
            "The FEC field description says that code is not incorporated into the total on the summary page."
        ),
        "pas2": (
            "The contributions-to-candidates file is a subset of the any-transaction file. "
            "Both files are read. A pas2 row whose SUB_ID was already aggregated from the any-transaction file is not added again."
        ),
        "privacy": (
            "Entity types IND and CAN are summed into the individuals residual bucket and the payee name is not stored. "
            "A blank, unrecognized, or conflicting entity type is summed into the other residual bucket and the name is not stored. "
            "Street, city, ZIP, employer, occupation, memo text, treasurer, and candidate id are not stored."
        ),
        "selection_rules": [c["reason"] for c in chosen],
        "pilot": pilot_committees,
        "reconciliation_failures": failures,
        "duplicate_summary_rows_dropped": duplicate_ids,
        "summary_total_missing_dropped": len(missing_total),
        "scan": {
            "rows_read": stats["rows_read"],
            "short_rows": stats.get("short_rows", 0),
            "memo_rows_excluded": stats["memo_rows"],
            "memo_cents_excluded": stats["memo_cents"],
            "receipt_rows_not_used_as_outflows": stats["receipt_rows"],
            "bad_amount_rows": stats["bad_amount_rows"],
            "zero_amount_rows": stats["zero_amount_rows"],
            "duplicate_sub_id_skipped": stats["duplicate_sub_id"],
            "pas2_rows_already_in_oth": stats["pas2_already_in_oth"],
            "missing_sub_id_rows_still_aggregated": stats["missing_sub_id"],
            "aggregated_rows": stats["aggregated_rows"],
            "aggregated_cents": stats["aggregated_cents"],
            "rows_whose_filer_is_not_in_the_pac_party_summary": stats["rows_filer_not_in_pac_party_summary"],
            "out_of_cycle_rows_included": stats["out_of_cycle_rows"],
            "out_of_cycle_cents_included": stats["out_of_cycle_cents"],
        },
        "sizes": {
            "pilot_committees": len(pilot_committees),
            "pilot_shard_bytes": pilot_bytes,
            "full_cycle_reconciled_committees_with_a_shard": projected_committees,
            "full_cycle_projected_shard_bytes": projected_bytes,
            "full_cycle_projected_gzip_bytes": projected_gzip,
            "committees_with_zero_official_and_zero_itemized": zero_committees,
            "reconciliation_failures": len(failures),
            "pac_and_party_committees_in_summary": len(summaries) + len(duplicate_ids),
            "note": (
                "Projected bytes are the JSON size, with the same indent as the pilot shards, "
                "of one top-payee shard for every PAC and party committee whose itemized non-memo "
                "disbursements fit under the official total and that reported a non-zero total or a non-zero itemized sum. "
                "The gzip figure uses Python gzip compresslevel 6 on those same bytes. "
                "Candidate-campaign committees are not in the projection."
            ),
        },
    }
    problems = public_problems(manifest)
    if problems:
        raise SystemExit("manifest failed the public-record check: %s" % "; ".join(problems[:8]))
    write_json(OUT_DIR / "pilot" / "manifest.json", manifest)
    print("wrote", len(pilot_committees), "pilot shards,", pilot_bytes, "bytes")
    print("projection", projected_committees, "committees,", projected_bytes, "bytes")
    print("failures", len(failures))
    for row in pilot_committees:
        print(
            row["committee_id"], row["official_total_out"],
            "other", row["residual_other"], "individuals", row["individuals_bucket"],
            row["shard_bytes"], "bytes",
        )


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "build"
    if cmd == "fetch":
        fetch(refresh="--refresh" in argv)
    elif cmd == "build":
        build()
    else:
        raise SystemExit("usage: python3 ingest/moneyflow.py fetch|build")


if __name__ == "__main__":
    main(sys.argv)
