# AKIRS Scraper Dashboard

Static HTML, CSS, and JavaScript frontend for a backend business-lead scraper.

## Structure

- `index.html` - application shell, top header, and collapsible sidebar
- `css/styles.css` - responsive enterprise dashboard styling with light and dark mode
- `js/app.js` - hash routing, backend data loading, reusable render helpers, and UI interactions

## Pages

- `#/dashboard` - operational overview and activity feed
- `#/scraper` - scraper configuration, controls, live KPIs, and activity log
- `#/results` - card/table explorer for collected business leads
- `#/review` - review queue with bulk workflow controls
- `#/taxable` - verified business contacts ready for tax payment outreach
- `#/analytics` - KPI and chart-style analytics dashboard
- `#/settings` - scraper defaults and notification preferences

## Run Locally

Run the FastAPI backend from the project root so the UI can load records from `akirs.db`:

```bash
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Then visit `http://127.0.0.1:8000/ui/`.

## Backend Integration Notes

The frontend does not read the SQLite file directly. It uses backend endpoints for scraper records, taxable entities, and scrape job status:

- `/scraped/advertisers/`
- `/taxation/entities`
- `/jobs`
- `/jobs/{job_id}`
