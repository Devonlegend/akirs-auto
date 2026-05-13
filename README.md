# Ad Scraper - Modular Automation Project

A class-based, modular Playwright automation framework for scraping Facebook Ads Library and extracting social media links.

## Project Structure

```
akirs-auto/
├── main.py                 # Entry point / Orchestrator
├── config.py              # Configuration settings
├── models/
│   └── __init__.py        # Data models (AdDetails, SocialLink)
├── pages/
│   └── __init__.py        # Page Objects (FacebookAdsLibraryPage)
├── services/
│   ├── __init__.py        # CSV export service
│   └── ad_scraper.py      # Ad scraping service
├── output/                # Output directory (created at runtime)
│   └── ads_social_links.csv
├── pyproject.toml         # Project metadata
└── README.md
```

## Architecture

### 1. **Models** (`models/__init__.py`)
Data structures for type-safe data handling:
- `SocialLink`: Represents a single social media link
- `AdDetails`: Represents complete ad information with associated social links

### 2. **Config** (`config.py`)
Centralized configuration management:
- `FacebookAdsConfig`: Facebook-specific settings (countries, keywords, browser options)
- `AppConfig`: Main application configuration

### 3. **Page Objects** (`pages/__init__.py`)
- `FacebookAdsLibraryPage`: Encapsulates all interactions with the Facebook Ads Library UI
  - Methods for country selection, keyword search, clicking buttons
  - Social link extraction and platform detection
  - Advertiser information extraction

### 4. **Services** (`services/`)
- `AdScraperService` (`ad_scraper.py`): High-level orchestration of scraping logic
  - Uses the page object to perform actions
  - Manages data collection pipeline
  - Converts raw data into models
  
- `CSVExportService` (`services/__init__.py`): Handles data persistence
  - Export ads to CSV with one row per social link
  - Append-mode for incremental scraping

### 5. **Orchestrator** (`main.py`)
- `AdScraperOrchestrator`: Ties all components together
  - Browser lifecycle management
  - Workflow coordination
  - Error handling

## Usage

### Basic Usage
```python
from main import AdScraperOrchestrator
from config import AppConfig

# Create config
config = AppConfig()
config.facebook_ads.countries = ["Nigeria"]
config.facebook_ads.keywords = ["Learn"]

# Run scraper
orchestrator = AdScraperOrchestrator(config)
orchestrator.run(ad_count=5)
```

### From Command Line
```bash
python main.py
```

## Output

Results are saved to `output/ads_social_links.csv` with the following columns:
- `ad_id`: Unique identifier for the ad
- `advertiser_name`: Name of the advertiser
- `advertiser_url`: Link to advertiser's profile
- `social_platform`: Type of social media (facebook, instagram, twitter, etc.)
- `social_url`: URL of the social media link
- `scraped_at`: Timestamp when the ad was scraped

### Example CSV Output
```csv
ad_id,advertiser_name,advertiser_url,social_platform,social_url,scraped_at
ad_0,ImagePlus Eye Clinic,https://facebook.com/...,instagram,https://instagram.com/imageplusclinic,2024-05-13T10:30:00
ad_0,ImagePlus Eye Clinic,https://facebook.com/...,website,https://imageplusclinic.com,2024-05-13T10:30:00
ad_1,Another Business,https://facebook.com/...,facebook,https://facebook.com/anotherbusiness,2024-05-13T10:31:00
```

## Extending the Framework

### Add a New Service
1. Create a new file in `services/` directory
2. Import in `services/__init__.py`
3. Use in `AdScraperService` or `AdScraperOrchestrator`

### Add New Page Interactions
1. Add methods to `FacebookAdsLibraryPage` class
2. Call from `AdScraperService.scrape_ad_details()` or new workflows

### Add New Data Models
1. Create new dataclass in `models/__init__.py`
2. Use in services for type-safe data handling

### Add Configuration Options
1. Add fields to `FacebookAdsConfig` or create new config class
2. Access from `AppConfig` in orchestrator

## Requirements
- Python 3.9+
- Playwright
- Python dataclasses (standard library)
- CSV (standard library)

## Installation
```bash
pip install playwright
playwright install chromium
```

## Next Steps / Bootstrap Ideas
- Add database export (JSON, SQLite)
- Implement pagination for scraping more ads
- Add advanced filtering options
- Create dashboard for results visualization
- Add rate limiting and retry logic
- Implement headless browser pooling for parallel scraping
