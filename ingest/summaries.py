"""Short source summaries: Verification Standard steps 3 and 4.

Drafting: an LLM (optional, env LLM_API_URL/LLM_API_KEY; not configured yet) or the built-in deterministic
template drafter receives ONLY verified claim objects and must tag every sentence with [claim:ID].
Second pass (sentence_check): rejects any sentence that
  - has no claim tag, or cites a claim that is not verified, or
  - contains a number, date, capitalized name or quoted phrase that does not appear in the cited claims' text/value/excerpt.
Output goes to data/review-queue/*.json with status 'pending_review'. Nothing auto-publishes:
the site renders only summaries a human editor has moved to status 'approved'."""
import re, json, sys
from common import *

QUEUE = ROOT / "data" / "review-queue"
TAG = re.compile(r"\[claim:(c_[0-9a-f]{14})\]")

def tokens(s):
    s = TAG.sub("", s)
    nums = set(re.findall(r"\$?\d[\d,\.]*%?", s))
    names = set(re.findall(r"\b[A-Z][a-zA-Z'’\.-]+(?:\s+[A-Z][a-zA-Z'’\.-]+)*", s))
    quotes = set(re.findall(r"“([^”]+)”|\"([^\"]+)\"", s))
    return nums, names, {q[0] or q[1] for q in quotes}

# Characterizations that need a primary record (and editor sign-off), never model inference.
LOADED = ["corrupt\\w*", "brib\\w*", "dark money", "influen\\w*", "control\\w*", "puppet", "owned", "kickback\\w*", "scandal\\w*", "illegal\\w*", "crim\\w*", "fraud\\w*", "secret\\w*", "pay-to-play", "quid pro quo", "foreign agent", "hypocri\\w*", "lie[sd]?", "lying"]
STOP = {"The", "On", "In", "He", "She", "They", "This", "Of", "And", "A", "An", "As", "During", "Since", "From", "Record", "Politidex"}

def sentence_check(text, claims):
    """Return (ok, problems). Every sentence needs >=1 verified claim tag and no facts beyond its claims."""
    problems = []
    # A sentence ends at its claim tag(s); trailing text without a tag becomes its own (failing) sentence.
    sentences = [s.strip() for s in re.split(r"(?<=\])\s+(?!\[claim:)", text.strip()) if s.strip()]
    for s in sentences:
        ids = TAG.findall(s)
        if not ids: problems.append(("no-claim", s)); continue
        cl = [claims.get(i) for i in ids]
        if any(c is None or c.get("status") != "verified" for c in cl): problems.append(("unverified-claim", s)); continue
        support = " ".join(f"{c['text']} {json.dumps(c['value'])} {c['excerpt']}" for c in cl)
        support_n = support.replace(",", "")
        nums, names, quotes = tokens(s)
        for n in nums:
            core = n.strip("$%").replace(",", "").rstrip(".")
            if core and core not in support_n: problems.append(("unsupported-number", f"{n} in: {s}"))
        for nm in names:
            if nm in STOP or nm.split()[0] in STOP and len(nm.split()) == 1: continue
            if nm not in support: problems.append(("unsupported-name", f"{nm} in: {s}"))
        for w in LOADED:
            if re.search(rf"\b{w}\b", s, re.I) and not re.search(rf"\b{w}\b", support, re.I): problems.append(("loaded-language", f"{w} in: {s}"))
        for q in quotes:
            if q not in support: problems.append(("unsupported-quote", f"{q} in: {s}"))
    return (not problems), problems

def template_draft(profile, claims):
    """Deterministic drafter: restates verified claims only (stand-in until an LLM is configured)."""
    out = []
    for f in profile.get("facts", [])[:3]:
        c = claims.get(f["claim"])
        if c and c["status"] == "verified": out.append(f"{c['text']} [claim:{c['id']}]")
    an = profile.get("analysis") or {}
    for k in ("missed", "party_line"):
        c = claims.get((an.get(k) or {}).get("claim"))
        if c and c["status"] == "verified": out.append(f"{c['text']} [claim:{c['id']}]")
    return " ".join(out)

if __name__ == "__main__":
    claims = read_json(BUILD / "site" / "claims.json")["claims"]
    import glob
    n_ok = n_bad = 0
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    for f in sorted(glob.glob(str(BUILD / "site" / "profiles" / "*.json")))[:limit]:
        pr = read_json(f); slug = pr["person"]["slug"]
        draft = template_draft(pr, claims)
        ok, probs = sentence_check(draft, claims)
        item = {"slug": slug, "drafted_at": now_iso(), "drafter": "template-v1", "text": draft,
                "second_pass": {"ok": ok, "problems": probs}, "status": "pending_review" if ok else "rejected"}
        write_json(QUEUE / f"{slug}.json", item)
        n_ok += ok; n_bad += (not ok)
    print("queued", n_ok, "rejected", n_bad)
