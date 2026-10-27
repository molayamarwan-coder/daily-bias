import json, os, re, urllib.request, urllib.parse
import datetime as dt

FRED_KEY = os.environ.get("FRED_KEY", "")
ASSETS = ["gold", "nas", "spx", "dow", "dax"]

TPL = {
    "inflation": dict(gold=-1, idx=-1,
        up_en="Hotter inflation lifts rate-hike expectations and the dollar, which pressures gold and stocks.",
        down_en="Cooler inflation eases rate-hike fears and weakens the dollar, which supports gold and stocks.",
        up_ar="تضخم أعلى من المتوقع يرفع توقعات رفع الفائدة وقوة الدولار، مما يضغط على الذهب والأسهم.",
        down_ar="تضخم أقل من المتوقع يخفف مخاوف رفع الفائدة ويضعف الدولار، مما يدعم الذهب والأسهم."),
    "jobs": dict(gold=-1, idx=0,
        up_en="Strong hiring supports the dollar and yields (negative for gold); the effect on stocks is mixed.",
        down_en="Weak hiring weakens the dollar and raises rate-cut hopes (positive for gold); the effect on stocks is mixed.",
        up_ar="توظيف قوي يدعم الدولار والعوائد (سلبي للذهب)، وتأثيره على الأسهم متباين.",
        down_ar="توظيف ضعيف يضعف الدولار ويزيد آمال خفض الفائدة (إيجابي للذهب)، وتأثيره على الأسهم متباين."),
    "unemp": dict(gold=1, idx=0,
        up_en="Rising unemployment signals a softer economy and raises rate-cut hopes, supporting gold; stocks react in a mixed way.",
        down_en="Falling unemployment signals a stronger economy and supports the dollar, pressuring gold; stocks react in a mixed way.",
        up_ar="ارتفاع البطالة يشير إلى اقتصاد أضعف ويزيد آمال خفض الفائدة، مما يدعم الذهب، وردّ فعل الأسهم متباين.",
        down_ar="انخفاض البطالة يشير إلى اقتصاد أقوى ويدعم الدولار، مما يضغط على الذهب، وردّ فعل الأسهم متباين."),
    "rate": dict(gold=-1, idx=-1,
        up_en="A rate higher than expected is hawkish: stronger dollar and pressure on gold and stocks.",
        down_en="A rate lower than expected is dovish: weaker dollar and support for gold and stocks.",
        up_ar="فائدة أعلى من المتوقع موقف متشدد: دولار أقوى وضغط على الذهب والأسهم.",
        down_ar="فائدة أقل من المتوقع موقف متساهل: دولار أضعف ودعم للذهب والأسهم."),
}

RULES = {
    "cpi m/m": dict(tpl="inflation", series="CPIAUCSL", calc="mom", tol=0.05, ref="monthly",
        ar="مؤشر أسعار المستهلك (شهري)",
        what_en="Monthly change in consumer prices, the main inflation gauge the Fed and markets watch.",
        what_ar="التغير الشهري في أسعار المستهلك، وهو أهم مقياس للتضخم يتابعه الفيدرالي والأسواق."),
    "core cpi m/m": dict(tpl="inflation", series="CPILFESL", calc="mom", tol=0.05, ref="monthly",
        ar="مؤشر أسعار المستهلك الأساسي (شهري)",
        what_en="Monthly change in consumer prices excluding food and energy, a cleaner read of underlying inflation.",
        what_ar="التغير الشهري في أسعار المستهلك دون الغذاء والطاقة، وهو قراءة أوضح للتضخم الأساسي."),
    "cpi y/y": dict(tpl="inflation", series="CPIAUCSL", calc="yoy", tol=0.05, ref="monthly",
        ar="مؤشر أسعار المستهلك (سنوي)",
        what_en="Yearly change in consumer prices.",
        what_ar="التغير السنوي في أسعار المستهلك."),
    "non-farm employment change": dict(tpl="jobs", series="PAYEMS", calc="diff", tol=25, ref="monthly",
        ar="الوظائف غير الزراعية",
        what_en="Number of jobs added in the US economy last month (in thousands), the most watched jobs report.",
        what_ar="عدد الوظائف المضافة في الاقتصاد الأمريكي الشهر الماضي (بالآلاف)، وهو أكثر تقارير التوظيف متابعة."),
    "unemployment rate": dict(tpl="unemp", series="UNRATE", calc="level", tol=0.05, ref="monthly",
        ar="معدل البطالة",
        what_en="Share of the labor force that is unemployed.",
        what_ar="نسبة العاطلين عن العمل من إجمالي القوى العاملة."),
    "unemployment claims": dict(tpl="unemp", series="ICSA", calc="claims", tol=5, ref="weekly",
        ar="طلبات إعانة البطالة الأسبوعية",
        what_en="Weekly count of new jobless benefit claims (in thousands).",
        what_ar="العدد الأسبوعي لطلبات إعانة البطالة الجديدة (بالآلاف)."),
    "core pce price index m/m": dict(tpl="inflation", series="PCEPILFE", calc="mom", tol=0.05, ref="monthly",
        ar="مؤشر نفقات الاستهلاك الشخصي الأساسي (شهري)",
        what_en="The Fed's preferred inflation measure, excluding food and energy.",
        what_ar="مقياس التضخم المفضل لدى الفيدرالي، دون الغذاء والطاقة."),
    "federal funds rate": dict(tpl="rate", series="DFEDTARU", calc="level", tol=0.0, ref="any",
        ar="قرار سعر الفائدة الفيدرالي",
        what_en="The Fed's interest rate decision (upper bound of the target range).",
        what_ar="قرار الفيدرالي بشأن سعر الفائدة (الحد الأعلى للنطاق المستهدف)."),
}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def fred(sid):
    q = urllib.parse.urlencode({"series_id": sid, "api_key": FRED_KEY, "file_type": "json", "sort_order": "desc", "limit": 14})
    obs = get("https://api.stlouisfed.org/fred/series/observations?" + q)["observations"]
    return [(o["date"], float(o["value"])) for o in obs if o["value"] not in (".", "")]

