from akirs.keywords import expand
from akirs.keywords.generator import KeywordRunSpec


def test_cap_enforced_below_cartesian():
    # 31 LGAs × 30 categories = 930. Cap at 50 should truncate.
    result = expand(cap=50)
    assert len(result) == 50


def test_explicit_locations_and_categories():
    result = expand(locations=["Uyo", "Eket"], categories=["food", "health"])
    assert len(result) == 4
    keywords = {spec.keyword for spec in result}
    assert keywords == {"food Uyo", "health Uyo", "food Eket", "health Eket"}


def test_user_keywords_appended():
    result = expand(
        locations=["Uyo"],
        categories=["food"],
        user_keywords=["Akwa Ibom market"],
    )
    assert KeywordRunSpec("food Uyo", "Uyo") in result
    assert KeywordRunSpec("Akwa Ibom market", None) in result


def test_llm_expansion_only_runs_when_flag_set():
    no_llm = expand(locations=["Uyo"], categories=["food"], use_llm=False)
    with_llm = expand(locations=["Uyo"], categories=["food"], use_llm=True, cap=20)
    assert len(with_llm) > len(no_llm)


def test_duplicate_user_keyword_dedupes():
    # Identical (keyword, location) pair should dedupe: a user keyword that
    # matches an already-emitted curated entry exactly is dropped.
    result = expand(
        locations=["Uyo"],
        categories=["food"],
        user_keywords=["food Uyo", "food Uyo"],  # double-duplicate
    )
    # User keywords have location=None, so they're distinct from curated location-tagged entries.
    # But two identical user keywords should collapse to one.
    assert sum(1 for r in result if r.keyword == "food Uyo" and r.location is None) == 1
