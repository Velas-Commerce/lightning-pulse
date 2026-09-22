# Lightning Pulse — Agent Guide

Real-time Bitcoin Lightning Network analytics dashboard, built by Velas Commerce. It combines data from the operator's own LND node (REST API) with the public Mempool.space API, and presents network health, topology, liquidity velocity, and growth metrics in a neon-styled React dashboard.

## Project Overview

Monorepo with two independently deployed services:

- **Backend** — FastAPI (Python 3.11+) at the repo root. Entry point `main.py`, run with uvicorn on port 8000. Read-only GET API; it proxies and caches external data, computes derived metrics, and optionally persists daily snapshots to MongoDB.
- **Frontend** — React 19 + TypeScript + Vite in `frontend/`. Dev server on port 5173; production build is a static site (`frontend/dist/`).

Data sources:

- **LND node** — `GET {LND_URL}/v1/graph` (full network graph, used for network metrics) and `/v1/graph/info`. Authenticated with a readonly macaroon (`Grpc-Metadata-Macaroon` header) and the node's TLS cert.
- **Mempool.space public API** — lightning statistics, nodes per country, largest nodes, BTC price (current and hourly historical prices).
- **Hardcoded growth data** — `services/growth_stats.py` contains manually curated figures from River/Breez reports. These are intentionally static, not fetched.

## Repository Layout

```
main.py                  FastAPI app: lifespan (DB connect + background refresh loop), CORS, router registration
db.py                    Optional MongoDB (pymongo AsyncMongoClient); disabled if MONGODB_URI is unset
models.py                All Pydantic response models
routers/                 HTTP layer only — one router per concern (health, lnd, mempool, growth_stats, history, report)
services/                Business logic: external API calls, caching, metric computation
scripts/                 One-shot maintenance scripts, kept out of the uvicorn import path
tls.cert                 LND node TLS certificate (gitignored, required locally unless TLS_CERT_B64 is used)
frontend/
  src/App.tsx            Dashboard grid; 60-second refresh via a `refreshKey` prop passed to all cards
  src/api.ts             One fetch function per backend endpoint; base URL from VITE_API_URL
  src/types.ts           TypeScript types mirroring backend models.py
  src/components/        One card component per dashboard section; TrendChart.tsx is the shared SVG trend chart (series helpers live in src/utils.ts)
  public/countries-110m.json   TopoJSON for the world-map component
  railway.json           Railway deployment config for the frontend
```

## Backend Architecture

