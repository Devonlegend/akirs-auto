from config.settings import get_settings
from recon.base import FallbackReconCoordinator
from recon.data_warehouses import DataWarehouseRecon
from recon.enrichment_apis import EnrichmentAPIRecon
from recon.nominatim import NominatimRecon
from recon.places import PlacesEnrichmentRecon
from recon.registries import RegistryRecon
from recon.search_engine import SearchEngineRecon
from recon.social_profiles import SocialProfileRecon
from recon.website import WebsiteRecon


def build_default_coordinator() -> FallbackReconCoordinator:
    settings = get_settings()

    # Tier 1: Free and fast direct website scraping
    tier_1 = [
        WebsiteRecon(concurrency=settings.recon_search_concurrency), # Using search concurrency setting
    ]

    # Tier 2: Free but slower — search engines, social scraping, OSM geocoding.
    # NominatimRecon is free and provides addresses; runs here so we always try
    # it before any paid Tier-3 calls. ``address`` is NOT in the coordinator's
    # stop conditions, so Tier 3 still runs to add phone + verified names.
    tier_2 = [
        SearchEngineRecon(concurrency=settings.recon_search_concurrency),
        SocialProfileRecon(concurrency=settings.recon_social_concurrency),
        NominatimRecon(concurrency=1),  # OSM policy: 1 req/sec hard cap
    ]

    # Tier 3: Paid/API endpoints and registries (auto-disabled when keys missing).
    # PlacesEnrichmentRecon (TomTom) layers on top of Nominatim with phone
    # numbers and verified POI names when a key is configured.
    tier_3 = [
        PlacesEnrichmentRecon(concurrency=settings.recon_places_concurrency),
        RegistryRecon(concurrency=settings.recon_registry_concurrency),
        DataWarehouseRecon(concurrency=settings.recon_warehouse_concurrency),
        EnrichmentAPIRecon(concurrency=settings.recon_enrichment_concurrency),
    ]

    tiers = [tier_1, tier_2, tier_3]
    return FallbackReconCoordinator(tiers)
