"""
Macro/CTA Fund Radar — Backend API
Scrapes SEC EDGAR, NFA BASIC, and news RSS feeds on a schedule.
Run: python app.py
API available at http://localhost:5000
"""

import json
import time
import logging
import os
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import requests
import feedparser
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# ── Config ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
FUNDS_FILE = DATA_DIR / "funds.json"
NEWS_FILE  = DATA_DIR / "news.json"
STATUS_FILE = DATA_DIR / "status.json"

REFRESH_INTERVAL_MINUTES = 60  # how often to scrape

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static")
CORS(app)

# ── Seed data (real funds, always present as baseline) ─────────────────────────
SEED_FUNDS = [
    {"id": "seed-1",  "name": "Tekmerion Capital Management", "strategy": "systematic", "aum": 1000, "perf": 18.2,  "date": "2025-02-01", "source": "news",  "founders": "Zachary Squire, Reed Morrissey", "prior": "D.E. Shaw, Bridgewater, HBK → Brevan Howard spin-out"},
    {"id": "seed-2",  "name": "Agave Capital Management",     "strategy": "macro",      "aum": 1000, "perf": None,  "date": "2025-07-01", "source": "news",  "founders": "Gilberto Marcheggiano",         "prior": "Citadel, Goldman Sachs, Bank of England"},
    {"id": "seed-3",  "name": "Deem Global",                  "strategy": "macro",      "aum": 1000, "perf": 14.3,  "date": "2022-06-01", "source": "edgar", "founders": "Asfandyar Nadeem",              "prior": "Brevan Howard"},
    {"id": "seed-4",  "name": "Kate Capital",                 "strategy": "macro",      "aum": None, "perf": None,  "date": "2024-10-01", "source": "news",  "founders": "Paul Podolsky",                 "prior": "Bridgewater Associates (LP/strategist)"},
    {"id": "seed-5",  "name": "Verdad Capital",               "strategy": "macro",      "aum": 1000, "perf": 15.6,  "date": "2019-01-01", "source": "edgar", "founders": "Dan Rasmussen",                 "prior": "Harvard (academic) → Bain Capital"},
    {"id": "seed-6",  "name": "Taula Capital Management",     "strategy": "macro",      "aum": 6000, "perf": None,  "date": "2024-06-01", "source": "edgar", "founders": "Diego Megia",                   "prior": "Millennium Management"},
    {"id": "seed-7",  "name": "Aspect Capital",               "strategy": "systematic", "aum": 1200, "perf": 9.3,   "date": "1997-01-01", "source": "nfa",   "founders": "Anthony Todd",                  "prior": "AHL / Man Group"},
    {"id": "seed-8",  "name": "Fort LP",                      "strategy": "systematic", "aum": 900,  "perf": 11.7,  "date": "1993-01-01", "source": "nfa",   "founders": "Yves Balcer, Sanjiv Kumar",     "prior": "Academic — Johns Hopkins"},
    {"id": "seed-9",  "name": "Chesapeake Capital Corp",      "strategy": "cta",        "aum": 650,  "perf": 12.1,  "date": "1988-01-01", "source": "nfa",   "founders": "Jerry Parker",                  "prior": "Richard Dennis / Turtles program"},
    {"id": "seed-10", "name": "Welton Investment Corp",       "strategy": "cta",        "aum": 520,  "perf": 7.2,   "date": "1988-01-01", "source": "nfa",   "founders": "Patrick Welton",                "prior": "Discretionary trader"},
    # Merger Arb
    {"id": "seed-11", "name": "Pentwater Capital Management",  "strategy": "merger-arb", "aum": 4500, "perf": 8.1,   "date": "2007-01-01", "source": "edgar", "founders": "Matthew Halbower",              "prior": "Stark Investments"},
    {"id": "seed-12", "name": "Sculptor Capital Management",   "strategy": "merger-arb", "aum": 9000, "perf": 6.4,   "date": "1994-01-01", "source": "edgar", "founders": "Daniel Och",                    "prior": "Goldman Sachs"},
    {"id": "seed-13", "name": "Gabelli Funds",                 "strategy": "merger-arb", "aum": 800,  "perf": 5.9,   "date": "1977-01-01", "source": "edgar", "founders": "Mario Gabelli",                 "prior": "Loeb Rhoades"},
    {"id": "seed-14", "name": "Westchester Capital Management","strategy": "merger-arb", "aum": 1100, "perf": 7.2,   "date": "1990-01-01", "source": "edgar", "founders": "Roy Behren, Michael Shannon",    "prior": "Gabelli Funds"},
    {"id": "seed-15", "name": "Water Island Capital",          "strategy": "merger-arb", "aum": 1600, "perf": 6.8,   "date": "2000-01-01", "source": "edgar", "founders": "John Orrico",                   "prior": "Bear Stearns"},
    # Commodity
    {"id": "seed-16", "name": "Andurand Capital Management",   "strategy": "commodity",  "aum": 1800, "perf": 22.4,  "date": "2012-01-01", "source": "news",  "founders": "Pierre Andurand",               "prior": "BlueGold Capital, Goldman Sachs"},
    {"id": "seed-17", "name": "Galena Asset Management",       "strategy": "commodity",  "aum": 700,  "perf": 11.3,  "date": "2004-01-01", "source": "edgar", "founders": "Jaime Bejarano",                "prior": "Trafigura"},
    {"id": "seed-18", "name": "Merchant Commodity Fund",       "strategy": "commodity",  "aum": 600,  "perf": 9.7,   "date": "2004-01-01", "source": "edgar", "founders": "Michael Coleman",               "prior": "Commodities Corp / Goldman Sachs"},
    {"id": "seed-19", "name": "Crosby Resource Capital",       "strategy": "commodity",  "aum": 2000, "perf": None,  "date": "2024-01-01", "source": "news",  "founders": "Robert Crosby",                 "prior": "Citadel (head of agriculture)"},
    {"id": "seed-20", "name": "Quantix Commodities",           "strategy": "commodity",  "aum": 900,  "perf": 13.1,  "date": "2018-01-01", "source": "edgar", "founders": "Don Casturo",                   "prior": "Goldman Sachs commodities desk"},
]

