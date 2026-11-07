# Fund Radar — backend snapshot

An earlier Flask backend for collecting fund leads from public search results, NFA pages and RSS headlines. For the version with a browser dashboard, see [Fund Radar](https://github.com/nmwjs98h9j-bit/take6-octo-guide).

## Run the API

Use Python 3.11 and an isolated environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

The API listens on port 5000. Available routes are `GET /api/funds`, `GET /api/news`, `GET /api/status` and `POST /api/refresh`.

This snapshot does not include `static/index.html`, so its root dashboard route cannot serve a page. Data is cached as JSON under `data/`, configurable through `DATA_DIR`.

## Behaviour and limits

Direct execution starts hourly collection. Gunicorn imports `app:app` without starting that scheduler. Collection is best-effort; bundled records and figures are sample content, not verified live data. The refresh route has no access control, and concurrent JSON writes are not coordinated. Keep this snapshot for reference rather than treating it as a complete deployment.
