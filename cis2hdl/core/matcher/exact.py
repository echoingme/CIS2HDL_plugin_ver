"""ExactMatcher — fingerprint-based exact component matching.

Matches components by comparing their fingerprints (footprint + value + pin_count).
If fingerprints match exactly, confidence = 1.0.

v0.8.0: Also supports JEDEC_TYPE match via PST netlist data.
"""

from __future__ import annotations

import logging

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.exceptions import CIS2HDLMatchError
from cis2hdl.core.config import config

logger = logging.getLogger(__name__)


class ExactMatcher(MatcherBase):
    """Exact component matcher using ComponentDef.fingerprint.

    The fingerprint is a composite hash of footprint + value + pin_count.
    This matcher runs first in the pipeline (priority 1) and returns
    confidence=1.0 on an exact match.

    v0.8.0: Falls back to JEDEC_TYPE match when fingerprint fails.
    """

    MATCHER_NAME: str = "exact"
    MATCHER_PRIORITY: int = 1

    # Confidence for JEDEC_TYPE-based match
    CONF_JEDEC: float = 0.95

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Match source against candidates by exact fingerprint comparison.

        Args:
            source: The CIS component to match.
            candidates: HDL candidate components.

        Returns:
            MatchResult with confidence=1.0 if found, else no_match.
        """
        source_fp: str = source.fingerprint

        # ── Filter: reject fingerprint-only match if no meaningful data ──
        fp_parts = source_fp.split('|')
        if len(fp_parts) >= 2 and not fp_parts[0].strip() and not fp_parts[1].strip():
            logger.debug(
                "Exact: skipping fingerprint-only match for '%s' (fp=%s)",
                source.library_id, source_fp,
            )
            return MatchResult.no_match(source.library_id)

        for candidate in candidates:
            if candidate.fingerprint == source_fp:
                pin_mapping: dict[str, str] = self._build_pin_mapping(
                    source, candidate
                )
                logger.debug(
                    "Exact match: %s -> %s (fp=%s)",
                    source.library_id,
                    candidate.library_id,
                    source_fp,
                )
                return MatchResult(
                    confidence=1.0,
                    strategy=MatchStrategy.EXACT,
                    source_library_id=source.library_id,
                    target_library_id=candidate.library_id,
                    pin_mapping=pin_mapping,
                )

        # ── v0.8.0: JEDEC_TYPE fallback ──────────────────────────
        # When fingerprint match fails, try matching by PST JEDEC_TYPE
        # to the HDL library's chips.prt JEDEC_TYPE or part_name.
        src_jedec: str = source.extra_data.get("pst_jedec_type", "")
        if src_jedec:
            result = self._match_jedec(source, candidates, src_jedec)
            if result.target_library_id:
                return result

        logger.debug(
            "No exact match for %s (fp=%s, %d candidates checked)",
            source.library_id,
            source_fp,
            len(candidates),
        )
        return MatchResult.no_match(source.library_id)

    # ------------------------------------------------------------------
    #  JEDEC_TYPE matching (v0.8.0)
    # ------------------------------------------------------------------

    @staticmethod
    def _match_jedec(
        source: ComponentDef,
        candidates: list[ComponentDef],
        src_jedec: str,
    ) -> MatchResult:
        """Match source to candidate by JEDEC_TYPE.

        Compares the PST JEDEC_TYPE (e.g. "HSC0201-HDTA") against
        candidate chips.prt JEDEC_TYPE or part_name fields.

        Args:
            source: CIS component with pst_jedec_type in extra_data.
            candidates: HDL candidates.
            src_jedec: Normalised JEDEC_TYPE from PST data.

        Returns:
            MatchResult if unique match found, else no_match.
        """
        jedec_lower = src_jedec.lower()
        matched: list[ComponentDef] = []

        for candidate in candidates:
            # Check chips.prt JEDEC_TYPE
            cand_jedec = candidate.extra_data.get("jedec_type", "")
            if cand_jedec and cand_jedec.lower() == jedec_lower:
                matched.append(candidate)
                continue

            # Check part_name contains JEDEC_TYPE keywords
            # e.g. "CAPACITOR_0402" ← "HSC0402-HDTD" → size "0402"
            pn = candidate.part_name.lower()
            if _extract_size_code(src_jedec) and any(
                sc in pn for sc in _size_codes_from_jedec(src_jedec)
            ):
                matched.append(candidate)

        if not matched:
            return MatchResult.no_match(source.library_id)

        if len(matched) == 1:
            best = matched[0]
            pin_mapping = MatcherBase._build_pin_mapping_static(source, best)
            logger.info(
                "JEDEC match: %s → %s (jedec=%s)",
                source.library_id, best.library_id, src_jedec,
            )
            return MatchResult(
                confidence=0.95,
                strategy=MatchStrategy.EXACT,
                source_library_id=source.library_id,
                target_library_id=best.library_id,
                pin_mapping=pin_mapping,
                warnings=[f"JEDEC_TYPE match: '{src_jedec}'"],
            )

        # Multiple matches — use first
        best = matched[0]
        pin_mapping = MatcherBase._build_pin_mapping_static(source, best)
        return MatchResult(
            confidence=0.80,
            strategy=MatchStrategy.EXACT,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
            warnings=[f"JEDEC_TYPE match (ambiguous): '{src_jedec}'"],
        )

    def confidence_threshold(self) -> float:
        """Exact matching threshold from config."""
        return config.matching.exact_threshold


# ------------------------------------------------------------------
#  JEDEC helpers
# ------------------------------------------------------------------

import re as _re

#: Extract 4-digit imperial size from JEDEC_TYPE like "HSC0402-HDTD"
_JEDEC_SIZE_RE = _re.compile(r"(\d{4})")


def _extract_size_code(jedec: str) -> str:
    """Extract 4-digit package size from JEDEC_TYPE string."""
    m = _JEDEC_SIZE_RE.search(jedec)
    return m.group(1) if m else ""


def _size_codes_from_jedec(jedec: str) -> list[str]:
    """Generate candidate size codes from JEDEC_TYPE.

    e.g. "HSC0201-HDTA" → ["0201", "_0201"]
    """
    size = _extract_size_code(jedec)
    if not size:
        return []
    return [size, f"_{size}"]