- **Layering convention:** routers contain no logic — they call a service function and declare a `response_model` from `models.py`. Services handle HTTP calls to LND/Mempool.space and all computation.
- **Caching:** `cachetools.TTLCache(maxsize=1, ttl=N)` per upstream dataset in `services/mempool.py` and `services/lnd.py` (TTLs of 30 s – 5 min). Do not add per-request fetches without going through these caches — the frontend polls every 60 s and would hammer the upstream APIs.
- **Background metrics:** `services/graph_metrics.py` runs a `refresh_loop()` started in the FastAPI lifespan. It fetches the full LND graph (~43 MB, ~40k channels, 120 s timeout), computes `NetworkMetrics` (pulse score, Gini coefficient, top-10/top-100 centralization, median fee rate, median node degree), keeps the result in a module-level `_cache`, and persists a snapshot to MongoDB if connected. `/node/network-metrics` serves only this cache and returns 503 until the first computation finishes.
- **Snapshot schedule:** the loop runs once at boot and then at a **fixed 00:15 UTC** (`SNAPSHOT_HOUR_UTC` / `SNAPSHOT_MINUTE_UTC`), not every 24 h from process start — a drifting schedule would undermine the median+MAD baselines the report card rests on. Snapshots are **upserted by UTC `date`**, so a restart refreshes the day's document rather than appending a second one. Documents written before the `date` field existed have no date, never match, and are left alone; no migration was needed.
- **Channel opens:** `services/channel_flow.py` decodes the BOLT 7 short channel ID on every graph edge, which encodes the block that confirmed the funding transaction. One graph fetch therefore reconstructs the entire history of opens with no day-over-day diffing. Block heights are placed in time by a `BlockClock` built from mempool.space timestamps — exact for the last `EXACT_BLOCKS` (~3 days), interpolated between daily anchors before that. **Only exactly-timed days get hourly detail**; interpolated days carry `hourly: None`, because their day boundaries are good to within the hour but not the hour-bucket. Two caveats travel with every number: only channels *still open* are visible, so older days undercount, and this is our own node's gossip view, not the whole network.
- **LND offline behavior:** `/node/graph-info` returns 503 when the node is unreachable (`routers/lnd.py` translates `httpx` errors). The frontend `/node/*` fetchers throw on non-OK, and the affected cards degrade instead of crashing — Network Topology falls back to mempool.space-only data, Network Metrics shows an unavailable note.
- **Pulse score formula:** equity 35 % + decentralization 35 % + fee health 30 %. The scoring logic is duplicated on the frontend in `frontend/src/components/NetworkMetricsList.tsx` (`calcComponents`) — **keep both implementations in sync** when changing it.
- **Daily report card:** `routers/report.py` exposes `GET /report/daily`, served by `services/report_card.py` from the `daily_flow` collection. Baselines are **median + MAD**, not mean + stddev, because channel flow is spiky. The comparison window is derived from the data actually held (`window_days`), never hardcoded, so generated copy grows with the archive — and `BANNED_PHRASES` guards against "record"/"all-time" claims the ~3-month archive cannot support. While fewer than `MIN_LIVE_DAYS` live days exist, the verdict reports facts and makes no claim about significance, because backfilled days undercount. Run `python scripts/backfill_opens.py [days]` once after deploying to seed history; it marks days `is_backfilled: True` and never overwrites a day the live job recorded.
- **History:** `routers/history.py` exposes `/history/network-metrics`, `/history/graph-info`, `/history/lightning-stats` (`?days=1..365`, default 30), reading from MongoDB collections `network_metrics`, `graph_info`, `lightning_stats`. `/history/velocity` derives velocity per snapshot by joining `lightning_stats` capacity with mempool's hourly historical prices (`services/velocity.py`), holding the latest hardcoded monthly-volume estimate constant — nothing extra is persisted. All history endpoints return 503 when the database is not configured. The Velocity and Network Metrics cards each have a trend view (Gauge/Current ↔ Trend toggle) built on these endpoints, sharing `TrendChart.tsx`; the toggle hides itself when history 503s.
- **TLS cert handling** (`services/lnd.py`): `TLS_CERT_B64` (base64 cert, for env-var-only hosts) takes priority; otherwise `LND_TLS_CERT_PATH` (default `tls.cert`) is used. `LND_URL` and `LND_READONLY_MACAROON_HEX` are stripped of whitespace on load.

### Environment variables

Backend `.env` (see `.env.example`):

- `LND_URL` — LND REST base URL, e.g. `https://your-node:8080` (required)
- `LND_READONLY_MACAROON_HEX` — hex-encoded readonly macaroon (required)
- `LND_TLS_CERT_PATH` — cert file path for local dev (default `tls.cert`)
- `TLS_CERT_B64` — base64 cert; overrides the path (production)
- `CORS_ORIGINS` — comma-separated origins (default `http://localhost:5173`); only GET is allowed
- `MONGODB_URI` — optional; without it, persistence and `/history/*` are disabled and the app still runs

Frontend `frontend/.env`: `VITE_API_URL` (defaults to `http://localhost:8000`).

## Build and Run Commands

Backend (from repo root):

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in LND_URL, macaroon, cert
uvicorn main:app --reload        # serves on http://localhost:8000
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev        # vite dev server on http://localhost:5173
npm run build      # tsc -b && vite build → dist/
npm run lint       # eslint .
npm run preview    # serve the production build locally
npm start          # serve dist -p $PORT (used by Railway)
```

API docs are auto-generated at `http://localhost:8000/docs` when the backend runs.

## Testing

There is **no pytest/Vitest suite and no CI pipeline**. Verification is manual, with one scripted exception:

