"""Attach official FEC image, receipts, and bulk-file links to displayed money rows.

Does not change claims.json (excerpts, values, and checks stay as verified).
IMAGE_NUM is PAS2/OTH column 4 (0-based); FILE_NUM is column 18.
"""
import json, collections
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

UNP = RAW / "fec" / "unpacked"
SITE = BUILD / "site"

PAS2_BULK = "https://www.fec.gov/files/bulk-downloads/2026/pas226.zip"
PAS2_DESC = "https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/"
OTH_BULK = "https://www.fec.gov/files/bulk-downloads/2026/oth26.zip"
OTH_DESC = "https://www.fec.gov/campaign-finance-data/any-transaction-one-committee-another-file-description/"
IE_BULK = "https://www.fec.gov/files/bulk-downloads/2026/independent_expenditure_2026.csv"
IE_DESC = "https://www.fec.gov/campaign-finance-data/independent-expenditures-file-description/"

def img_url(num):
    num = (num or "").strip()
    return f"https://docquery.fec.gov/cgi-bin/fecimg/?{num}" if num else None

def receipts_url(giver, recip):
    return (f"https://www.fec.gov/data/receipts/?data_type=processed"
            f"&committee_id={recip}&contributor_id={giver}&two_year_transaction_period=2026")

def disbursements_url(giver, recip):
    return (f"https://www.fec.gov/data/disbursements/?committee_id={giver}"
            f"&recipient_committee_id={recip}&two_year_transaction_period=2026")

def ie_url(spender, cand):
    return (f"https://www.fec.gov/data/independent-expenditures/?data_type=processed"
            f"&q_spender={spender}&candidate_id={cand}&two_year_transaction_period=2026")

def parse_cm():
    out = {}
    path = UNP / "cm.txt"
    if not path.exists():
        return out
    for line in path.read_text(errors="replace").splitlines():
        c = line.split("|")
        if len(c) < 15:
            continue
        out[c[0].strip()] = {"committee_type": c[9].strip(), "designation": c[8].strip()}
    return out

def collect_images(pairs, path, col_ok=20):
    """pairs: set of (giver, recipient). Return dict key -> {images, files} (up to 3, non-memo)."""
    found = {k: {"images": [], "files": []} for k in pairs}
    if not path.exists():
        return found
    for line in path.open(errors="replace"):
        c = line.split("|")
        if len(c) < col_ok:
            continue
        if c[5].strip() != "24K":
            continue
        if c[19].strip() == "X":
            continue
        key = (c[0].strip(), c[15].strip())
        e = found.get(key)
        if not e:
            continue
        img = c[4].strip() if len(c) > 4 else ""
        fnum = c[18].strip() if len(c) > 18 else ""
        if img and img not in e["images"] and len(e["images"]) < 3:
            e["images"].append(img)
        if fnum and fnum not in e["files"] and len(e["files"]) < 3:
            e["files"].append(fnum)
    return found

def main():
    cm = parse_cm()
    profiles = list((SITE / "profiles").glob("*.json"))
    want_pas2, want_oth = set(), set()
    for p in profiles:
        pr = json.loads(p.read_text())
        for r in ((pr.get("ties") or {}).get("money") or {}).get("rows") or []:
            key = (r.get("giver_id"), r.get("recipient_id"))
            if not all(key):
                continue
            if r.get("source_file") == "oth":
                want_oth.add(key)
            else:
                want_pas2.add(key)
    orgs_dir = SITE / "orgs"
    # org members may not have giver/recipient; skip unless present
    print(f"pairs to enrich pas2={len(want_pas2)} oth={len(want_oth)}", flush=True)
    pas2 = collect_images(want_pas2, UNP / "itpas2.txt")
    oth = collect_images(want_oth, UNP / "itoth.txt")
    n_img = n_rows = 0
    for p in profiles:
        pr = json.loads(p.read_text())
        ties = pr.get("ties") or {}
        money = (ties.get("money") or {}).get("rows") or []
        changed = False
        for r in money:
            n_rows += 1
            gid, rid = r.get("giver_id"), r.get("recipient_id")
            meta = cm.get(gid) or {}
            if meta.get("committee_type"):
                r["committee_type"] = meta["committee_type"]
            if meta.get("designation"):
                r["designation"] = meta["designation"]
            src = r.get("source_file") or "pas2"
            bag = (oth if src == "oth" else pas2).get((gid, rid)) or {"images": [], "files": []}
            r["receipts_url"] = receipts_url(gid, rid)
            r["disbursements_url"] = disbursements_url(gid, rid)
            r["bulk_url"] = OTH_BULK if src == "oth" else PAS2_BULK
            r["bulk_description_url"] = OTH_DESC if src == "oth" else PAS2_DESC
            urls = [img_url(x) for x in bag["images"] if x]
            r["image_nums"] = bag["images"]
            r["image_urls"] = urls
            r["file_nums"] = bag["files"]
            if urls:
                n_img += 1
            changed = True
        for r in (ties.get("ie") or {}).get("rows") or []:
            r["bulk_url"] = IE_BULK
            r["bulk_description_url"] = IE_DESC
            if r.get("spender_id") and r.get("candidate_id"):
                r["disbursements_url"] = ie_url(r["spender_id"], r["candidate_id"])
            changed = True
        if changed:
            p.write_text(json.dumps(pr, indent=2, ensure_ascii=False) + "\n")
    # org members: add image_urls when the member claim is a money claim we can map
    # Build claim -> image_urls from profiles
    by_claim = {}
    for p in profiles:
        pr = json.loads(p.read_text())
        for r in ((pr.get("ties") or {}).get("money") or {}).get("rows") or []:
            if r.get("claim"):
                by_claim[r["claim"]] = {
                    "image_urls": r.get("image_urls") or [],
                    "receipts_url": r.get("receipts_url"),
                    "disbursements_url": r.get("disbursements_url"),
                    "bulk_url": r.get("bulk_url"),
                    "bulk_description_url": r.get("bulk_description_url"),
                }
    n_org = 0
    if orgs_dir.exists():
        for p in orgs_dir.glob("*.json"):
            o = json.loads(p.read_text())
            ch = False
            # org-level type/designation codes from cm
            cid = o.get("committee_id")
            if cid and cid in cm:
                o["committee_type"] = cm[cid].get("committee_type") or o.get("committee_type")
                o["designation"] = cm[cid].get("designation") or o.get("designation")
                ch = True
            for m in o.get("members") or []:
                extra = by_claim.get(m.get("claim"))
                if extra:
                    m.update({k: v for k, v in extra.items() if v})
                    ch = True
                    n_org += 1
            if ch:
                p.write_text(json.dumps(o, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"money_rows": n_rows, "rows_with_images": n_img, "org_members_updated": n_org}))

if __name__ == "__main__":
    main()
