"""Layered keyword expansion: curated base × Akwa Ibom matrix × user-supplied × optional LLM, with hard cap."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.geography import default_locations
from keywords.akwa_ibom_matrix import generate_akwa_ibom_keywords
from keywords.categories import default_categories
from keywords.llm_expander import get_expander

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeywordRunSpec:
    keyword: str
    location: str | None  # the geography name that drove this run


def expand(
    locations: list[str] | None = None,
    categories: list[str] | None = None,
    user_keywords: list[str] | None = None,
    use_llm: bool = False,
    cap: int = 50,
) -> list[KeywordRunSpec]:
    """Build the keyword-run list.

    Order of generation:
        1. Curated cartesian (location × category)
        2. Akwa Ibom keyword matrix (hyper-local, cultural, commercial)
        3. User-supplied raw keywords
        4. LLM-expanded variants

    Order matters because we truncate at ``cap``.
    """
    locs = locations if locations is not None else default_locations()
    cats = categories if categories is not None else default_categories()

    out: list[KeywordRunSpec] = []
    seen: set[tuple[str, str | None]] = set()

    def _add(keyword: str, location: str | None) -> bool:
        """Append a keyword spec if not already seen. Returns True when cap is hit."""
        key = (keyword, location)
        if key in seen:
            return False
        seen.add(key)
        out.append(KeywordRunSpec(keyword=keyword, location=location))
        return len(out) >= cap

    # Layer 1 — Curated cartesian: location × category
    for loc in locs:
        for cat in cats:
            kw = f"{cat} {loc}"
            if _add(kw, loc):
                return out

    # Layer 2 — Akwa Ibom keyword matrix (already embeds location context)
    for kw in generate_akwa_ibom_keywords():
        if _add(kw, None):
            logger.debug("Cap reached during Akwa Ibom matrix expansion at %d keywords", len(out))
            return out

    # Layer 3 — User-supplied raw keywords (no location attribution unless caller embedded it)
    for kw in user_keywords or []:
        if _add(kw, None):
            return out

    # Layer 4 — LLM expansion across already-generated keywords
    if use_llm:
        expander = get_expander()
        for spec in list(out):
            for variant in expander.expand(spec.keyword):
                if _add(variant, spec.location):
                    return out

    return out
