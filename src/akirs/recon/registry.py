from akirs.config.settings import get_settings
from akirs.recon.base import FallbackReconCoordinator
from akirs.recon.data_warehouses import DataWarehouseRecon
from akirs.recon.enrichment_apis import EnrichmentAPIRecon
from akirs.recon.registries import RegistryRecon
from akirs.recon.search_engine import SearchEngineRecon
from akirs.recon.social_profiles import SocialProfileRecon
from akirs.recon.website import WebsiteRecon


def build_default_coordinator() -> FallbackReconCoordinator:
    settings = get_settings()
    
    # Tier 1: Free and fast direct website scraping
    tier_1 = [
        WebsiteRecon(concurrency=settings.recon_search_concurrency), # Using search concurrency setting
    ]
    
    # Tier 2: Free but slower, higher risk of bot detection (Search + Social Profiles)
    tier_2 = [
        SearchEngineRecon(concurrency=settings.recon_search_concurrency),
        SocialProfileRecon(concurrency=settings.recon_social_concurrency),
    ]
    
    # Tier 3: Paid/API endpoints and registries
    tier_3 = [
        RegistryRecon(concurrency=settings.recon_registry_concurrency),
        DataWarehouseRecon(concurrency=settings.recon_warehouse_concurrency),
        EnrichmentAPIRecon(concurrency=settings.recon_enrichment_concurrency),
    ]
    
    tiers = [tier_1, tier_2, tier_3]
    return FallbackReconCoordinator(tiers)
