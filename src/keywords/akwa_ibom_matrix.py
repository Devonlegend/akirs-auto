"""Akwa Ibom keyword matrix — hyper-local, cultural, and commercial keyword buckets.

This module provides a structured keyword taxonomy tailored to Akwa Ibom State,
Nigeria. It powers the keyword expansion layer with location-embedded terms that
don't require an additional location qualifier — they already carry geographic
signal through landmarks, dialect markers, or explicit "{service} in {city}"
patterns.

Buckets:
    hyper_local:       Named landmarks, estates, roads, neighborhoods, institutions
    state_identity:    Cultural, ethnic, dialect, cuisine, and slogan markers
    commercial_intent: Cartesian product of location tokens × business suffixes,
                       emitted across four templates:
                           "{suffix} in {loc}"
                           "{loc} {suffix}"
                           "best {suffix} in {loc}"
                           "{suffix} near {loc}"
"""

from __future__ import annotations

import logging
from itertools import product
from typing import Final

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Location tokens used in the commercial_intent cartesian
# ---------------------------------------------------------------------------
# Capital + state name + abbreviation + secondary cities. Secondary cities are
# included because advertisers frequently target Eket/Ikot Ekpene/Oron as
# proxies for state-wide reach.
_LOCATION_TOKENS: Final[tuple[str, ...]] = (
    "Uyo",
    "AKS",
    "Akwa Ibom",
    "Akwa Ibom State",
    "Eket",
    "Ikot Ekpene",
    "Oron",
    "Abak",
    "Itu",
)

# ---------------------------------------------------------------------------
# Commercial suffixes — services and businesses common in AKS
# ---------------------------------------------------------------------------
_COMMERCIAL_SUFFIXES: Final[tuple[str, ...]] = (
    # Retail / fashion
    "boutique", "thrift", "ankara", "fashion designer", "tailor",
    "shoe vendor", "wig vendor", "perfume",
    # Beauty
    "makeup artist", "salon", "barber", "lash tech", "nail tech",
    "spa", "skincare",
    # Food & hospitality
    "restaurant", "catering", "small chops", "cake", "shawarma",
    "bakery", "hotel", "lounge",
    # Logistics / mobility
    "delivery", "logistics", "dispatch rider", "haulage", "car hire",
    "uber driver", "bolt driver",
    # Real estate / construction
    "real estate", "shortlet", "apartment", "land for sale",
    "architecture", "interior design", "POP",
    # Tech / professional services
    "tech hub", "coworking", "phone repair", "laptop repair",
    "web designer", "graphics designer", "social media manager",
    "school", "tutorial center", "driving school",
    # Health / wellness
    "pharmacy", "gym", "fitness coach", "physiotherapy",
    # Finance / hustle economy
    "POS agent", "Bet9ja", "betting", "forex trader", "crypto",
    "loan", "fintech agent",
    # Events / entertainment
    "event planner", "DJ", "MC", "photographer", "videographer",
    "rental",
    # Professional / civic
    "lawyer", "doctor", "dentist", "mechanic", "electrician",
    "plumber", "painter", "surveyor", "printing", "florist",
    "laundry", "cleaning",
)

# ---------------------------------------------------------------------------
# Commercial-intent templates
# ---------------------------------------------------------------------------
# Each template is f-string-ish; only the placeholders {loc} and {suffix} are
# substituted. Kept as a tuple so adding a new template is a one-line change.
_COMMERCIAL_TEMPLATES: Final[tuple[str, ...]] = (
    "{suffix} in {loc}",
    "{loc} {suffix}",
    "best {suffix} in {loc}",
    "{suffix} near {loc}",
)


