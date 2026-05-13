"""Example configuration for different use cases."""

from config import AppConfig


# Example 1: Basic setup for Nigeria
def get_basic_config():
    config = AppConfig()
    config.facebook_ads.headless = False
    config.facebook_ads.countries = ["Nigeria"]
    config.facebook_ads.keywords = ["Learn"]
    return config


# Example 2: Multiple countries
def get_multi_country_config():
    config = AppConfig()
    config.facebook_ads.headless = False
    config.facebook_ads.countries = ["Nigeria", "Ghana", "Kenya"]
    config.facebook_ads.keywords = ["Education", "Technology", "Health"]
    return config


# Example 3: Headless mode for production
def get_headless_config():
    config = AppConfig()
    config.facebook_ads.headless = True
    config.facebook_ads.countries = ["Nigeria"]
    config.facebook_ads.keywords = ["Solution"]
    config.output_csv_path = "output/ads_results_headless.csv"
    return config


if __name__ == "__main__":
    from main import AdScraperOrchestrator

    # Use basic config
    config = get_basic_config()
    orchestrator = AdScraperOrchestrator(config)
    orchestrator.run(ad_count=5)
