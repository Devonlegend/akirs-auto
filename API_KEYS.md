# API Keys

The pipeline is designed so that **free sources run first** in every tier and
**paid sources only run if you've provided their API keys**. Every paid
source auto-disables when its key is missing — the pipeline works end-to-end
without any keys.

Add the keys you want to use to `.env` (see `.env.example`).

---

## TL;DR — minimum viable setup

| Goal | Keys needed |
|---|---|
| Just try it (free only) | **none** |
| Recommended free setup | none — `website` + `search` + `social` + `nominatim` cover most of the value |
| Add verified addresses + phones | `TOMTOM_API_KEY` (free tier: 2,500 req/day) |
| Add corporate registry lookups | `OPENCORPORATES_API_KEY` (free tier: 500 calls/mo) |
| Add bulk email enrichment | `HUNTER_API_KEY` (25/mo free) and/or `APOLLO_API_KEY` |

---

## Free sources (no key required)

These always run.

### `website` — Tier 1

Scrapes the advertiser's own landing page for emails, phones, addresses.

- **Cost:** free
- **Limits:** none (your own bandwidth)
- **Setup:** none

### `search` — Tier 2

DuckDuckGo HTML scraping. Pulls emails / phones / mentions from search
snippets.

- **Cost:** free
- **Limits:** DuckDuckGo rate-limits aggressive use. Tunable via
  `RECON_SEARCH_DELAY_SECONDS` (default 2.0s between queries).
- **Setup:** none

### `social` — Tier 2

Playwright-driven scraping of public social profiles for bio + contact info.

- **Cost:** free
- **Limits:** rate-limited by the platforms themselves
- **Setup:** Playwright Chromium is already installed via `playwright install chromium`

### `nominatim` — Tier 2

OpenStreetMap Nominatim geocoder. Looks up the advertiser by name and
returns a formatted address, biased to Akwa Ibom.

- **Cost:** free
- **Limits:** [OSM policy](https://operations.osmfoundation.org/policies/nominatim/)
  caps at **1 request/second**. The source enforces this internally — do not
  raise its concurrency.
- **Setup:** none. A descriptive `User-Agent` is sent automatically (required
  by policy).

---

## Paid sources (key required — auto-disabled if missing)

### `places` (TomTom) — Tier 3

Verified Place-of-Interest lookup. Adds physical address, phone number, and
the POI's official name.

- **Free tier:** [2,500 requests/day](https://developer.tomtom.com/store/maps-api)
- **Sign up:** [developer.tomtom.com](https://developer.tomtom.com/) → register
  → My Dashboard → Create new key → enable **Search API**
- **Env var:** `TOMTOM_API_KEY`
- **Notes:** geo-biased to Uyo (5.0382°N, 7.9128°E) within a 150 km radius and
  filtered to Nigeria (`countrySet=NG`).

### `registry` (OpenCorporates) — Tier 3

Corporate registry records — useful for verifying legal names.

- **Free tier:** [500 calls/month](https://api.opencorporates.com/)
- **Sign up:** [opencorporates.com](https://opencorporates.com/api_accounts/new)
- **Env var:** `OPENCORPORATES_API_KEY`

### `enrichment` (Hunter.io + Apollo.io) — Tier 3

Bulk email / people enrichment. Two providers behind one source — the source
queries whichever keys are set.

#### Hunter.io
- **Free tier:** [25 searches/month](https://hunter.io/pricing) on the free plan
- **Sign up:** [hunter.io](https://hunter.io/users/sign_up) → API tab
- **Env var:** `HUNTER_API_KEY`
- **Finds:** emails, organization names, job titles

#### Apollo.io
- **Free tier:** limited free credits, generous trial
- **Sign up:** [apollo.io](https://app.apollo.io/) → Settings → Integrations → API
- **Env var:** `APOLLO_API_KEY`
- **Finds:** people emails, phone numbers, titles, organization names

### `warehouse` (DataWarehouseRecon) — Tier 3

Pre-built B2B data warehouse adapter. Currently a no-op without provider
credentials — wire your own warehouse key here when you add one.

---

## How tier stop-conditions work

The recon coordinator stops descending tiers as soon as a tier produces
either an **email** OR **phone** finding. That means:

- A free `website` hit with both → Tier 3 is skipped, saving paid quota.
- `nominatim` produces `address` only → does **not** stop the cascade →
  TomTom still runs in Tier 3 to layer on phone + verified name.

This is intentional: free sources get first crack at expensive-to-find data
(emails, phones), and paid sources are reserved for either filling those
gaps or adding higher-confidence verification.

To change stop conditions, pass `stop_conditions={"email", "phone", "address"}`
when constructing the coordinator in `akirs/recon/registry.py`.

---

## Concurrency tuning

Each source has its own concurrency knob in `akirs/config/settings.py`:

```
RECON_SEARCH_CONCURRENCY        # default 2 — DDG + Website
RECON_SOCIAL_CONCURRENCY        # default 1 — social profiles
RECON_PLACES_CONCURRENCY        # default 2 — TomTom
RECON_ENRICHMENT_CONCURRENCY    # default 2 — Hunter + Apollo
RECON_REGISTRY_CONCURRENCY      # default 1 — OpenCorporates
RECON_WAREHOUSE_CONCURRENCY     # default 1
RECON_SEARCH_DELAY_SECONDS      # default 2.0 — between DDG queries
```

`nominatim` is **hard-coded to concurrency=1** to comply with OSM policy.
Do not raise it.
