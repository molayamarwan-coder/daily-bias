import json, time, calendar
import datetime as dt
import urllib.parse
import feedparser
from transformers import pipeline

GENERIC_FEEDS = {
    "CNBC": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "FXStreet": "https://www.fxstreet.com/rss/news",
    "Investing": "https://www.investing.com/rss/news.rss",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
}

ASSETS = {
    "gold": {"name": "Gold (XAUUSD)", "query": "gold price OR XAUUSD",
             "keywords": ["gold", "xau", "bullion", "safe haven", "fed ", "yields", "dollar", "inflation", "rate cut", "rate hike"]},
    "nas": {"name": "Nasdaq 100", "query": "Nasdaq 100",
            "keywords": ["nasdaq", "tech", "nvidia", "apple", "microsoft", "amazon", "alphabet", "tesla", "chip", "semiconductor"]},
    "spx": {"name": "S&P 500", "query": "S&P 500",
            "keywords": ["s&p", "wall street", "stock market", "earnings", "equities"]},
    "dow": {"name": "Dow Jones", "query": "Dow Jones",
            "keywords": ["dow", "wall street", "industrial", "boeing", "caterpillar"]},
    "dax": {"name": "DAX 40", "query": "DAX Germany stocks",
            "keywords": ["dax", "germany", "german", "europe", "european", "ecb"]},
}

GOLD_FLIP = ["dollar", "yields", "treasury"]
MIN_NEWS = 8

print("Loading FinBERT...")
clf = pipeline("text-classification", model="ProsusAI/finbert", top_k=None, truncation=True)
now = time.time()

def read_feed(url, source=None, max_age=72):
    out = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:50]:
            ts = calendar.timegm(e.published_parsed) if getattr(e, "published_parsed", None) else now
            age_h = (now - ts) / 3600
            if age_h > max_age:
                continue
            title = e.get("title", "").strip()
            src = source
            if source == "Google News" and " - " in title:
                title, src = title.rsplit(" - ", 1)
            if title:
                out.append({"title": title, "text": (title + " " + e.get("summary", "")).lower(),
                            "source": src or "News", "age_h": age_h})
    except Exception as ex:
        print("FAILED", url, ex)
    return out

generic = []
for name, url in GENERIC_FEEDS.items():
    items = read_feed(url, name)
    print(name, len(items))
    generic += items

def score(title):
    out = clf(title)[0]
    d = {x["label"].lower(): x["score"] for x in out}
    return d.get("positive", 0) - d.get("negative", 0)

def age_label(h):
    return f"{int(h*60)} min" if h < 1 else f"{int(h)} h"

result = {"updated": dt.datetime.utcnow().isoformat() + "Z", "assets": {}}

for key, a in ASSETS.items():
    gurl = "https://news.google.com/rss/search?q=" + urllib.parse.quote_plus(a["query"] + " when:2d") + "&hl=en-US&gl=US&ceid=US:en"
    specific = read_feed(gurl, "Google News")
    filtered = [i for i in generic if any(k in i["text"] for k in a["keywords"])]
    seen, matched = set(), []
    for i in sorted(specific + filtered, key=lambda i: i["age_h"]):
        k = i["title"].lower()[:80]
        if k in seen:
            continue
        seen.add(k)
        matched.append(i)
    matched = matched[:30]

    bull = neu = bear = 0.0
    news = []
    for i in matched:
        s = score(i["title"])
        low = i["title"].lower()
        if key == "gold" and any(w in low for w in GOLD_FLIP) and "gold" not in low and "xau" not in low:
            s = -s
        w = 1 / (1 + i["age_h"] / 12)
        if s > 0.2: bull += w
        elif s < -0.2: bear += w
        else: neu += w
        news.append({"title": i["title"], "source": i["source"], "age": age_label(i["age_h"]), "score": round(s, 2)})

    total = bull + neu + bear
    if total == 0:
        result["assets"][key] = {"name": a["name"], "bullish": 0, "neutral": 0, "bearish": 0,
                                 "bias": "Low confidence", "count": 0, "news": []}
        continue
    pb, pn, pr = round(bull/total*100), round(neu/total*100), round(bear/total*100)
    bias = "Bullish" if pb >= pr + 15 else "Bearish" if pr >= pb + 15 else "Mixed"
    if len(matched) < MIN_NEWS:
        bias = "Low confidence"
    result["assets"][key] = {"name": a["name"], "bullish": pb, "neutral": pn, "bearish": pr,
                             "bias": bias, "count": len(matched), "news": news[:12]}
    print(a["name"], bias, pb, pn, pr, f"({len(matched)} headlines)")

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("Done")
