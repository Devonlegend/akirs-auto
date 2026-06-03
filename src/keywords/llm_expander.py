"""Pluggable keyword expander.

The default implementation does lightweight morphological expansion only — no
model calls. A future custom LLM can be swapped in by registering a different
expander via `set_expander`.
"""

from abc import ABC, abstractmethod


class LLMExpander(ABC):
    @abstractmethod
    def expand(self, term: str) -> list[str]: ...


class MorphologicalExpander(LLMExpander):
    """Static variants — abbreviations, plurals, common misspellings."""

    AKWA_IBOM_ALIASES = ("Akwa Ibom", "AKS", "Akwaibom", "akwa-ibom", "AK Ibom")

    def expand(self, term: str) -> list[str]:
        out: set[str] = {term, term.lower()}
        lowered = term.lower()
        for alias in self.AKWA_IBOM_ALIASES:
            if alias.lower() in lowered:
                for other in self.AKWA_IBOM_ALIASES:
                    out.add(lowered.replace(alias.lower(), other.lower()))

        if not term.endswith("s"):
            out.add(term + "s")
        if " " in term:
            out.add(term.replace(" ", ""))
            out.add(term.replace(" ", "-"))

        return sorted(out)


_default = MorphologicalExpander()
_active: LLMExpander = _default


def get_expander() -> LLMExpander:
    return _active


def set_expander(expander: LLMExpander) -> None:
    global _active
    _active = expander


def reset_expander() -> None:
    global _active
    _active = _default
