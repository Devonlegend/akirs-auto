"""Shared extraction utilities for recon sources.

Centralises regex patterns and parsing logic for emails, phone numbers,
and street addresses so every ReconSource uses the same robust rules.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Email extraction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9][a-zA-Z0-9_.+-]*@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?",
)

_ASSET_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    ".map", ".ico",
})


def extract_emails(text: str) -> set[str]:
    """Return a de-duplicated set of plausible email addresses from *text*.

    Filters out strings that look like asset filenames (e.g. ``icon@2x.png``)
    and common no-reply / system addresses.
    """
    raw = _EMAIL_RE.findall(text)
    results: set[str] = set()
    for addr in raw:
        addr_lower = addr.lower()
        # Skip asset-like extensions
        if any(addr_lower.endswith(ext) for ext in _ASSET_EXTENSIONS):
            continue
        # Skip obvious non-human addresses
        if addr_lower.startswith(("noreply@", "no-reply@", "mailer-daemon@")):
            continue
        results.add(addr)
    return results


# ---------------------------------------------------------------------------
# Phone extraction
# ---------------------------------------------------------------------------

# Matches Nigerian (+234 …), international (+1/+44 …) and local formats.
# Requires at least 7 digits so we don't pick up random short numbers.
_PHONE_RE = re.compile(
    r"""
    (?<!\d)                          # not preceded by a digit
    (?:\+?\d{1,3}[\s.-]?)?          # optional country code
    \(?0?\d{2,4}\)?                 # area / operator code
    [\s.\-]?
    \d{3,4}                         # subscriber block 1
    [\s.\-]?
    \d{3,4}                         # subscriber block 2
    (?!\d)                          # not followed by a digit
    """,
    re.VERBOSE,
)

_MIN_DIGIT_COUNT = 7


def extract_phones(text: str, *, max_results: int = 5) -> list[str]:
    """Return a list of phone-number strings found in *text*.

    Results are capped at *max_results* to avoid noise from pages that list
    many unrelated numbers (e.g. product IDs).
    """
    raw = _PHONE_RE.findall(text)
    seen: set[str] = set()
    results: list[str] = []
    for phone in raw:
        normalised = re.sub(r"[\s()\-.]", "", phone)
        digit_count = sum(c.isdigit() for c in normalised)
        if digit_count < _MIN_DIGIT_COUNT:
            continue
        if normalised in seen:
            continue
        seen.add(normalised)
        results.append(phone.strip())
        if len(results) >= max_results:
            break
    return results


# ---------------------------------------------------------------------------
# Address extraction
# ---------------------------------------------------------------------------

_ADDRESS_KEYWORDS = re.compile(
    r"(?:address|location|visit\s+us|headquarters|office|hq)\s*[:\-–]\s*",
    re.IGNORECASE,
)

_ADDRESS_SENTENCE = re.compile(
    r"(?:address|location|visit\s+us|headquarters|office|hq)"
    r"\s*[:\-–]\s*"
    r"(.+?)(?:\.|<|$)",
    re.IGNORECASE,
)


def extract_addresses(text: str) -> list[str]:
    """Heuristic extraction of street / office addresses.

    Looks for sentences prefixed by common address-indicator keywords.
    """
    results: list[str] = []
    for match in _ADDRESS_SENTENCE.finditer(text):
        addr = match.group(1).strip()
        # Skip if too short to be a real address
        if len(addr) < 10 or len(addr) > 300:
            continue
        results.append(addr)
    return results


# ---------------------------------------------------------------------------
# Domain extraction
# ---------------------------------------------------------------------------


def extract_domain(url: str) -> str | None:
    """Return the bare domain (no ``www.``) from a URL, or *None*."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.hostname
        if not host:
            return None
        return host.removeprefix("www.")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Bio text helper (social profiles)
# ---------------------------------------------------------------------------


def extract_contact_from_bio(bio: str) -> dict[str, list[str]]:
    """Parse a social-media bio for emails and phones.

    Returns ``{"emails": [...], "phones": [...]}``.
    """
    return {
        "emails": sorted(extract_emails(bio)),
        "phones": extract_phones(bio, max_results=3),
    }
