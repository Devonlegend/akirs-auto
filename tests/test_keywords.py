from akirs.keywords import expand
from akirs.keywords.generator import KeywordRunSpec


def test_cap_enforced_below_cartesian():
    # 31 LGAs × 30 categories = 930. Cap at 50 should truncate.
    result = expand(cap=50)
    assert len(result) == 50


def test_explicit_locations_and_categories():
    # Layer 1 (curated cartesian) emits |locations| × |categories| = 4 entries.
    # Layer 2 (Akwa Ibom matrix) ALWAYS runs and adds geo-tagged variants.
    # We assert presence of the curated entries rather than exact length.
    result = expand(locations=["Uyo", "Eket"], categories=["food", "health"])
    keywords_with_loc = {(spec.keyword, spec.location) for spec in result}
    assert ("food Uyo", "Uyo") in keywords_with_loc
    assert ("health Uyo", "Uyo") in keywords_with_loc
    assert ("food Eket", "Eket") in keywords_with_loc
    assert ("health Eket", "Eket") in keywords_with_loc


def test_user_keywords_appended():
    # When the cap allows, user keywords reach the output.  Raise the cap
    # high enough that Layer-2 (Akwa Ibom matrix) doesn't crowd them out.
    result = expand(
        locations=["Uyo"],
        categories=["food"],
        user_keywords=["Akwa Ibom market never duplicated"],
        cap=10_000,
    )
    assert KeywordRunSpec("food Uyo", "Uyo") in result
    assert KeywordRunSpec("Akwa Ibom market never duplicated", None) in result


def test_llm_expansion_only_runs_when_flag_set():
    no_llm = expand(locations=["Uyo"], categories=["food"], use_llm=False, cap=10_000)
    with_llm = expand(locations=["Uyo"], categories=["food"], use_llm=True, cap=10_000)
    assert len(with_llm) > len(no_llm)


def test_duplicate_user_keyword_dedupes():
    # Two identical user keywords should collapse to one — high cap so the
    # entries actually reach the user-keyword layer instead of being clipped.
    unique_marker = "non-overlapping-test-keyword-xyz"
    result = expand(
        locations=["Uyo"],
        categories=["food"],
        user_keywords=[unique_marker, unique_marker],
        cap=10_000,
    )
    matches = [r for r in result if r.keyword == unique_marker and r.location is None]
    assert len(matches) == 1
