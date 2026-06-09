import pytest

from src.db.repositories import AdvertiserRepository, ReconRepository, SocialLinkRepository


@pytest.mark.asyncio
async def test_upsert_advertiser_creates_then_returns_existing(session):
    repo = AdvertiserRepository(session)
    adv1, created1 = await repo.upsert(fb_url="https://facebook.com/foo", name="Foo")
    assert created1 is True
    adv2, created2 = await repo.upsert(fb_url="https://facebook.com/foo", name="Foo Renamed")
    assert created2 is False
    assert adv1.id == adv2.id
    assert adv2.name == "Foo Renamed"


@pytest.mark.asyncio
async def test_social_links_dedupe_on_url(session):
    adv_repo = AdvertiserRepository(session)
    link_repo = SocialLinkRepository(session)
    adv, _ = await adv_repo.upsert(fb_url="https://facebook.com/bar", name="Bar")
    inserted = await link_repo.add_many(
        adv.id,
        [
            {"platform": "instagram", "url": "https://instagram.com/bar"},
            {"platform": "instagram", "url": "https://instagram.com/bar"},  # dup
            {"platform": "website", "url": "https://bar.com"},
        ],
    )
    assert inserted == 2
    links = await link_repo.list_for_advertiser(adv.id)
    urls = {l.url for l in links}
    assert urls == {"https://instagram.com/bar", "https://bar.com"}


@pytest.mark.asyncio
async def test_recon_findings_persist(session):
    adv_repo = AdvertiserRepository(session)
    recon_repo = ReconRepository(session)
    adv, _ = await adv_repo.upsert(fb_url="https://facebook.com/baz", name="Baz")
    count = await recon_repo.add_findings(
        adv.id,
        [
            {"source": "search", "kind": "mention", "value": "https://example.com/baz", "confidence": 0.4},
            {"source": "social", "kind": "bio", "value": "...", "confidence": 0.6},
        ],
    )
    assert count == 2
    findings = await recon_repo.list_for_advertiser(adv.id)
    assert {f.source for f in findings} == {"search", "social"}
