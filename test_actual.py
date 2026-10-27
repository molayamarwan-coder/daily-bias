import json, os, urllib.request

def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

print("=== BLS ===")
try:
    body = json.dumps({"seriesid": ["CUSR0000SA0", "CES0000000001", "LNS14000000"]}).encode()
    d = get("https://api.bls.gov/publicAPI/v1/timeseries/data/", body)
    for s in d["Results"]["series"]:
        print(s["seriesID"], [(x["year"], x["periodName"], x["value"]) for x in s["data"][:3]])
except Exception as ex:
    print("FAILED", ex)

print("=== FRED ===")
key = os.environ.get("FRED_KEY", "")
if not key:
    print("skipped (no key)")
else:
    for sid in ["CPIAUCSL", "PAYEMS", "UNRATE", "ICSA", "DFEDTARGETU", "PCEPILFE"]:
        try:
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}&file_type=json&sort_order=desc&limit=3"
            d = get(url)
            print(sid, [(o["date"], o["value"]) for o in d["observations"]])
        except Exception as ex:
            print(sid, "FAILED", ex)
