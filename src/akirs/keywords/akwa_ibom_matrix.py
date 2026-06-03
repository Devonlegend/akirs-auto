"""Akwa Ibom keyword matrix — hyper-local, cultural, and commercial keyword buckets.

This module provides a structured keyword taxonomy tailored to Akwa Ibom State,
Nigeria. It powers the keyword expansion layer with location-embedded terms that
don't require an additional location qualifier — they already carry geographic
signal through landmarks, dialect markers, or explicit "{service} in {city}"
patterns.

Buckets:
    hyper_local:       Named landmarks, estates, roads, and neighborhoods
    state_identity:    Cultural, ethnic, and dialect markers
    commercial_intent: Cartesian product of location tokens × business suffixes
"""

from __future__ import annotations

import logging
from typing import Final

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Location tokens used in the commercial_intent cartesian
# ---------------------------------------------------------------------------
_LOCATION_TOKENS: Final[tuple[str, ...]] = (
    "Uyo",
    "AKS",
    "Akwa Ibom",
    "Eket",
    "Ikot Ekpene",
)

# ---------------------------------------------------------------------------
# Commercial suffixes — services and businesses common in AKS
# ---------------------------------------------------------------------------
_COMMERCIAL_SUFFIXES: Final[tuple[str, ...]] = (
    "delivery",
    "boutique",
    "real estate",
    "makeup artist",
    "logistics",
    "catering",
    "hotel",
    "restaurant",
    "gym",
    "salon",
    "barber",
    "laundry",
    "cleaning",
    "photography",
    "printing",
    "cake",
    "fashion designer",
    "tailor",
    "event planner",
    "DJ",
    "MC",
    "baker",
    "florist",
    "mechanic",
    "electrician",
    "plumber",
    "painter",
    "interior design",
    "architecture",
    "surveyor",
    "lawyer",
    "doctor",
    "dentist",
    "pharmacy",
    "school",
    "driving school",
    "tech hub",
    "coworking",
    "POS agent",
    "Bet9ja",
    "betting",
    "forex trader",
    "crypto",
    "phone repair",
    "laptop repair",
)

# ---------------------------------------------------------------------------
# Keyword Buckets
# ---------------------------------------------------------------------------
AKWA_IBOM_KEYWORD_BUCKETS: Final[dict[str, list[str]]] = {
    # Bucket 1: Landmarks & Neighborhoods
    "hyper_local": [
        "Aka Road",
        "Abak Road",
        "Ikot Ekpene Road",
        "Osongama Estate",
        "Shelter Afrique",
        "UniUyo",
        "Ibom Tropicana",
        "Ibom Plaza",
        "Ibom Hall",
        "Ibom Connection",
        "Ewet Housing",
        "Four Lanes",
        "Nwaniba Road",
        "IBB Way",
        "Oron Road",
        "Udo Udoma Avenue",
        "Babangida Avenue",
        "Wellington Bassey Way",
        "Aka Itiam",
        "Itam Market",
        "Brook Street",
        "Nsikak Eduok Avenue",
        "Godswill Akpabio Stadium",
        "Ibom E-Library",
        "Le Meridien Ibom Hotel",
        "Ibom Specialist Hospital",
        "Ibom Air",
        "Ikot Oku Ikono",
        "Mbierebe",
        "Ekom Iman",
        "Use Offot",
    ],
    # Bucket 2: Cultural & Dialect Markers
    "state_identity": [
        "Akwa Ibom",
        "Dakkada",
        "Ibom",
        "Edikang Ikong",
        "Afang",
        "Uyo pride",
        "Ibibio",
        "Annang",
        "Oron people",
        "Ekpe masquerade",
        "Ibom culture",
        "promise land",
        "Akwa Cross",
        "Niger Delta",
        "South South Nigeria",
    ],
    # Bucket 3: Business + Location Combos (populated at import time)
    "commercial_intent": [
        f"{suffix} in {loc}"
        for loc in _LOCATION_TOKENS
        for suffix in _COMMERCIAL_SUFFIXES
    ]
    + [
        f"{loc} {suffix}"
        for loc in _LOCATION_TOKENS
        for suffix in _COMMERCIAL_SUFFIXES
    ],
}


def generate_akwa_ibom_keywords() -> list[str]:
    """Generate a deduplicated, sorted list of all Akwa Ibom keywords.

    Combines hyper-local landmarks, state identity markers, and commercial
    intent combos into a single flat list. Commercial intent entries are
    generated in two patterns per (location, suffix) pair:

    * ``"{suffix} in {location}"``  — matches "delivery in Uyo"
    * ``"{location} {suffix}"``     — matches "Uyo delivery"

    Returns:
        Sorted list of unique keyword strings.
    """
    seen: set[str] = set()
    result: list[str] = []

    # Emit hyper_local as-is
    for kw in AKWA_IBOM_KEYWORD_BUCKETS["hyper_local"]:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(kw)

    # Emit state_identity as-is
    for kw in AKWA_IBOM_KEYWORD_BUCKETS["state_identity"]:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(kw)

    # Emit commercial_intent combos
    for kw in AKWA_IBOM_KEYWORD_BUCKETS["commercial_intent"]:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(kw)

    result.sort(key=str.lower)
    logger.debug("Generated %d Akwa Ibom keywords", len(result))
    return result


def get_keyword_buckets() -> dict[str, list[str]]:
    """Return the raw keyword buckets for inspection or testing.

    Returns:
        Dictionary mapping bucket names to their keyword lists. The returned
        dict is a shallow copy — mutating it will not affect the module-level
        constant.
    """
    return dict(AKWA_IBOM_KEYWORD_BUCKETS)
