# 🗺️ Project Navigation Guide

## 📍 Key Files Quick Reference

### 🎯 Entry Point
- **`main.py`** - Run with `python main.py`
  - Contains `AdScraperOrchestrator` class
  - Coordinates entire workflow
  - Default configuration: Nigeria, "Learn" keyword, 5 ads

### ⚙️ Configuration
- **`config.py`** - Centralized settings
  - `FacebookAdsConfig` - Facebook-specific settings
  - `AppConfig` - Master configuration
  
- **`examples_config.py`** - Pre-built configurations
  - `get_basic_config()` - Basic setup
  - `get_multi_country_config()` - Multiple countries
  - `get_headless_config()` - Production headless mode

### 🧠 Models
- **`models/__init__.py`** - Data structures
  - `SocialLink` - Individual social media link
  - `AdDetails` - Complete ad information

### 🖥️ Page Objects
- **`pages/__init__.py`** - Package exports
- **`pages/facebook_ads_page.py`** - UI interactions
  - `FacebookAdsLibraryPage` class
  - Methods: `navigate()`, `select_country()`, `search_keyword()`, `extract_social_links_from_dialog()`, etc.

### 🔧 Services
- **`services/__init__.py`** - Package exports
- **`services/ad_scraper.py`** - High-level scraping
  - `AdScraperService` class
  - Methods: `setup()`, `scrape_ad_details()`, `scrape_multiple_ads()`
  
- **`services/csv_export.py`** - Data export
  - `CSVExportService` class
  - Methods: `export_ads()`, `append_ads()`

### 📚 Documentation
- **`README.md`** - Full documentation
- **`QUICKSTART.md`** - Usage examples
- **`ARCHITECTURE.md`** - Design patterns
- **`IMPLEMENTATION_SUMMARY.md`** - What was built

---

## 🔄 Component Interaction Flow

```
┌─────────────────────────────────────────────────────────┐
│                     main.py                             │
│               AdScraperOrchestrator                      │
│                                                         │
│  • Browser lifecycle management                        │
│  • Workflow coordination                               │
│  • Error handling                                      │
└──────────────┬──────────────┬──────────────────────────┘
               │              │
        ┌──────▼──────┐   ┌───▼──────────────┐
        │  services/  │   │  config.py       │
        │ad_scraper   │   │                  │
        │AdScraperSvc │   │ AppConfig()      │
        │             │   │ FacebookAdsConfig│
        │ • setup()   │   └──────────────────┘
        │ • scrape()  │
        └──────┬──────┘
               │
        ┌──────▼──────────────────┐
        │ pages/facebook_ads_page │
        │ FacebookAdsLibraryPage  │
        │                         │
        │ • navigate()            │
        │ • select_country()      │
        │ • search_keyword()      │
        │ • extract_social_links()│
        │ • get_advertiser_info() │
        └──────┬──────────────────┘
               │
        ┌──────▼──────────────┐
        │ Playwright Page     │
        │ (Browser)           │
        └─────────────────────┘

        │
        └──► models/AdDetails
             models/SocialLink
             │
             └──► services/csv_export
                  CSVExportService
                  │
                  └──► output/*.csv
```

---

## 🎯 How to Use (Quick Examples)

### Example 1: Default Run
```bash
python main.py
```
Output: `output/ads_social_links.csv`

### Example 2: Custom Countries & Keywords
```python
# In main.py or new script
from main import AdScraperOrchestrator
from config import AppConfig

config = AppConfig()
config.facebook_ads.countries = ["Nigeria", "Ghana"]
config.facebook_ads.keywords = ["Health", "Education"]

orchestrator = AdScraperOrchestrator(config)
orchestrator.run(ad_count=10)
```

### Example 3: Using Pre-built Config
```python
from examples_config import get_multi_country_config
from main import AdScraperOrchestrator

config = get_multi_country_config()
orchestrator = AdScraperOrchestrator(config)
orchestrator.run(ad_count=20)
```

### Example 4: Headless Mode
```python
from config import AppConfig
from main import AdScraperOrchestrator

config = AppConfig()
config.facebook_ads.headless = True

orchestrator = AdScraperOrchestrator(config)
orchestrator.run(ad_count=5)
```

