# Quick Start Guide

## Installation

1. **Install dependencies:**
```bash
pip install playwright
playwright install chromium
```

## Running the Scraper

### Basic Usage
```bash
python main.py
```

This will:
1. Launch Firefox in non-headless mode
2. Navigate to Facebook Ads Library
3. Filter by Nigeria
4. Search for "Learn"
5. Scrape 5 ads and extract social links
6. Export results to `output/ads_social_links.csv`

### Custom Configuration

Edit `main.py` to customize settings:

```python
config = AppConfig()
config.facebook_ads.headless = False  # Show browser
config.facebook_ads.countries = ["Nigeria", "Ghana"]
config.facebook_ads.keywords = ["Education", "Health"]
config.output_csv_path = "output/my_results.csv"

orchestrator = AdScraperOrchestrator(config)
orchestrator.run(ad_count=10)  # Scrape 10 ads
```

## Using Example Configurations

```bash
python examples_config.py
```

Or in your code:
```python
from examples_config import get_multi_country_config
from main import AdScraperOrchestrator

config = get_multi_country_config()
orchestrator = AdScraperOrchestrator(config)
orchestrator.run(ad_count=20)
```

## How It Works

### Architecture Flow

```
main.py (Entry Point)
    ↓
AdScraperOrchestrator (Orchestrator)
    ├─→ FacebookAdsLibraryPage (Page Object)
    │    └─→ Playwright interactions
    ├─→ AdScraperService (Scraper)
    │    ├─→ Uses FacebookAdsLibraryPage
    │    └─→ Produces AdDetails models
    └─→ CSVExportService (Exporter)
         └─→ Writes to CSV
```

### Data Flow

```
1. Navigate to Facebook Ads Library
2. Apply filters (country, keywords)
3. For each ad:
   a. Click "See ad details"
   b. Extract advertiser info
   c. Extract social links from dialog
   d. Convert to AdDetails model
4. Export all ads to CSV
```

### Social Link Detection

The `_detect_platform()` method identifies social media links by checking URLs against keywords:

- **Facebook**: facebook.com, fb.me
- **Instagram**: instagram.com, instagr.am
- **Twitter**: twitter.com, x.com, t.co
- **TikTok**: tiktok.com, vm.tiktok
- **YouTube**: youtube.com, youtu.be
- **LinkedIn**: linkedin.com
- **WhatsApp**: whatsapp.com, wa.me
- **Telegram**: telegram.me, t.me
- **Website**: http://, https://

## Output Format

CSV file with the following columns:

```csv
ad_id,advertiser_name,advertiser_url,social_platform,social_url,scraped_at
ad_0,ImagePlus Eye Clinic,https://facebook.com/...,instagram,https://instagram.com/imageplusclinic,2024-05-13T10:30:00
ad_0,ImagePlus Eye Clinic,https://facebook.com/...,website,https://imageplusclinic.com,2024-05-13T10:30:00
```

## Extending the Framework

### Add a New Export Format (e.g., JSON)

1. Create `services/json_export.py`:
```python
import json
from typing import List
from models import AdDetails

class JSONExportService:
    def __init__(self, output_path: str = "output/ads_social_links.json"):
        self.output_path = output_path
    
    def export_ads(self, ads: List[AdDetails]) -> None:
        data = [ad.to_dict() for ad in ads]
        with open(self.output_path, "w") as f:
            json.dump(data, f, indent=2)
```

2. Update `main.py` to use it:
```python
from services.json_export import JSONExportService

# In AdScraperOrchestrator
json_service = JSONExportService()
json_service.export_ads(ads)
```

### Add a New Filter

1. Add method to `FacebookAdsLibraryPage`:
```python
def filter_by_date_range(self, start_date: str, end_date: str) -> None:
    # Implement date filter logic
    pass
```

2. Use in `AdScraperService.setup()`:
```python
self.facebook_ads_page.filter_by_date_range("2024-01-01", "2024-12-31")
```

### Add Database Storage

1. Create `services/database_export.py`
2. Implement database schema and insert logic
3. Call from orchestrator

## Troubleshooting

### No ads found
- Check internet connection
- Verify Facebook Ads Library is accessible
- Try with different keywords or countries

### Social links not detected
- Links might be in different format
- Add more platform keywords to `_detect_platform()` method
- Enable browser view to debug dialog content

### Slow performance
- Use headless mode: `config.facebook_ads.headless = True`
- Reduce `ad_count`
- Add timeouts: `config.facebook_ads.timeout = 60000`

## Next Steps

- [ ] Add database persistence (SQLite/PostgreSQL)
- [ ] Implement pagination to scrape all ads
- [ ] Add scheduling (run periodically)
- [ ] Create web dashboard for results
- [ ] Add email notifications
- [ ] Implement proxy rotation
- [ ] Add CAPTCHA handling
- [ ] Create API endpoint for external access
