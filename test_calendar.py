import json, os, urllib.request, datetime as dt

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def report(name, events):
    n = len(events)
    with_actual = [e for e in events if e.get("actual") not in (None, "", "null")]
    print(f"\n=== {name}: {n} events, {len(with_actual)} with actual ===")
    for e in (with_actual[:5] or events[:3]):
        print(json.dumps(e, ensure_ascii=False)[:300])

# Source 1: faireconomy (mirror dyal calendar dyal ForexFactory)
for label, url in [("faireconomy thisweek", "https://nfs.faireconomy.media/ff_calendar_thisweek.json")]:
    try:
        report(label, get(url))
    except Exception as ex:
        print(f"\n=== {label}: FAILED {ex}")

# Source 2: Finnhub (khassha key mejjani f Secrets, ikhtiyari)
key = os.environ.get("FINNHUB_KEY", "")
if key:
    today = dt.date.today()
    url = f"https://finnhub.io/api/v1/calendar/economic?from={today - dt.timedelta(days=3)}&to={today}&token={key}"
    try:
        data = get(url)
        report("finnhub", data.get("economicCalendar", []) if isinstance(data, dict) else [])
    except Exception as ex:
        print(f"\n=== finnhub: FAILED {ex}")
else:
    print("\n=== finnhub: skipped (no key)")
