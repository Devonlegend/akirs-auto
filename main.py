"""Main orchestrator for ad scraping automation."""

import logging
from playwright.sync_api import sync_playwright
from config import AppConfig
from services import CSVExportService
from services.ad_scraper import AdScraperService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AdScraperOrchestrator:
    """Orchestrates the ad scraping workflow."""

    def __init__(self, config: AppConfig = None):
        self.config = config or AppConfig()
        self.scraper = None
        self.export_service = CSVExportService(self.config.output_csv_path)

    def run(self, ad_count: int = 5) -> None:
        """Run the complete scraping workflow."""
        with sync_playwright() as playwright:
            # Launch browser
            browser = playwright.chromium.launch(
                headless=self.config.facebook_ads.headless
            )
            context = browser.new_context()
            page = context.new_page()

            try:
                # Initialize scraper
                self.scraper = AdScraperService(page)

                # Setup with filters
                logger.info("Setting up scraper with filters...")
                self.scraper.setup(
                    countries=self.config.facebook_ads.countries,
                    keywords=self.config.facebook_ads.keywords,
                )

                # Scrape ads
                logger.info(f"Starting to scrape {ad_count} ads...")
                self.scraper.scrape_multiple_ads(count=ad_count)

                # Export results
                logger.info("Exporting results to CSV...")
                ads = self.scraper.get_scraped_ads()
                self.export_service.export_ads(ads)

                logger.info("✓ Scraping completed successfully!")

            except Exception as e:
                logger.error(f"Error during scraping: {e}", exc_info=True)
            finally:
                context.close()
                browser.close()


def main():
    """Main entry point."""
    # Create config with custom settings if needed
    config = AppConfig()

    # Customize if needed
    config.facebook_ads.headless = False  # Set to True for headless mode
    config.facebook_ads.countries = ["Nigeria"]
    config.facebook_ads.keywords = ["Learn"]

    # Run orchestrator
    orchestrator = AdScraperOrchestrator(config)
    orchestrator.run(ad_count=5)  # Scrape 5 ads


if __name__ == "__main__":
    main()
