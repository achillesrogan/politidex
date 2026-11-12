"""Congress.gov API v3 (Library of Congress): member detail, sponsored and cosponsored legislation.
Key: CONGRESS_API_KEY or DATA_GOV_API_KEY (sent as X-Api-Key header; never stored)."""
import sys, json, time
from common import *

BASE = "https://api.congress.gov/v3"
KEY = api_key("CONGRESS_API_KEY")

def get(path, cache):
    cache = RAW / "congress" / cache
    if cache.exists(): return json.loads(cache.read_text())
    st, b = fetch(f"{BASE}{path}", timeout=40, headers={"X-Api-Key": KEY, "Accept": "application/json"})
    time.sleep(0.3)
    if st != 200: return None
    d = json.loads(b); d["_retrieved_at"] = now_iso()
    cache.parent.mkdir(parents=True, exist_ok=True); cache.write_text(json.dumps(d))
    return d

if __name__ == "__main__":
    L = read_json(RAW / "legislators-current.json")
    import concurrent.futures as cf
    if len(sys.argv) > 1 and sys.argv[1] == "reverse": L = L[::-1]
    def one(p):
        b = p["id"]["bioguide"]
        get(f"/member/{b}?format=json", f"member/{b}.json")
        get(f"/member/{b}/sponsored-legislation?format=json&limit=250", f"sponsored/{b}.json")
        get(f"/member/{b}/cosponsored-legislation?format=json&limit=250", f"cosponsored/{b}.json")
    with cf.ThreadPoolExecutor(6) as ex:
        for n, _ in enumerate(ex.map(one, L)):
            if n % 50 == 0: print("members", n, flush=True)
    print("done", len(L))
