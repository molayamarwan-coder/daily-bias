import json, time, urllib.request, urllib.parse
import datetime as dt
from zoneinfo import ZoneInfo

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

_pipe = None
def local_tr(text):
    global _pipe
    if _pipe is None:
        from transformers import pipeline
        _pipe = pipeline("translation", model="Helsinki-NLP/opus-mt-en-ar")
    return _pipe(text, max_length=200)[0]["translation_text"]

google_fails = 0
def translate(text):
    global google_fails
    if google_fails < 2:
        try:
            q = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "ar", "dt": "t", "q": text})
            res = fetch("https://translate.googleapis.com/translate_a/single?" + q)
            out = "".join(p[0] for p in res[0] if p[0]); time.sleep(1)
            if out:
                return out
        except Exception as ex:
            google_fails += 1
            print("google translate failed:", ex)
    try:
        return local_tr(text)
    except Exception as ex:
        print("local translate failed:", ex)
        return ""

data = load("data.json", None)
cache = load("translations.json", {})
newcache = {}
done = fresh = 0
for a in data["assets"].values():
    for n in a["news"]:
        t = n["title"]
        ar = cache.get(t, "")
        if not ar:
            ar = translate(t)
            if ar:
                fresh += 1
        if ar:
            newcache[t] = ar
            n["title_ar"] = ar
            done += 1
        num, unit = n["age"].split()
        n["age_ar"] = num + (" دقيقة" if unit == "min" else " ساعة")
print("translated titles:", done, "| new this run:", fresh)
save("translations.json", newcache)
save("data.json", data)

now = dt.datetime.now(dt.timezone.utc)
day = now.strftime("%Y-%m-%d")
hist = load("history.json", {"days": {}})
d = hist["days"].setdefault(day, {"snaps": []})
d["snaps"].append({"t": now.strftime("%H:%M"),
                   "a": {k: [v["bullish"], v["neutral"], v["bearish"], v["bias"], v.get("count", 0)]
                         for k, v in data["assets"].items()}})

open_utc = dt.datetime.combine(now.date(), dt.time(9, 30), tzinfo=ZoneInfo("America/New_York")).astimezone(dt.timezone.utc)
pre = [i for i, s in enumerate(d["snaps"])
       if dt.datetime.fromisoformat(day + "T" + s["t"] + ":00+00:00") < open_utc]
d["pre"] = pre[-1] if pre else None

SYM = {"gold": "GC=F", "nas": "^NDX", "spx": "^GSPC", "dow": "^DJI", "dax": "^GDAXI"}
out = {}
for k, s in SYM.items():
    try:
        r = fetch("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(s) + "?range=5d&interval=1d")["chart"]["result"][0]
        off = r["meta"].get("gmtoffset", 0)
        pairs = [(t, c) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None]
        last_day = (dt.datetime.utcfromtimestamp(pairs[-1][0] + off)).strftime("%Y-%m-%d")
        today_local = (now + dt.timedelta(seconds=off)).strftime("%Y-%m-%d")
        if len(pairs) >= 2 and last_day == today_local:
            out[k] = round((pairs[-1][1] / pairs[-2][1] - 1) * 100, 2)
    except Exception as ex:
        print("yahoo failed", s, ex)
if out:
    d["out"] = out

for old in sorted(hist["days"])[:-90]:
    del hist["days"][old]
save("history.json", hist)
print("snapshots today:", len(d["snaps"]), "| pre-open index:", d["pre"], "| moves:", out)
