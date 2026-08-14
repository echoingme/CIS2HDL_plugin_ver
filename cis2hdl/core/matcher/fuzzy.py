"""FuzzyNameMatcher — fuzzy component name matching via rapidfuzz.

Uses token_sort_ratio to compare part names between CIS and HDL components.
Runs at priority 2 (after ExactMatcher).
"""

from __future__ import annotations

import logging

from rapidfuzz import fuzz, process

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.exceptions import CIS2HDLMatchError
from cis2hdl.core.config import config

logger = logging.getLogger(__name__)


class FuzzyNameMatcher(MatcherBase):
    """Fuzzy component name matcher using rapidfuzz token_sort_ratio.

    Part names are compared with token_sort_ratio (order-independent
    token matching).  A score_cutoff of 60 filters out poor matches.
    """

    MATCHER_NAME: str = "fuzzy"
    MATCHER_PRIORITY: int = 2

    # Minimum rapidfuzz score to consider (0-100).
    SCORE_CUTOFF: int = 60

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Match source against candidates by fuzzy part-name comparison.

        Args:
            source: The CIS component to match.
            candidates: HDL candidate components.

        Returns:
            MatchResult with confidence=score/100 if a match passes cutoff,
            else no_match.
        """
        if not candidates:
            logger.debug("Fuzzy: no candidates for %s", source.library_id)
            return MatchResult.no_match(source.library_id)

        # Build name list + index map
        names: list[str] = [c.part_name for c in candidates]

        result = process.extractOne(
            source.part_name,
            names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.SCORE_CUTOFF,
        )

        if result is None:
            logger.debug(
                "Fuzzy: no match above cutoff %d for '%s'",
                self.SCORE_CUTOFF,
                source.part_name,
            )
            return MatchResult.no_match(source.library_id)

        matched_name: str
        score: float
        idx: int
        matched_name, score, idx = result

        best: ComponentDef = candidates[idx]
        confidence: float = score / 100.0

        pin_mapping: dict[str, str] = self._build_pin_mapping(source, best)

        logger.debug(
            "Fuzzy match: %s -> %s (score=%.1f, conf=%.2f)",
            source.library_id,
            best.library_id,
            score,
            confidence,
        )

        return MatchResult(
            confidence=confidence,
            strategy=MatchStrategy.FUZZY,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
        )

    def confidence_threshold(self) -> float:
        """Fuzzy matching threshold from config."""
        return config.matching.fuzzy_threshold

