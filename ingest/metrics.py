"""Politi-Matrix v1 record metrics. Shared by build.py and verify.py so the verifier recomputes identically."""
import re, collections
PROC = re.compile(r"cloture|motion to proceed|previous question|ordering the previous|motion to table|on the motion to recommit|motion to commit|rule|waive", re.I)
PASS = re.compile(r"on passage|passage of the bill|on the joint resolution|suspend the rules and pass|on the resolution|concur|agree to the conference|on the bill", re.I)

def member_metrics(bid, votes):
    """votes: list of roll-call dicts with positions and party, in chronological order."""
    lst = [(v, v["positions"][bid]) for v in votes if bid in v["positions"]]
    total = len(lst)
    nv = sum(1 for _, p in lst if p == "NV"); pres = sum(1 for _, p in lst if p == "P")
    pl_n = pl_with = 0
    for v, pos in lst:
        pt = v.get("party", {}).get(bid)
        if not pt or pt in ("I", "ID") or pos not in ("Y", "N"): continue
        if "_tally" not in v:
            t = collections.Counter((v["party"].get(k), q) for k, q in v["positions"].items())
            v["_tally"] = t
        ys = v["_tally"][(pt, "Y")]; ns = v["_tally"][(pt, "N")]
        if ys == ns: continue
        pl_n += 1; pl_with += (pos == ("Y" if ys > ns else "N"))
    byleg = collections.defaultdict(lambda: {"proc": [], "pass": []})
    for v, pos in lst:
        if not v["legis"] or pos not in ("Y", "N"): continue
        q = v["question"] or ""
        if PASS.search(q) and not PROC.search(q): byleg[v["legis"]]["pass"].append(pos)
        elif PROC.search(q) and not re.search(r"motion to table|recommit", q, re.I): byleg[v["legis"]]["proc"].append(pos)
    div, base = [], 0
    for lg, d in byleg.items():
        if d["proc"] and d["pass"]:
            base += 1
            if len(set(d["proc"])) == 1 and set(d["proc"]) != {d["pass"][-1]}: div.append(lg)
    return {"lst": lst, "missed": [nv, total], "present": pres, "party_line": [pl_with, pl_n], "divergence": [len(div), base], "div_items": div}
