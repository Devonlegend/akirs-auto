"""Tests for the scraper connector's advertiser → text-blob builder.

Uses lightweight fake objects to avoid needing a real database or the
heavy embedding / vector-store dependencies.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from chatbot.connectors.scraper_connector import build_advertiser_text


def _make_advertiser(**overrides):
    """Build a fake advertiser with sensible defaults; override as needed."""
    defaults = dict(
        id=42,
        name="Joe's Kitchen",
        fb_url="https://facebook.com/joeskitchen",
        first_seen=datetime(2026, 1, 1, 12, 0, 0),
        last_seen=datetime(2026, 6, 1, 12, 0, 0),
        social_links=[],
        recon_findings=[],
        social_profiles=[],
        registry_records=[],
        warehouse_votes=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_build_text_basic_name_and_url():
    adv = _make_advertiser()
    text = build_advertiser_text(adv)
    assert "Business: Joe's Kitchen" in text
    assert "Facebook URL: https://facebook.com/joeskitchen" in text


def test_build_text_social_links():
    adv = _make_advertiser(
        social_links=[
            SimpleNamespace(platform="instagram", url="https://instagram.com/joeskitchen"),
            SimpleNamespace(platform="whatsapp", url="https://wa.me/2348012345678"),
        ]
    )
    text = build_advertiser_text(adv)
    assert "Social Links:" in text
    assert "instagram: https://instagram.com/joeskitchen" in text
    assert "whatsapp:" in text


def test_build_text_recon_findings_grouped_by_kind():
    adv = _make_advertiser(
        recon_findings=[
            SimpleNamespace(kind="email", value="info@joeskitchen.ng", confidence=0.9, source="website"),
            SimpleNamespace(kind="phone", value="+2348012345678", confidence=0.8, source="website"),
        ]
    )
    text = build_advertiser_text(adv)
    assert "Email: info@joeskitchen.ng" in text
    assert "Phone: +2348012345678" in text


def test_build_text_social_profiles_with_bio():
    adv = _make_advertiser(
        social_profiles=[
            SimpleNamespace(
                platform="instagram",
                handle="joeskitchen_uyo",
                bio="Best dishes in Uyo",
                follower_count=1200,
            )
        ]
    )
    text = build_advertiser_text(adv)
    assert "Social Profiles:" in text
    assert "@joeskitchen_uyo" in text
    assert "1,200 followers" in text
    assert "Bio: Best dishes in Uyo" in text


def test_build_text_registry_records():
    adv = _make_advertiser(
        registry_records=[
            SimpleNamespace(registry="CAC", registration_number="RC-1234567", status="Active")
        ]
    )
    text = build_advertiser_text(adv)
    assert "Registry:" in text
    assert "CAC" in text
    assert "RC: RC-1234567" in text
    assert "(Active)" in text


def test_build_text_warehouse_votes_grouped_by_provider():
    adv = _make_advertiser(
        warehouse_votes=[
            SimpleNamespace(provider="PDL", kind="industry", value="Restaurant", confidence=0.9),
            SimpleNamespace(provider="brave", kind="website", value="joeskitchen.ng", confidence=0.7),
        ]
    )
    text = build_advertiser_text(adv)
    assert "Warehouse Data:" in text
    assert "PDL:" in text
    assert "industry: Restaurant" in text
    assert "brave:" in text


def test_build_text_empty_advertiser():
    adv = _make_advertiser(name=None, fb_url="")
    text = build_advertiser_text(adv)
    # With no name/url and no relationships, text should be empty or minimal.
    assert "Business:" not in text


def test_build_text_full_record():
    adv = _make_advertiser(
        social_links=[SimpleNamespace(platform="instagram", url="https://instagram.com/x")],
        recon_findings=[
            SimpleNamespace(kind="email", value="a@b.com", confidence=0.9, source="website")
        ],
        registry_records=[
            SimpleNamespace(registry="CAC", registration_number="RC-1", status="Active")
        ],
        warehouse_votes=[
            SimpleNamespace(provider="PDL", kind="industry", value="Food", confidence=0.9)
        ],
    )
    text = build_advertiser_text(adv)
    # All sections present.
    assert "Business: Joe's Kitchen" in text
    assert "Social Links:" in text
    assert "Email:" in text
    assert "Registry:" in text
    assert "Warehouse Data:" in text
