from src.config.settings import get_settings
from src.recon.base import FallbackReconCoordinator
from src.recon.data_warehouses import DataWarehouseRecon
from src.recon.enrichment_apis import EnrichmentAPIRecon
from src.recon.google_maps import GoogleMapsRecon
from src.recon.nominatim import NominatimRecon
from src.recon.places import PlacesEnrichmentRecon
from src.recon.registries import RegistryRecon
from src.recon.search_engine import SearchEngineRecon
from src.recon.social_profiles import SocialProfileRecon
from src.recon.website import WebsiteRecon
from src.recon.cac_registry import CACRegistryRecon
from src.recon.linkedin_ddg import LinkedInDDGRecon


def build_default_coordinator() -> FallbackReconCoordinator:
    settings = get_settings()

    # Tier 1: Free and fast direct website scraping
    tier_1 = [
        WebsiteRecon(concurrency=settings.recon_search_concurrency),
    ]

    # Tier 2: Free but slower — search engines, social scraping, OSM geocoding, Google Maps, CAC, LinkedIn DDG.
    tier_2 = [
        SearchEngineRecon(concurrency=settings.recon_search_concurrency),
        SocialProfileRecon(concurrency=settings.recon_social_concurrency),
        NominatimRecon(concurrency=1),
        GoogleMapsRecon(concurrency=settings.recon_search_concurrency),
        CACRegistryRecon(concurrency=1), # Low concurrency to avoid blocking on CAC
        LinkedInDDGRecon(concurrency=settings.recon_search_concurrency),
    ]

    # Tier 3: Paid/API endpoints and registries (auto-disabled when keys missing).
    tier_3 = [
        PlacesEnrichmentRecon(concurrency=settings.recon_places_concurrency),
        RegistryRecon(concurrency=settings.recon_registry_concurrency),
        DataWarehouseRecon(concurrency=settings.recon_warehouse_concurrency),
        EnrichmentAPIRecon(concurrency=settings.recon_enrichment_concurrency),
    ]

    tiers = [tier_1, tier_2, tier_3]
    return FallbackReconCoordinator(tiers)


