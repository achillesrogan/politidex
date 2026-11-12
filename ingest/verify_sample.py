"""Dry-run: check a random sample of claims per kind (no writes). Used for spot checks and debugging."""
import random, sys, collections
import verify as V
from common import *
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
claims = read_json(BUILD / "site" / "claims.json")["claims"]
by = collections.defaultdict(list)
for c in claims.values(): by[c["check"]["kind"]].append(c)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
need_votes = False
res = collections.Counter(); notes = []
for kind, lst in by.items():
    if kind in ("derived-votes",): continue
    for c in random.sample(lst, min(n, len(lst))):
        vs = {}
        if kind in ("house-vote", "senate-vote"):
            st, b = V.live(c["check"]["url"])
            import xml.etree.ElementTree as ET
            r = ET.fromstring(b); pos = {}
            if kind == "house-vote":
                for rv in r.iter("recorded-vote"): x=(rv.findtext("vote") or "").strip(); pos[rv.find("legislator").get("name-id")] = V.V.MAP.get(x, x)
            else:
                for m in r.iter("member"):
                    bid = V.V.LIS2BIO.get((m.findtext("lis_member_id") or "").strip()); x=(m.findtext("vote_cast") or "").strip()
                    if bid: pos[bid] = V.V.MAP.get(x, x)
            vs = {c["check"]["url"]: {"positions": pos}}
        ok, note = V.check(c, vs)
        res[(kind, ok)] += 1
        if not ok: notes.append((kind, c["text"][:120], note))
print(dict(res))
for x in notes[:20]: print(x)
