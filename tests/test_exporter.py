import pytest

from akirs.exporters import CSVExportService
from akirs.db.repositories import AdvertiserRepository, SocialLinkRepository


@pytest.mark.asyncio
async def test_csv_export_includes_advertiser_with_no_links(session):
    adv_repo = AdvertiserRepository(session)
    link_repo = SocialLinkRepository(session)
    adv1, _ = await adv_repo.upsert("https://facebook.com/with-links", "WithLinks")
    adv2, _ = await adv_repo.upsert("https://facebook.com/no-links", "NoLinks")
    await link_repo.add_many(adv1.id, [
        {"platform": "instagram", "url": "https://instagram.com/withlinks"},
        {"platform": "website", "url": "https://withlinks.com"},
    ])
    await session.commit()

    csv_text = await CSVExportService(session).to_string()
    lines = csv_text.strip().splitlines()
    header, *rows = lines
    assert header.split(",") == [
        "ad_id", "advertiser_name", "advertiser_url",
        "social_platform", "social_url",
        "recon_legal_name", "recon_emails", "recon_phones",
        "recon_addresses", "recon_sources",
        "scraped_at",
    ]
    assert len(rows) == 3  # 2 link rows for adv1 + 1 empty row for adv2
    assert any("NoLinks" in r and ",," in r for r in rows)
