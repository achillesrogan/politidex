"""Shared helpers for Politidex ingestion. API keys come only from env vars; never logged."""
import os, json, time, datetime, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BUILD = ROOT / "data" / "build"
UA = "Politidex-civic-research/0.1 (+https://politidex.icu; open-source non-profit)"

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

def api_key(name):
    """CONGRESS_API_KEY / FEC_API_KEY, falling back to DATA_GOV_API_KEY, then DEMO_KEY."""
    return os.environ.get(name) or os.environ.get("DATA_GOV_API_KEY") or "DEMO_KEY"

def fetch(url, headers=None, retries=4, timeout=60):
    h = {"User-Agent": UA}
    if headers: h.update(headers)
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 400, 403):
                return e.code, b""
            if e.code == 429:
                if retries == 1: return 429, b""
                time.sleep(30 * (i + 1)); continue
            time.sleep(3 * (i + 1))
        except Exception:
            time.sleep(3 * (i + 1))
    return 0, b""

def safe_url(url):
    """Strip api_key params before storing a URL anywhere."""
    import re
    return re.sub(r"([?&])api_key=[^&]*&?", r"\1", url).rstrip("?&")

def write_json(path, obj):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False))
    tmp.replace(path)

def read_json(path):
    return json.loads(pathlib.Path(path).read_text())