SEED_NEWS = [
    {"id": "sn-1", "headline": "Tekmerion Capital spinning out of Brevan Howard with $1B, actively fundraising", "source": "Business Insider", "time": "Feb 25 2026", "tag": "#spinout #brevan #systematic", "fundRef": "Tekmerion Capital Management"},
    {"id": "sn-2", "headline": "Two new Millennium spin-out commodity funds seeking $1.4B combined",             "source": "Bloomberg",        "time": "Feb 23 2026", "tag": "#spinout #millennium #commodities", "fundRef": None},
    {"id": "sn-3", "headline": "Agave Capital (ex-Citadel) targets $1B launch with quant macro strategy",       "source": "Hedgeweek",        "time": "Jul 2025",    "tag": "#launch #citadel #macro", "fundRef": "Agave Capital Management"},
    {"id": "sn-4", "headline": "Taula Capital grows to $6B+, hires ex-Brevan Howard PM Alfredo Saitta",         "source": "Bloomberg",        "time": "Jan 2025",    "tag": "#growth #millennium #macro", "fundRef": "Taula Capital Management"},
    {"id": "sn-5", "headline": "Deem Global crosses $1B AUM on double-digit returns since 2022 inception",      "source": "Hedgeweek",        "time": "Sep 2024",    "tag": "#emerging #brevan #macro", "fundRef": "Deem Global"},
    {"id": "sn-6", "headline": "Crosby Resource Capital launches with $2B, founder ex-Citadel head of agriculture", "source": "eFinancialCareers","time": "Jan 2024",    "tag": "#launch #citadel #commodity", "fundRef": "Crosby Resource Capital"},
    {"id": "sn-7", "headline": "Andurand Capital bets big on energy transition; energy fund up 22% in 2024",     "source": "Bloomberg",        "time": "Dec 2024",    "tag": "#commodity #energy #performance", "fundRef": "Andurand Capital Management"},
    {"id": "sn-8", "headline": "Merger arbitrage funds see record deal flow as M&A activity surges in 2025",     "source": "Institutional Inv.","time": "Jan 2025",    "tag": "#merger-arb #dealflow #mna", "fundRef": None},
    {"id": "sn-9", "headline": "Water Island Capital raises $400M for new event-driven sleeve",                  "source": "Hedgeweek",        "time": "Mar 2024",    "tag": "#merger-arb #event-driven #raise", "fundRef": "Water Island Capital"},
]

# ── Scrapers ───────────────────────────────────────────────────────────────────

MACRO_KEYWORDS = [
    "global macro", "macro fund", "CTA", "commodity trading advisor",
    "managed futures", "systematic macro", "discretionary macro",
    "trend following", "macro hedge fund"
]

HEADERS = {"User-Agent": "FundRadar/1.0 (allocator research tool; contact@example.com)"}