def num(s):
    m = re.match(r"^\s*(-?[\d.]+)", s or "")
    return float(m.group(1)) if m else None

def compute(calc, obs):
    if calc == "mom": return (obs[0][1] / obs[1][1] - 1) * 100
    if calc == "yoy": return (obs[0][1] / obs[12][1] - 1) * 100
    if calc == "diff": return obs[0][1] - obs[1][1]
    if calc == "claims": return obs[0][1] / 1000
    return obs[0][1]

def fresh(ref, obs_date, ev_date):
    d = dt.date.fromisoformat(obs_date)
    if ref == "monthly":
        prev = ev_date.replace(day=1) - dt.timedelta(days=1)
        return (d.year, d.month) == (prev.year, prev.month)
    if ref == "weekly":
        return 0 <= (ev_date - d).days <= 10
    return True

def make_bias(t, actual, forecast, tol):
    s = actual - forecast
    if abs(s) <= tol:
        return s, {a: "neutral" for a in ASSETS}, "inline"
    up = s > 0
    out = {}
    for a in ASSETS:
        sign = t["gold"] if a == "gold" else t["idx"]
        out[a] = "mixed" if sign == 0 else ("bullish" if (sign > 0) == up else "bearish")
    return s, out, "up" if up else "down"

def load_events():
    events = []
    for u in ["thisweek", "nextweek"]:
        try:
            events += get(f"https://nfs.faireconomy.media/ff_calendar_{u}.json")
        except Exception as ex:
            print(u, "FAILED", ex)
    return events

now = dt.datetime.now(dt.timezone.utc)
out = []
unmatched = set()

for e in load_events():
    if e.get("impact") != "High" or e.get("country") not in ("USD", "EUR"):
        continue
    local = dt.datetime.fromisoformat(e["date"])
    when = local.astimezone(dt.timezone.utc)
    ev_date = local.date()
    title = e["title"]
    item = {"title": title, "title_ar": title, "country": e["country"], "time_utc": when.isoformat(),
            "forecast": e.get("forecast", ""), "previous": e.get("previous", ""), "actual": None,
            "status": "upcoming" if when > now else "released",
            "what_en": "High-impact event.", "what_ar": "حدث عالي التأثير.",
            "reason_en": "", "reason_ar": "", "bias": {a: "n/a" for a in ASSETS}}
    rule = RULES.get(title.lower())
    if not rule:
        unmatched.add(title)
        out.append(item)
        continue
    t = TPL[rule["tpl"]]
    item.update(title_ar=rule["ar"], what_en=rule["what_en"], what_ar=rule["what_ar"])
    if when <= now and FRED_KEY:
        try:
            obs = fred(rule["series"])
            if fresh(rule["ref"], obs[0][0], ev_date):
                actual = round(compute(rule["calc"], obs), 2)
                item["actual"] = actual
                fc = num(item["forecast"])
                if fc is not None:
                    s, bias, d = make_bias(t, actual, fc, rule["tol"])
                    item["bias"] = bias
                    if d == "inline":
                        item["reason_en"] = f"Actual {actual} is in line with the forecast {fc}, so little surprise."
                        item["reason_ar"] = f"القراءة {actual} مطابقة تقريبًا للتوقع {fc}، فلا مفاجأة تُذكر."
                    else:
                        w_en = "above" if d == "up" else "below"
                        w_ar = "أعلى" if d == "up" else "أقل"
                        item["reason_en"] = f"Actual {actual} vs forecast {fc}: {w_en} expectations. " + t[d + "_en"]
                        item["reason_ar"] = f"القراءة {actual} مقابل التوقع {fc}: {w_ar} من المتوقع. " + t[d + "_ar"]
                else:
                    item["reason_en"] = "No numeric forecast to compare with."
                    item["reason_ar"] = "لا يوجد توقع رقمي للمقارنة."
            else:
                item["status"] = "released_no_actual_yet"
        except Exception as ex:
            print("FRED failed for", title, ex)
    out.append(item)

out.sort(key=lambda x: x["time_utc"])
with open("calendar.json", "w", encoding="utf-8") as f:
    json.dump({"updated": now.isoformat(), "events": out}, f, ensure_ascii=False, indent=2)

print(f"{len(out)} high-impact events")
for x in out:
    print(x["time_utc"][:16], x["country"], x["title"], "| actual:", x["actual"], "| forecast:", x["forecast"], "|", x["status"])
print("Not matched to a rule:", sorted(unmatched))
