"""Advertiser -> text blob builder for the taxation agent.

Self-contained within ``src/`` (mirrors the chatbot connector's
``build_advertiser_text``) so the scraper package keeps no dependency on the
chatbot package.
"""

from __future__ import annotations

from src.db.models import Advertiser


def build_profile_text(adv: Advertiser) -> str:
    """Render an advertiser + eager-loaded relations into a readable blob.

    Expects ``social_links``, ``recon_findings``, ``social_profiles``,
    ``registry_records``, and ``warehouse_votes`` to be loaded.
    """
    lines: list[str] = []

    if adv.name:
        lines.append(f"Business: {adv.name}")
    if adv.fb_url:
        lines.append(f"Facebook URL: {adv.fb_url}")
    if adv.first_seen:
        lines.append(f"First Seen: {adv.first_seen.isoformat()}")
    if adv.last_seen:
        lines.append(f"Last Seen: {adv.last_seen.isoformat()}")

    ad_count = len(adv.ads or [])
    if ad_count:
        lines.append(f"Active Ads: {ad_count}")

    social_links = adv.social_links or []
    if social_links:
        lines.append("Social Links:")
        for sl in social_links:
            lines.append(f"  {sl.platform}: {sl.url}")

    social_profiles = adv.social_profiles or []
    if social_profiles:
        lines.append("Social Profiles:")
        for sp in social_profiles:
            parts = [f"  {sp.platform}"]
            if sp.handle:
                parts.append(f"@{sp.handle}")
            if sp.follower_count is not None:
                parts.append(f"({sp.follower_count:,} followers)")
            lines.append(" ".join(parts))
            if sp.bio:
                lines.append(f"    Bio: {sp.bio}")

    recon_findings = adv.recon_findings or []
    if recon_findings:
        by_kind: dict[str, list[tuple[str, float, str]]] = {}
        for rf in recon_findings:
            by_kind.setdefault(rf.kind, []).append((rf.value, rf.confidence or 0.5, rf.source))
        for kind, items in sorted(by_kind.items()):
            unique_vals: dict[str, tuple[float, str]] = {}
            for v, c, s in items:
                if v not in unique_vals or c > unique_vals[v][0]:
                    unique_vals[v] = (c, s)
            label = kind.replace("_", " ").title()
            vals = ", ".join(
                f"{v} (conf: {c:.2f}, src: {s})" for v, (c, s) in sorted(unique_vals.items())
            )
            lines.append(f"{label}: {vals}")

    registry_records = adv.registry_records or []
    if registry_records:
        lines.append("Registry:")
        for rr in registry_records:
            parts = [f"  {rr.registry}"]
            if rr.registration_number:
                parts.append(f"RC: {rr.registration_number}")
            if rr.status:
                parts.append(f"({rr.status})")
            lines.append(" ".join(parts))

    warehouse_votes = adv.warehouse_votes or []
    if warehouse_votes:
        by_provider: dict[str, list[str]] = {}
        for wv in warehouse_votes:
            by_provider.setdefault(wv.provider, []).append(
                f"{wv.kind}: {wv.value} ({wv.confidence:.2f})"
            )
        lines.append("Warehouse Data:")
        for provider, items in sorted(by_provider.items()):
            lines.append(f"  {provider}: {' | '.join(items)}")

    return "\n".join(lines)