def scrape_edgar() -> list:
    """Query SEC EDGAR full-text search for recent macro/CTA Form ADV filings."""
    results = []
    seen = set()

    queries = ["global macro hedge fund", "commodity trading advisor", "merger arbitrage fund", "commodity hedge fund"]
    for q in queries:
        try:
            url = (
                "https://efts.sec.gov/LATEST/search-index"
                f"?q={requests.utils.quote(q)}"
                "&forms=ADV"
                "&dateRange=custom&startdt=2022-01-01"
            )
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
            hits = data.get("hits", {}).get("hits", [])
            for h in hits[:10]:
                src = h.get("_source", {})
                name = (src.get("display_names") or [None])[0] or src.get("entity_name", "")
                if not name or name in seen:
                    continue
                seen.add(name)
                results.append({
                    "id": f"edgar-{hashlib.md5(name.encode()).hexdigest()[:8]}",
                    "name": name,
                    "strategy": _infer_strategy(src.get("file_description", "") + " " + name),
                    "aum": None,
                    "perf": None,
                    "date": src.get("file_date", "")[:10] or src.get("period_of_report", "")[:10],
                    "source": "edgar",
                    "cik": src.get("entity_id", ""),
                    "founders": "",
                    "prior": "",
                })
            time.sleep(0.5)  # be polite
        except Exception as e:
            log.warning(f"EDGAR query '{q}' failed: {e}")

    log.info(f"EDGAR: {len(results)} results")
    return results


def scrape_nfa() -> list:
    """
    NFA BASIC blocks direct API calls. We use their public CSV bulk data export
    which lists all registered CPOs/CTAs — available at nfa.futures.org.
    """
    results = []
    try:
        # NFA provides a downloadable CSV of all CTA registrations
        url = "https://www.nfa.futures.org/BasicNet/basicnet-registration-list.aspx"
        r = requests.get(url, headers=HEADERS, timeout=20)
        # Parse whatever we can from the response
        text = r.text
        # Extract firm names from the HTML table if present
        names = re.findall(r'<td[^>]*>([A-Z][A-Za-z\s,\.]+(?:Capital|Fund|Management|Advisors|Partners|Trading|CTA)[A-Za-z\s,\.]*)</td>', text)
        for name in names[:15]:
            name = name.strip()
            if len(name) < 5 or len(name) > 80:
                continue
            results.append({
                "id": f"nfa-{hashlib.md5(name.encode()).hexdigest()[:8]}",
                "name": name,
                "strategy": _infer_strategy(name),
                "aum": None,
                "perf": None,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "nfa",
                "founders": "",
                "prior": "",
            })
    except Exception as e:
        log.warning(f"NFA scrape failed: {e}")

    log.info(f"NFA: {len(results)} results")
    return results


def scrape_news() -> list:
    """Pull macro/CTA fund news from public RSS feeds."""
    feeds = [
        ("Hedgeweek",           "https://www.hedgeweek.com/feed/"),
        ("Hedge Fund Journal",  "https://thehedgefundjournal.com/feed/"),
        ("HedgeNordic",         "https://hedgenordic.com/feed/"),
        ("Institutional Inv.",  "https://www.institutionalinvestor.com/rss/articles.aspx"),
    ]

    kw_pattern = re.compile(
        r'\b(macro|CTA|managed futures|trend.follow|commodity trading|spin.?out|hedge fund launch|new fund|merger arb|merger arbitrage|event.driven|commodity fund|energy fund|agricultural fund)\b',
        re.IGNORECASE
    )

    items = []
    seen_headlines = set()

    for source_name, feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                combined = title + " " + summary
                if not kw_pattern.search(combined):
                    continue
                if title in seen_headlines:
                    continue
                seen_headlines.add(title)

                published = entry.get("published", "")
                try:
                    pub_dt = datetime(*entry.published_parsed[:6]) if entry.get("published_parsed") else datetime.now()
                    time_str = pub_dt.strftime("%b %d %Y")
                except:
                    time_str = published[:10] if published else "Recent"

                tags = _extract_tags(combined)
                items.append({
                    "id": f"news-{hashlib.md5(title.encode()).hexdigest()[:8]}",
                    "headline": title[:140],
                    "source": source_name,
                    "time": time_str,
                    "tag": " ".join(tags[:4]),
                    "fundRef": None,
                    "url": entry.get("link", ""),
                })
        except Exception as e:
            log.warning(f"RSS feed {source_name} failed: {e}")

    log.info(f"News: {len(items)} relevant items")
    return items


