import json, time, calendar
import datetime as dt
import feedparser
from transformers import pipeline

FEEDS = {
    "CNBC": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "FXStreet": "https://www.fxstreet.com/rss/news",
    "Investing": "https://www.investing.com/rss/news.rss",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
}

ASSETS = {
    "gold": {"name": "Gold (XAUUSD)", "keywords": ["gold", "xau", "bullion", "precious metal", "safe haven", "fed ", "yields", "dollar", "inflation", "rate cut", "rate hike"]},
    "nas": {"name": "Nasdaq 100", "keywords": ["nasdaq", "tech", "nvidia", "apple", "microsoft", "amazon", "google", "alphabet", "meta ", "tesla", "chip", "semiconductor", "ai "]},
    "spx": {"name": "S&P 500", "keywords": ["s&p", "wall street", "stocks", "stock market", "earnings", "fed ", "equities"]},
    "dow": {"name": "Dow Jones", "keywords": ["dow", "wall street", "stocks", "industrial", "boeing", "caterpillar", "earnings"]},
    "dax": {"name": "DAX 40", "keywords": ["dax", "germany", "german", "europe", "european", "ecb", "euro "]},
}

# Kalimat li kat-9lb l ma3na 3la Gold (dollar/yields tla3 = Gold bearish)
GOLD_FLIP = ["dollar", "yields", "treasury"]

print("Loading FinBERT...")
clf = pipeline("text-classification", model="ProsusAI/finbert", top_k=None, truncation=True)

now = time.time()
items = []
for source, url in FEEDS.items():
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:40]:
            ts = calendar.timegm(e.published_parsed) if getattr(e, "published_parsed", None) else now
            age_h = (now - ts) / 3600
            if age_h > 48:
                continue
            title = e.get("title", "").strip()
            text = (title + " " + e.get("summary", "")).lower()
            if title:
                items.append({"title": title, "text": text, "source": source, "age_h": age_h})
        print(source, "OK")
    except Exception as ex:
        print(source, "FAILED", ex)

def score(title):
    out = clf(title)[0]
    d = {x["label"].lower(): x["score"] for x in out}
    return d.get("positive", 0) - d.get("negative", 0)

def age_label(h):
    return f"{int(h*60)} min" if h < 1 else f"{int(h)} h"

result = {"updated": dt.datetime.utcnow().isoformat() + "Z", "assets": {}}

for key, a in ASSETS.items():
    matched = [i for i in items if any(k in i["text"] for k in a["keywords"])]
    matched.sort(key=lambda i: i["age_h"])
    matched = matched[:25]
    bull = neu = bear = 0.0
    news = []
    for i in matched:
        s = score(i["title"])
        if key == "gold" and any(w in i["title"].lower() for w in GOLD_FLIP):
            s = -s
        w = 1 / (1 + i["age_h"] / 12)
        if s > 0.2: bull += w
        elif s < -0.2: bear += w
        else: neu += w
        news.append({"title": i["title"], "source": i["source"], "age": age_label(i["age_h"]), "score": round(s, 2)})
    total = bull + neu + bear
    if total == 0:
        result["assets"][key] = {"name": a["name"], "bullish": 0, "neutral": 0, "bearish": 0, "bias": "No data", "news": []}
        continue
    pb, pn, pr = round(bull/total*100), round(neu/total*100), round(bear/total*100)
    bias = "Bullish" if pb >= pr + 15 else "Bearish" if pr >= pb + 15 else "Mixed"
    result["assets"][key] = {"name": a["name"], "bullish": pb, "neutral": pn, "bearish": pr, "bias": bias, "news": news[:8]}
    print(a["name"], bias, pb, pn, pr, f"({len(matched)} headlines)")

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("Done")
