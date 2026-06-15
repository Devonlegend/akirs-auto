# akirs

Find businesses advertising on Facebook in **Akwa Ibom / Uyo**, then enrich
each advertiser with emails, phone numbers, and physical addresses pulled
from free and paid sources.

Two-phase pipeline:

1. **Scrape** the Facebook Ads Library for keywords tied to Akwa Ibom
   (landmarks, dialect, commercial intent).
2. **Enrich** each advertiser through tiered recon — free sources first,
   paid sources only if you provide API keys.

Output: a single CSV with one row per advertiser × social link, including
recon-derived emails, phones, addresses, and legal name.

---

## Quick start

```bash
# 1. Install
uv sync
.venv/bin/playwright install chromium

# 2. (Optional) add API keys for paid sources — see API_KEYS.md
cp .env.example .env
# edit .env

## Running Independent Components via uv

You can run the project's individual components directly using `uv`:

### 1. The Scraper
Run a single-shot scrape + recon job:
```bash
uv run python main.py --recon --headless --target 5 --cap 4
```
Results land in `output/akirs_enriched_<timestamp>.csv`.

### 2. The Web Server
To launch the FastAPI backend server:
```bash
uv run uvicorn backend.main:app --reload
```

### 3. The Chatbot
To launch the interactive Chatbot CLI:
```bash
uv run python -m chatbot
```

---

## How recon works

Recon runs in three tiers. A tier stops the next one only when it finds an
**email** or **phone** (stop conditions); other findings (addresses, mentions,
company names) accumulate across all tiers.

| Tier | Source              | Cost | What it finds                          |
|------|---------------------|------|----------------------------------------|
| 1    | `website`           | free | emails, phones, addresses from the advertiser's own page |
| 2    | `search`            | free | mentions, emails, phones from DuckDuckGo snippets |
| 2    | `social`            | free | profile bios from Instagram, etc.      |
| 2    | `nominatim`         | free | addresses via OpenStreetMap            |
| 3    | `places` (TomTom)   | paid | verified address + phone + POI name    |
| 3    | `registry`          | paid | corporate registry records             |
| 3    | `warehouse`         | paid | data warehouse profiles                |
| 3    | `enrichment`        | paid | Hunter.io + Apollo.io emails / titles  |

Paid sources **auto-disable** when their keys are missing — the pipeline
works end-to-end with zero keys.

See [API_KEYS.md](./API_KEYS.md) for sign-up details and free-tier limits.

---

## CLI flags

```
--locations    Akwa Ibom locations (default: all 31 LGAs)
--categories   business categories (default: curated list)
--target N     ads to capture per keyword run (default: 5)
--cap N        max keyword runs per job (default: 4)
--headless     run browser headless
--recon        run Phase 2 recon inline after scraping
```

---

## CSV columns

```
ad_id, advertiser_name, advertiser_url,
social_platform, social_url,
recon_legal_name, recon_emails, recon_phones,
recon_addresses, recon_sources,
scraped_at
```

One row per advertiser × social link. Recon columns are duplicated across
rows for the same advertiser so each row carries full context.
