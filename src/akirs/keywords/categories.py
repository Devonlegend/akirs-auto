"""Business category taxonomy used in keyword expansion."""

BUSINESS_CATEGORIES: tuple[str, ...] = (
    "food",
    "restaurant",
    "fashion",
    "clothing",
    "beauty",
    "cosmetics",
    "education",
    "tutoring",
    "school",
    "health",
    "clinic",
    "pharmacy",
    "real estate",
    "property",
    "transport",
    "logistics",
    "fintech",
    "loan",
    "retail",
    "supermarket",
    "agriculture",
    "farm",
    "hotel",
    "lodging",
    "events",
    "wedding",
    "automobile",
    "construction",
    "media",
    "marketing",
)


def default_categories() -> list[str]:
    return list(BUSINESS_CATEGORIES)
