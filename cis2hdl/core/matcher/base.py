"""MatcherBase abstract base class for the component matching pipeline.

All matchers inherit from this ABC and must implement match() and
confidence_threshold().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult


class MatcherBase(ABC):
    """Abstract base class for all component matchers.

    Each matcher has a unique MATCHER_NAME and MATCHER_PRIORITY.
    Lower priority numbers run first in the pipeline.

    Class Attributes:
        MATCHER_NAME: Human-readable matcher identifier.
        MATCHER_PRIORITY: Execution priority (lower = earlier).
    """

    MATCHER_NAME: ClassVar[str] = ""
    MATCHER_PRIORITY: ClassVar[int] = 99

    @abstractmethod
    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Attempt to match a source component against candidate components.

        Args:
            source: The CIS component definition to match.
            candidates: List of HDL component definitions to match against.

        Returns:
            MatchResult with confidence, strategy, and matched target info.
            Returns MatchResult.no_match(source.library_id) on failure.
        """
        ...

    @abstractmethod
    def confidence_threshold(self) -> float:
        """Return the minimum confidence for this matcher to accept a match.

        The pipeline uses this to decide whether to stop or continue to
        the next stage.

        Returns:
            float between 0.0 and 1.0.
        """
        ...

    # ------------------------------------------------------------------
    #  Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_pin_mapping(
        source: ComponentDef,
        target: ComponentDef,
    ) -> dict[str, str]:
        """Build a pin number → pin number mapping between source and target.

        Matches pins by pin number where both sides share the same pin
        number string, producing a 1:1 mapping.

        Args:
            source: Source (CIS) component definition.
            target: Target (HDL) component definition.

        Returns:
            Dict mapping source pin numbers to target pin numbers.
        """
        mapping: dict[str, str] = {}
        target_pins: set[str] = {p.number for p in target.pins}
        for src_pin in source.pins:
            if src_pin.number in target_pins:
                mapping[src_pin.number] = src_pin.number
        return mapping