def _build_commercial_intent() -> list[str]:
    """Cartesian (location × suffix × template), dedup-preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for loc, suffix, tpl in product(
        _LOCATION_TOKENS, _COMMERCIAL_SUFFIXES, _COMMERCIAL_TEMPLATES
    ):
        kw = tpl.format(loc=loc, suffix=suffix)
        key = kw.lower()
        if key not in seen:
            seen.add(key)
            out.append(kw)
    return out


# ---------------------------------------------------------------------------
# Keyword Buckets
# ---------------------------------------------------------------------------
AKWA_IBOM_KEYWORD_BUCKETS: Final[dict[str, list[str]]] = {
    # Bucket 1: Landmarks, roads, estates, markets, institutions, venues
    "hyper_local": [
        # Major arteries
        "Aka Road",
        "Abak Road",
        "Ikot Ekpene Road",
        "Oron Road",
        "Nwaniba Road",
        "Udo Udoma Avenue",
        "Wellington Bassey Way",
        "Nsikak Eduok Avenue",
        "Babangida Avenue",
        "IBB Way",
        "Brook Street",
        "Calabar-Itu Road",
        "Four Lanes",
        # Estates & neighborhoods
        "Osongama Estate",
        "Shelter Afrique",
        "Ewet Housing",
        "Ewet Estate",
        "Federal Housing",
        "Aka Itiam",
        "Ikot Oku Ikono",
        "Use Offot",
        "Mbierebe",
        "Ekom Iman",
        "Atiku Abubakar Avenue",
        # Markets
        "Itam Market",
        "Akpan Andem Market",
        "Urua Akpan Andem",
        "Plaza Market",
        "Etuk Street market",
        # Institutions & education
        "UniUyo",
        "University of Uyo",
        "AKSU",
        "Akwa Ibom State University",
        "Heritage Polytechnic",
        "Maritime Academy Oron",
        "Ritman University",
        # Landmarks & venues
        "Ibom Plaza",
        "Ibom Hall",
        "Ibom Connection",
        "Ibom Tropicana",
        "Tropicana Entertainment Centre",
        "Godswill Akpabio Stadium",
        "Ibom International Stadium",
        "Ibom E-Library",
        "Le Meridien Ibom Hotel",
        "Ibom Icon Hotel",
        "Ibom Specialist Hospital",
        "Ibom Air",
        "Ibom Airport",
        "Victor Attah International Airport",
        "Unity Park",
        # Religious / civic
        "Qua Iboe Church Headquarters",
        "Government House Uyo",
        "House of Assembly Uyo",
    ],
    # Bucket 2: Cultural & dialect markers, cuisine, slogans, festivals
    "state_identity": [
        # Identity / political slogans
        "Akwa Ibom",
        "Akwa Ibom State",
        "Dakkada",
        "Ibom",
        "Promise Land",
        "Land of Promise",
        "Akwa Cross",
        "Uyo pride",
        "ARISE Agenda",
        # Ethnic groups
        "Ibibio",
        "Annang",
        "Oron people",
        "Eket people",
        "Obolo",
        "Efik-Ibibio",
        # Dialect / cultural markers
        "Mbok",
        "Sosongo",
        "Abadie",
        "Nno",
        "Ekomette",
        # Cuisine (high-affinity for food businesses)
        "Edikang Ikong",
        "Afang",
        "Atama soup",
        "Ekpang Nkukwo",
        "Editan",
        "Iwuk Edesi",
        "Nsala soup",
        "Fisherman soup",
        "Afia Efere",
        # Festivals & arts
        "Ekpe masquerade",
        "Ekong dance",
        "Abang dance",
        "Ekombi",
        "Uyo Carnival",
        "Ibom Cultural Festival",
        # Regional descriptors
        "Niger Delta",
        "South South Nigeria",
        "South-South",
    ],
    # Bucket 3: Business + Location combos (populated at import time)
    "commercial_intent": _build_commercial_intent(),
}


def generate_akwa_ibom_keywords() -> list[str]:
    """Generate a deduplicated, sorted list of all Akwa Ibom keywords.

    Combines hyper-local landmarks, state identity markers, and commercial
    intent combos into a single flat list. Commercial intent entries are
    generated across four templates per (location, suffix) pair — see
    ``_COMMERCIAL_TEMPLATES``.

    Returns:
        Sorted list of unique keyword strings.
    """
    seen: set[str] = set()
    result: list[str] = []

    for bucket in ("hyper_local", "state_identity", "commercial_intent"):
        for kw in AKWA_IBOM_KEYWORD_BUCKETS[bucket]:
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
