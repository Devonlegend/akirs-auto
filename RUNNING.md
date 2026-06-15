# Running akirs

This document explains how to start the whole stack for local development and
for a live demo. Everything is launched with **`uv run`** — no manual
virtualenv activation, no `PYTHONPATH=...` prefixes.

The system has **four** pieces. Start them in this order:

1. **Redis** — the message broker + result store for the job queue.
2. **API server** (FastAPI/uvicorn) — serves the UI and the REST API.
3. **Celery worker** — actually runs scrape + recon jobs (browsers launch here).
4. **The UI** — open it in a browser; it is served by the API.

---

## 0. One-time setup

Install dependencies and the Playwright browser:

```bash
uv sync
```

```bash
uv run playwright install chromium
```

Create your local config (optional — sensible defaults work with no keys):

```bash
cp .env.example .env
```

Edit `.env` if you want. The two settings that matter for a demo are described
in [Demo mode](#demo-mode-visible-browsers) below.

---

## 1. Start Redis

The broker. If you have Redis installed as a system service:

```bash
sudo systemctl start redis-server
```

Check it is reachable:

```bash
redis-cli ping
```

You should see `PONG`. (If you run Redis another way — Docker, Homebrew — any
running Redis on `redis://localhost:6379/0` is fine.)

---

## 2. Start the API server

In its own terminal:

```bash
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- Serves the UI at <http://127.0.0.1:8000/ui/>
- Serves the REST API under the same origin (e.g. `/jobs`, `/scraped/...`)
- `--reload` restarts the server automatically when you edit backend code.
  Leave `--reload` off if you don't want that.

Check it is up:

```bash
curl http://127.0.0.1:8000/health
```

You should see `{"status":"ok"}`.

---

## 3. Start the Celery worker

In **another** terminal. This is the process that runs scrape and recon jobs;
the browsers open from here.

```bash
uv run celery -A src.tasks.celery_app:celery_app worker --loglevel=info --queues=scrape,recon,akirs --concurrency=1
```

What the flags mean:

- `-A src.tasks.celery_app:celery_app` — the Celery application to run.
- `--queues=scrape,recon,akirs` — consume all three queues. Phase-1 scrape jobs
  go to `scrape`, Phase-2 recon to `recon`; `akirs` is the default fallback.
- `--concurrency=1` — run one job at a time. Each job drives a real browser via
  Playwright, so one-at-a-time keeps the demo predictable. Raise it if you want
  parallelism.

When ready you'll see `celery@<host> ready.` and the three queues listed.

> Without a running worker, jobs you start from the UI are accepted and sit in
> the queue, but nothing executes. The worker is what makes them run.

---

## 4. Open the UI

Go to <http://127.0.0.1:8000/ui/> and sign in.

Local demo users (seeded automatically):

- `user1` / `user1`
- `user2` / `user2`

From **Scraper → Start** you can queue a scrape. Facebook login is optional —
see [the scraper notes](#scraper-facebook-login-is-optional).

---

## Demo mode (visible browsers)

By default the scraper and recon run **headless** (no visible window) so the
system works on a server. For a live demo where you want to *watch* the
browsers pop up, set both of these in `.env`:

```bash
FB_ADS_HEADLESS=false
RECON_BROWSER_HEADLESS=false
```

Then **restart the Celery worker** (step 3) so it picks up the change. Browsers
now open visibly for both the initial scrape and the recon pipeline.

For a deployed/headless server, set both back to `true` (or remove the lines).

---

## Scraper: Facebook login is optional

Scraping runs **anonymously** against the public Facebook Ads Library — no
login required. The old flow that opened a server-side login window has been
removed (it cannot work on a headless server).

If you *do* want to scrape while logged in, the Scraper page has an optional
**Facebook login** section (email + password). Those credentials are:

- used **once**, for that single job, to attempt a login at scrape time;
- **never stored** — they are stripped before the job is saved and never
  returned by the API;
- non-fatal — if the login fails (2FA, checkpoint, wrong password) the scrape
  simply continues anonymously.

---

## Stopping everything

- API server / worker: `Ctrl-C` in their terminals.
- Redis (if started as a service): `sudo systemctl stop redis-server`.

---

## Quick troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Jobs stay "queued" forever | No worker running | Start the worker (step 3) |
| `curl /health` fails | API not running | Start the API (step 2) |
| Worker logs `Connection refused` to Redis | Redis not running | Start Redis (step 1) |
| No browser window appears on a job | Headless mode on | Set the two `*_HEADLESS=false` flags, restart worker |
| Many old jobs fire at once when worker starts | Backlog queued while no worker ran | Clear the queue: `redis-cli flushall`, then restart the worker |

> Tip: a backlog can build up if you queue jobs with no worker running. Starting
> the worker then runs **all** of them — each opening a real browser against
> Facebook. Before a demo, if in doubt, run `redis-cli flushall` and start fresh.
