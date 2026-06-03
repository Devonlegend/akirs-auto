"""Abstract base for scrapers."""

from abc import ABC, abstractmethod
from typing import Any


class AbstractScraper(ABC):
    """Each scraper takes a Playwright page and exposes a scrape() coroutine."""

    @abstractmethod
    async def setup(self, **kwargs: Any) -> None: ...

    @abstractmethod
    async def scrape(self, target_count: int) -> list[dict]: ...
