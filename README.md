# Macro/CTA Fund Radar

Automated dashboard that monitors SEC EDGAR, NFA BASIC, and news RSS feeds for new macro/CTA fund launches. Refreshes every 60 minutes automatically.

---

## What it does

- **SEC EDGAR** — queries Form ADV filings for new investment adviser registrations matching macro/CTA keywords
- **NFA BASIC** — scrapes CTA/CPO registrations
- **News feeds** — monitors Hedgeweek, Hedge Fund Journal, HedgeNordic, Institutional Investor RSS for launch announcements
- Deduplicates and merges results, persists to JSON, serves via REST API
- Dashboard auto-refreshes every 15 minutes from the API

---

## Run locally

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

---

## Deploy (free, always-on)

### Option A — Railway (recommended, ~2 min setup)
1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Select the repo — Railway auto-detects the Procfile
4. Done. You get a public URL like `https://fund-radar-xxx.railway.app`

### Option B — Render
1. Push to GitHub
2. render.com → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1`
5. Done.

### Option C — Fly.io
```bash
brew install flyctl
flyctl auth login
flyctl launch   # follow prompts
flyctl deploy
```

---

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/funds` | All detected funds (JSON) |
| `GET /api/news` | News signal feed (JSON) |
| `GET /api/status` | Source status + last run time |
| `POST /api/refresh` | Trigger immediate scrape |

---

## Customise

Edit `app.py` to adjust:
- `REFRESH_INTERVAL_MINUTES` — how often to scrape (default: 60)
- `MACRO_KEYWORDS` — keywords used to filter EDGAR results
- `SEED_FUNDS` — baseline fund list always shown

To add more news sources, append to the `feeds` list in `scrape_news()`.

---

## Notes

- SEC EDGAR and NFA have rate limits — the scraper uses polite delays
- NFA blocks direct API calls; the scraper uses their public HTML pages
- Bloomberg/Hedgeweek paywalled content won't be scraped — RSS headlines only
- All data is stored in `data/funds.json` and `data/news.json` (persists across restarts)