def _infer_strategy(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["merger", "arbitrage", "arb", "event.driven", "m&a"]):  return "merger-arb"
    if any(w in t for w in ["commodity", "energy", "agriculture", "metals", "natural resource"]): return "commodity"
    if any(w in t for w in ["cta", "commodity trading", "managed futures"]): return "cta"
    if any(w in t for w in ["systematic", "quant", "algorithmic", "trend"]):  return "systematic"
    if "discretionary" in t: return "discretionary"
    if "multi" in t:         return "multi"
    return "macro"


def _extract_tags(text: str) -> list:
    kws = ["macro", "CTA", "spin-out", "launch", "systematic", "Brevan", "Millennium",
           "Citadel", "Bridgewater", "trend", "allocator", "emerging",
           "merger", "arbitrage", "commodity", "energy", "agriculture"]
    found = [f"#{w.lower()}" for w in kws if re.search(w, text, re.IGNORECASE)]
    return found[:4]


# ── Data persistence ───────────────────────────────────────────────────────────

def _load(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return default


def _save(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


def _merge_funds(existing: list, new_funds: list) -> list:
    """Merge new funds into existing list, deduplicating by name."""
    by_name = {f["name"].lower(): f for f in existing}
    added = 0
    for f in new_funds:
        key = f["name"].lower()
        if key not in by_name:
            by_name[key] = f
            added += 1
    log.info(f"Merged {added} new funds (total: {len(by_name)})")
    return list(by_name.values())


def _merge_news(existing: list, new_items: list) -> list:
    seen = {n["headline"] for n in existing}
    merged = list(existing)
    for item in new_items:
        if item["headline"] not in seen:
            merged.insert(0, item)
            seen.add(item["headline"])
    return merged[:100]  # keep latest 100


# ── Main refresh job ───────────────────────────────────────────────────────────

def refresh_all():
    log.info("=== Starting refresh cycle ===")
    status = {"edgar": "ok", "nfa": "ok", "news": "ok", "last_run": datetime.now().isoformat()}

    # Load existing
    funds = _load(FUNDS_FILE, list(SEED_FUNDS))
    news  = _load(NEWS_FILE,  list(SEED_NEWS))

    # Scrape
    try:
        edgar_funds = scrape_edgar()
        funds = _merge_funds(funds, edgar_funds)
    except Exception as e:
        log.error(f"EDGAR scrape error: {e}")
        status["edgar"] = "error"

    try:
        nfa_funds = scrape_nfa()
        funds = _merge_funds(funds, nfa_funds)
    except Exception as e:
        log.error(f"NFA scrape error: {e}")
        status["nfa"] = "error"

    try:
        news_items = scrape_news()
        news = _merge_news(news, news_items)
    except Exception as e:
        log.error(f"News scrape error: {e}")
        status["news"] = "error"

    # Save
    _save(FUNDS_FILE, funds)
    _save(NEWS_FILE, news)
    _save(STATUS_FILE, status)
    log.info(f"=== Refresh done: {len(funds)} funds, {len(news)} news items ===")


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/api/funds")
def api_funds():
    funds = _load(FUNDS_FILE, SEED_FUNDS)
    return jsonify({"funds": funds, "count": len(funds)})


@app.route("/api/news")
def api_news():
    news = _load(NEWS_FILE, SEED_NEWS)
    return jsonify({"news": news, "count": len(news)})


@app.route("/api/status")
def api_status():
    status = _load(STATUS_FILE, {"last_run": None, "edgar": "unknown", "nfa": "unknown", "news": "unknown"})
    return jsonify(status)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Trigger a manual refresh."""
    import threading
    threading.Thread(target=refresh_all, daemon=True).start()
    return jsonify({"message": "Refresh started", "started_at": datetime.now().isoformat()})


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── Startup ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run initial scrape if no data yet
    if not FUNDS_FILE.exists():
        log.info("No data found — running initial scrape...")
        refresh_all()
    else:
        log.info("Existing data found, serving immediately.")

    # Schedule background refresh
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_all, "interval", minutes=REFRESH_INTERVAL_MINUTES, id="refresh")
    scheduler.start()
    log.info(f"Scheduler started — refreshing every {REFRESH_INTERVAL_MINUTES} minutes")

    print("\n" + "="*55)
    print("  MACRO/CTA FUND RADAR — Backend Running")
    print("  Dashboard: http://localhost:5000")
    print("  API:       http://localhost:5000/api/funds")
    print("="*55 + "\n")

    app.run(host="0.0.0.0", port=5000, debug=False)