---

## 📊 CSV Output Structure

```csv
ad_id,advertiser_name,advertiser_url,social_platform,social_url,scraped_at
ad_0,Company A,https://facebook.com/companya,instagram,https://instagram.com/companya,2024-05-13T10:30:00
ad_0,Company A,https://facebook.com/companya,facebook,https://facebook.com/companya,2024-05-13T10:30:00
ad_0,Company A,https://facebook.com/companya,website,https://companya.com,2024-05-13T10:30:00
ad_1,Company B,https://facebook.com/companyb,tiktok,https://tiktok.com/@companyb,2024-05-13T10:31:00
```

---

## 🔍 Data Flow Deep Dive

### 1️⃣ Configuration Phase
```
AppConfig created
  ├─ FacebookAdsConfig.countries = ["Nigeria"]
  ├─ FacebookAdsConfig.keywords = ["Learn"]
  └─ FacebookAdsConfig.headless = False
```

### 2️⃣ Setup Phase
```
AdScraperService.setup()
  ├─ FacebookAdsLibraryPage.navigate()
  │  └─ Go to Ads Library URL
  ├─ For each country:
  │  └─ FacebookAdsLibraryPage.select_country()
  └─ For each keyword:
     └─ FacebookAdsLibraryPage.search_keyword()
```

### 3️⃣ Scraping Phase
```
AdScraperService.scrape_multiple_ads(5)
  └─ For each ad (i = 0 to 4):
     ├─ FacebookAdsLibraryPage.click_see_ad_details(i)
     ├─ advertiser_info = FacebookAdsLibraryPage.get_advertiser_info()
     ├─ social_links_data = FacebookAdsLibraryPage.extract_social_links_from_dialog()
     ├─ Convert to SocialLink objects
     ├─ Create AdDetails(
     │     ad_id="ad_0",
     │     advertiser_name="...",
     │     advertiser_url="...",
     │     social_links=[...]
     │  )
     ├─ Append to scraped_ads list
     └─ FacebookAdsLibraryPage.close_ad_details_dialog()
```

### 4️⃣ Export Phase
```
CSVExportService.export_ads(ads)
  ├─ For each ad:
  │  └─ ad.to_csv_row()  # Returns multiple rows per ad
  ├─ Collect all rows
  └─ Write to CSV with headers
```

---

## 🛠️ To Extend the Framework

### Add New Export Format
1. Create `services/json_export.py`
2. Implement `JSONExportService` class
3. Import in `services/__init__.py`
4. Call from `main.py` orchestrator

### Add New Data Source
1. Create `pages/google_ads_page.py`
2. Implement `GoogleAdsPage` class
3. Create `services/google_ads_scraper.py`
4. Implement `GoogleAdScraperService` class
5. Call from orchestrator

### Add Database Export
1. Create `services/database_export.py`
2. Implement `DatabaseExportService` class
3. Call from orchestrator instead of CSV

---

## 📖 Documentation Map

| Document | Purpose | Read When |
|----------|---------|-----------|
| README.md | Overview & setup | Getting started |
| QUICKSTART.md | Usage examples | Want to run code |
| ARCHITECTURE.md | Design patterns | Understanding structure |
| IMPLEMENTATION_SUMMARY.md | What was built | Understanding changes |
| This file | Navigation guide | Lost or confused |

---

## 🚀 Common Tasks

| Task | How |
|------|-----|
| **Change countries** | Edit `config.py` or pass to `AppConfig()` |
| **Change keywords** | Edit `config.py` or pass to `AppConfig()` |
| **Run headless** | Set `config.facebook_ads.headless = True` |
| **Scrape more ads** | Pass `ad_count=N` to `orchestrator.run()` |
| **Change CSV path** | Set `config.output_csv_path = "path/to/file.csv"` |
| **Append to CSV** | Use `CSVExportService.append_ads()` |
| **Extract specific platform** | Add filter after CSV export |
| **Add new platform detection** | Update `FacebookAdsLibraryPage._detect_platform()` |

---

**Need help?** Refer to documentation files or check example configurations in `examples_config.py`
