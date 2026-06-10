# AKIRS Scraper Dashboard

Static HTML, CSS, and JavaScript frontend for a backend business-lead scraper.

## Structure

- `index.html` - application shell, top header, and collapsible sidebar
- `css/styles.css` - responsive enterprise dashboard styling with light and dark mode
- `js/app.js` - hash routing, mock data, reusable render helpers, and UI interactions

## Pages

- `#/dashboard` - operational overview and activity feed
- `#/scraper` - scraper configuration, controls, live KPIs, and activity log
- `#/results` - card/table explorer for collected business leads
- `#/review` - review queue with bulk workflow controls
- `#/taxable` - verified business contacts ready for tax payment outreach
- `#/analytics` - KPI and chart-style analytics dashboard
- `#/settings` - scraper defaults and notification preferences

## Run Locally

Open `index.html` directly in a browser, or serve the folder with any static server:

```bash
python3 -m http.server 5173
```

Then visit `http://localhost:5173`.

## Backend Integration Notes

Mock data is centralized near the top of `js/app.js`:

- `profiles` mock business lead data
- `activityLog`

Replace those arrays with API calls when backend endpoints are ready. The UI already separates rendering helpers for cards, tables, activity logs, KPI cards, drawers, toasts, and filters so backend pagination, saved filters, and bulk actions can be wired in without changing the layout.
