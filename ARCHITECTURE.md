# Architecture & Design Patterns

## Overview

This project follows **Object-Oriented Design** principles and common **Testing-friendly patterns**:

- **Page Object Model (POM)**: UI interactions are encapsulated in page objects
- **Service Layer Pattern**: Business logic separated from UI interactions
- **Data Models**: Type-safe data structures (dataclasses)
- **Dependency Injection**: Services receive dependencies via constructor
- **Configuration Pattern**: Centralized configuration management

## Project Layers

### 1. **Models Layer** (`models/`)
**Responsibility**: Define data structures and contracts

```python
@dataclass
class SocialLink:
    """Immutable representation of a social media link"""
    platform: str
    url: str

@dataclass
class AdDetails:
    """Complete ad information with analytics"""
    ad_id: str
    advertiser_name: str
    advertiser_url: Optional[str]
    social_links: List[SocialLink]
    scraped_at: datetime
```

**Key Features**:
- Type hints for IDE support
- `to_dict()` for serialization
- `to_csv_row()` for export flexibility

### 2. **Configuration Layer** (`config.py`)
**Responsibility**: Manage application settings

```python
@dataclass
class FacebookAdsConfig:
    """Facebook-specific settings"""
    base_url: str
    headless: bool
    timeout: int
    countries: list
    keywords: list

@dataclass
class AppConfig:
    """Master configuration container"""
    facebook_ads: FacebookAdsConfig
    output_csv_path: str
```

**Benefits**:
- Single source of truth for settings
- Easy to create different configs per environment
- Type-safe configuration

### 3. **Page Object Layer** (`pages/`)
**Responsibility**: Encapsulate UI interactions

```python
class FacebookAdsLibraryPage:
    """Represents Facebook Ads Library interface"""
    
    def __init__(self, page: Page):
        self.page = page  # Playwright Page object
    
    def navigate(self) -> None:
        """Navigate to the library"""
    
    def select_country(self, country_name: str) -> None:
        """Apply country filter"""
    
    def extract_social_links_from_dialog(self) -> List[dict]:
        """Extract links from ad details modal"""
```

**Benefits**:
- Isolates test code from UI details
- Easy to maintain when selectors change
- Clear public API
- Reusable across multiple scrapers

### 4. **Service Layer** (`services/`)
**Responsibility**: Implement business logic

#### AdScraperService
```python
class AdScraperService:
    """Orchestrates ad scraping workflow"""
    
    def __init__(self, page: Page):
        self.facebook_ads_page = FacebookAdsLibraryPage(page)
        self.scraped_ads: List[AdDetails] = []
    
    def setup(self, countries: List[str]) -> None:
        """Initialize filters"""
    
    def scrape_ad_details(self, ad_index: int) -> Optional[AdDetails]:
        """Scrape single ad and convert to model"""
    
    def scrape_multiple_ads(self, count: int) -> List[AdDetails]:
        """Scrape multiple ads"""
```

#### CSVExportService
```python
class CSVExportService:
    """Handles data persistence"""
    
    def export_ads(self, ads: List[AdDetails]) -> None:
        """Write to new CSV"""
    
    def append_ads(self, ads: List[AdDetails]) -> None:
        """Append to existing CSV"""
```

**Benefits**:
- Single Responsibility Principle (SRP)
- Easy to test independently
- Reusable in different contexts
- Easy to add new export formats

### 5. **Orchestrator Layer** (`main.py`)
**Responsibility**: Coordinate all layers

```python
class AdScraperOrchestrator:
    """Main workflow controller"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.export_service = CSVExportService(config.output_csv_path)
    
    def run(self, ad_count: int) -> None:
        """Execute complete workflow"""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(...)
            page = browser.new_page()
            
            scraper = AdScraperService(page)
            scraper.setup(self.config.facebook_ads.countries)
            scraper.scrape_multiple_ads(ad_count)
            
            self.export_service.export_ads(scraper.get_scraped_ads())
```

**Benefits**:
- Clear workflow visibility
- Centralized error handling
- Resource management (browser lifecycle)

## Design Patterns Used

### 1. **Page Object Model (POM)**
```
UI Interactions (Playwright)
        ↓
FacebookAdsLibraryPage
        ↓
AdScraperService (Business Logic)
```

### 2. **Service Layer**
```
AdScraperService (High-level operations)
        ↓
FacebookAdsLibraryPage (Low-level UI)
        ↓
Playwright (Browser automation)
```

### 3. **Data Transfer Objects (DTOs)**
```python
# Raw data from page → Model
raw_link = {"platform": "instagram", "url": "..."}
social_link = SocialLink(**raw_link)  # Type-safe
```

### 4. **Factory Pattern** (implicit)
```python
# AdDetails acts as a factory for CSV rows
ad.to_csv_row()  # Returns multiple rows per ad
```

## Composition & Dependency Flow

```
AppConfig (Configuration)
    ↓
AdScraperOrchestrator (Orchestrator)
    ├→ AdScraperService
    │   ├→ FacebookAdsLibraryPage
    │   │   └→ Playwright Page
    │   └→ [produces] AdDetails[]
    │       └→ SocialLink[]
    └→ CSVExportService
        └→ [exports] AdDetails[]
```

## Scaling & Extensibility

### Add New Export Format

```
services/
├── __init__.py
├── csv_export.py
├── json_export.py  ← NEW
├── database_export.py  ← NEW
└── ad_scraper.py
```

### Add New Page Object

```
pages/
├── __init__.py
├── facebook_ads_page.py
├── google_ads_page.py  ← NEW
└── tiktok_ads_page.py  ← NEW
```

### Add New Scraper Service

```
services/
├── __init__.py
├── ad_scraper.py
├── influencer_scraper.py  ← NEW
└── csv_export.py
```

## Key Features of This Architecture

| Feature | Benefit |
|---------|---------|
| **Separation of Concerns** | Each class has single responsibility |
| **Type Safety** | Dataclasses + type hints catch errors early |
| **Testability** | Easy to mock dependencies and test in isolation |
| **Maintainability** | Clear structure, easy to understand |
| **Reusability** | Services can be used in multiple contexts |
| **Flexibility** | Easy to add new features without breaking existing code |
| **Scalability** | Can parallelize scrapers, add queues, caching, etc. |

## Testing Strategy (Future)

```python
# Unit test example
def test_social_link_detection():
    url = "https://instagram.com/myaccount"
    platform = FacebookAdsLibraryPage._detect_platform(url)
    assert platform == "instagram"

# Integration test example
def test_scrape_single_ad(mock_page):
    scraper = AdScraperService(mock_page)
    ad = scraper.scrape_ad_details(0)
    assert isinstance(ad, AdDetails)
    assert len(ad.social_links) > 0
```

## Comparison with Monolithic Approach

### ❌ Before (Monolithic)
```python
# main.py - 300+ lines of spaghetti code
def run(playwright):
    browser = ...
    page = ...
    page.goto(...)
    page.locator(...).click()
    # ... 200+ more lines of page interactions
```

### ✅ After (Modular)
```python
# main.py - Clean & focused
orchestrator = AdScraperOrchestrator(config)
orchestrator.run(ad_count=5)
```

**Benefits of modular approach**:
- ✅ Each component does one thing well
- ✅ Easy to test individual components
- ✅ Easy to modify without breaking everything
- ✅ Easy to reuse in different contexts
- ✅ Clear separation of concerns
- ✅ Scalable architecture