- `python scripts/check_report_card.py` — 43 assertions over the report card's pure logic (short channel ID decode, `BlockClock` interpolation, median/MAD, percentiles, every verdict branch, the language guard). No network, no database; exits non-zero on failure. Run it after touching `services/report_card.py` or `services/channel_flow.py`. Several checks are regressions for bugs that rendered perfectly while being wrong — a verdict that narrated the wrong metric, a "last 0 days" clause, and backfilled days polluting the baseline.
- Backend: hit the endpoint (e.g. `curl http://localhost:8000/health`) or use `/docs`; compare against the upstream API response.
- Frontend: `npm run build` (type-checks via `tsc -b`) and `npm run lint`.

If you add more tests, choose pytest for the backend and keep them out of the import path used by uvicorn, as `scripts/` already is.

## Code Style Guidelines

- **Backend:** plain modern Python, type hints throughout, `async`/`await` for all I/O (httpx, AsyncMongoClient). Models are Pydantic v2 `BaseModel`s and are the single source of truth for API shapes. Note the mixed field naming in models: LND/Mempool-derived fields keep their upstream names (e.g. `publicKey`, `firstSeen`), computed fields are snake_case.
- **Frontend:** strict TypeScript (`tsc -b` must pass), functional components with hooks, `type` imports (`import type { ... }`). Types in `src/types.ts` mirror `models.py` one-to-one — update both together. Styling is plain CSS in `App.css`/`index.css` with CSS variables (e.g. `--lightning`, `--amber`) and class-name conventions like `card`, `nm-feature`; there is no CSS framework or component library.
- Components fetch their own data in `useEffect` keyed on the `refreshKey` prop, and render a `Skeleton` placeholder from `components/Skeleton.tsx` while data is null.
- `react-simple-maps` is aliased to the `@vnedyalk0v/react19-simple-maps` fork for React 19 compatibility (see the `react-simple-maps.d.ts` declaration) — do not "fix" the package name.
- The repo contains a `notes.md` (gitignored) with the maintainer's workflow for adding features — backend: check API response → model → service → router → test; frontend: type → fetch function → component → register in `App.tsx`. Follow this order.

## Deployment

Production is **two separate Railway services**, both watching `main`:

- **Backend** (service `lightning-pulse`) — Python host running `uvicorn main:app --host 0.0.0.0 --port $PORT`. There is no committed backend deploy config; the start command and all env vars live in the Railway dashboard. Use `TLS_CERT_B64` rather than a cert file.
- **Frontend** — served at `pulse.velascommerce.com`. `frontend/railway.json` builds with `npm run build` and starts with `npm start` (`serve dist -p $PORT`).

**A push to `origin/main` deploys both services.** Treat it as a production deploy, not just source control.

Deploy ordering is not controllable via push, and the frontend always wins the race (a ~3 s Vite build versus pip install → uvicorn → a full LND graph fetch with a 120 s timeout). This means a brief window of new-frontend-against-old-backend: a missing `/history/*` endpoint 404s, the fetcher throws, and the affected trend toggle hides itself — degraded, not broken. To eliminate the window, pause the frontend service, push, wait for the backend to come up, then resume it.

Expect `/node/network-metrics` to return 503 for up to 120 s after every backend deploy while the first `refresh_metrics()` runs; `/health` reports `metrics_ready: false` until it finishes. The Network Metrics card renders an unavailable note during this window by design.

Env vars exist only in the Railway dashboards — nothing in the repo records the production values:

- Backend: `MONGODB_URI` is the easiest to lose. Without it `/history/*` returns 503 and **every** trend toggle silently disappears. Also confirm `CORS_ORIGINS` names the production frontend origin rather than the `http://localhost:5173` default.
- Frontend: `VITE_API_URL` is baked in at build time, so it must be set *before* Railway runs the build. Changing the backend URL requires a rebuild, not a restart.

There is no CI. `npm run build` (which runs `tsc -b`) is the only type gate that exists — run it locally before merging to `main`.

## Security Considerations

- **Never commit secrets.** `.env` and `tls.cert` are gitignored; only `.env.example` files are in the repo. Use a *readonly* macaroon — the app never needs write access to LND.
- The API is read-only by design: CORS allows only GET, there are no mutation endpoints, and no user input is written anywhere.
- When changing CORS or auth-related code, preserve the allowlist approach (`CORS_ORIGINS`) rather than widening to `*`.
- MongoDB is optional; keep it that way — the app must start and serve everything except `/history/*` without a database.
