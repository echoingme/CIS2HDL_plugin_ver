"""FallbackMatcher — prefix-filter fallback matching for Phase 2B chain.

v2.0 Simplified: Cross-type scoring (v1.0 _score_candidate) has been
removed.  FallbackMatcher now operates within a type-filtered candidate
pool (provided by CandidatePoolBuilder), so its job is simply:

1. Filter candidates by refdes prefix
2. Do three-level matching: exact → size → prefix
3. Return the best match

This is effectively the v0.8.2 approach, restored as the last level
of the Phase 2B ActiveMatcher chain.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar

from cis2hdl.core.config import config
from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.matcher.prefix_filter import extract_prefix
from cis2hdl.core.matcher.value_matcher import extract_pkg_size

logger = logging.getLogger(__name__)

# Hardcoded fallback for VALUE_CATEGORY_HINTS (used when YAML missing)
_DEFAULT_VALUE_HINTS: dict[str, list[str]] = {
    "DZ": ["zener", "diode", "tvs"],
    "DZ_": ["zener", "diode", "tvs"],
    "DZ3": ["zener", "diode", "tvs"],
    "MJ8": ["connector", "rj45"],
    "UART": ["connector", "header"],
    "USB": ["connector", "header"],
    "TESTPOINT": ["hole", "test_point", "mark"],
    "NH": ["inductor", "ferrite", "ferrite_bead"],
    "UH": ["inductor", "ferrite"],
}


class FallbackMatcher(MatcherBase):
    """Prefix-filter fallback matcher for the Phase 2B chain.

    v2.0: Simplified — operates within a pre-filtered type pool.
    Uses three-level matching:
       - **exact** (conf=1.0): footprint size AND value both match
       - **size**  (conf=0.8): footprint size matches, value does not
       - **prefix** (conf=0.5): only refdes prefix match
    """

    MATCHER_NAME: ClassVar[str] = "fallback"
    MATCHER_PRIORITY: ClassVar[int] = 4

    CONF_EXACT: ClassVar[float] = 1.0
    CONF_SIZE: ClassVar[float] = 0.8
    CONF_PREFIX: ClassVar[float] = 0.5

    @property
    def VALUE_CATEGORY_HINTS(self) -> dict[str, list[str]]:
        try:
            from .match_config import MatchConfig
            return MatchConfig.instance().value_category_hints
        except Exception:
            return _DEFAULT_VALUE_HINTS

    # ── Static helpers ───────────────────────────────────────────────

    @staticmethod
    def extract_refdes_prefix(text: str) -> str:
        """Extract alphabetic prefix from a library_id or refdes string."""
        return extract_prefix(text)

    @staticmethod
    def extract_pkg_size(footprint: str) -> str:
        """Extract the package size code from a footprint string."""
        return extract_pkg_size(footprint)

    @staticmethod
    def normalize_value(value: str) -> str:
        """Normalise a component value string for comparison."""
        if not value:
            return ""
        normalized = value.upper().strip()
        normalized = normalized.rstrip("*")
        normalized = re.sub(r"\s+", "", normalized)
        return normalized

    # ── Candidate filtering (v0.8.2-style prefix filter) ────────────

    @staticmethod
    def _filter_by_category(
        categories: list[str],
        candidates: list[ComponentDef],
    ) -> list[ComponentDef]:
        """Filter candidates whose part_name contains any category keyword.

        Candidates are sorted by category priority.
        """
        if not categories:
            return candidates

        cat_priority: dict[str, int] = {
            cat.lower(): idx for idx, cat in enumerate(categories)
        }
        matched_with_priority: list[tuple[int, ComponentDef]] = []

        for candidate in candidates:
            part_lower: str = candidate.part_name.lower()
            best_priority: int = len(categories)
            for idx, cat in enumerate(categories):
                if cat.lower() in part_lower and idx < best_priority:
                    best_priority = idx
            if best_priority < len(categories):
                matched_with_priority.append((best_priority, candidate))

        if matched_with_priority:
            matched_with_priority.sort(key=lambda x: x[0])
            return [c for _, c in matched_with_priority]

        return []

    # ── Core matching interface ──────────────────────────────────────

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Match source against candidates using refdes-prefix-based fallback.

        v2.0: Simplified — candidates are already type-filtered.
        Uses three-level matching within the pool.
        """
        if not candidates:
            logger.debug("Fallback: no candidates for %s", source.library_id)
            return MatchResult.no_match(source.library_id)

        # ── Step 1: extract refdes prefix ─────────────────────────
        refdes_or_id: str = (
            getattr(source, "refdes", "")
            or source.part_name
            or source.library_id
        )
        prefix: str = self.extract_refdes_prefix(refdes_or_id)

        if not prefix:
            if refdes_or_id != source.part_name and source.part_name:
                prefix = self.extract_refdes_prefix(source.part_name)

        if not prefix:
            logger.debug("Fallback: cannot extract prefix from '%s'", refdes_or_id)
            return MatchResult.no_match(source.library_id)

        # ── Step 2: extract footprint size & normalise value ──────
        fp_size: str = self.extract_pkg_size(source.footprint)
        norm_value: str = self.normalize_value(source.value)

        # ── Step 3: three-level matching within candidates ────────
        best_candidate: ComponentDef | None = None
        best_confidence: float = 0.0
        best_tier: str = ""

        for candidate in candidates:
            confidence, tier = self._score_candidate_simple(
                candidate, fp_size, norm_value
            )
            if confidence > best_confidence:
                best_confidence = confidence
                best_candidate = candidate
                best_tier = tier
                if best_confidence >= self.CONF_EXACT:
                    break
            # Tiebreaker: prefer footprint-size in part_name
            elif (confidence == best_confidence
                  and confidence > 0
                  and fp_size
                  and best_candidate is not None):
                def _fp_affinity(comp: ComponentDef) -> int:
                    score = 0
                    if fp_size in comp.part_name:
                        score += 2
                    if fp_size in comp.library_id:
                        score += 1
                    return score

                if _fp_affinity(candidate) > _fp_affinity(best_candidate):
                    best_candidate = candidate
                    best_tier = tier

        if best_candidate is None:
            logger.debug("Fallback: no match for prefix '%s'", prefix)
            return MatchResult.no_match(source.library_id)

        # ── Step 4: unity boost for single-candidate pools ────────
        if len(candidates) == 1:
            if best_confidence == self.CONF_PREFIX:
                best_confidence = min(best_confidence + 0.15, 0.65)
                best_tier = "prefix_unity"
            elif best_confidence >= 0.50:
                best_confidence = min(best_confidence + 0.10, 0.75)

        # ── Step 5: value hint boost ──────────────────────────────
        value_boost: float = 0.0
        src_value_upper: str = (source.value or "").upper().strip("*")
        for val_key in self.VALUE_CATEGORY_HINTS:
            if val_key in src_value_upper:
                value_boost = max(value_boost, 0.20)
                break

        if value_boost > 0 and best_confidence >= self.CONF_PREFIX:
            best_confidence = min(best_confidence + value_boost, 0.85)
            best_tier = f"{best_tier}_value_hint" if best_tier else "value_hint"

        # ── Step 6: select primitive ──────────────────────────────
        self._select_primitive(best_candidate, source)

        # ── Step 7: build result ──────────────────────────────────
        pin_mapping: dict[str, str] = self._build_pin_mapping(
            source, best_candidate
        )

        logger.info(
            "Fallback: %s → %s (prefix=%s, tier=%s, conf=%.2f)",
            source.library_id, best_candidate.library_id,
            prefix, best_tier, best_confidence,
        )

        return MatchResult(
            confidence=best_confidence,
            strategy=MatchStrategy.FALLBACK,
            source_library_id=source.library_id,
            target_library_id=best_candidate.library_id,
            pin_mapping=pin_mapping,
            warnings=[f"Fallback tier: {best_tier}"],
        )

    def _score_candidate_simple(
        self,
        candidate: ComponentDef,
        fp_size: str,
        norm_value: str,
    ) -> tuple[float, str]:
        """Score a candidate with three-level matching (v2.0 simplified).

        Does NOT do cross-type scoring — the candidate pool is already
        type-filtered by CandidatePoolBuilder.

        Args:
            candidate: HDL candidate.
            fp_size: Source footprint package size.
            norm_value: Source normalised value.

        Returns:
            Tuple of (confidence, tier_name).
        """
        candidate_value: str = self.normalize_value(candidate.value)
        candidate_fp_size: str = self.extract_pkg_size(candidate.footprint)

        # Tier 1 — exact: footprint size + value both match
        if fp_size and candidate_fp_size:
            fp_matches: bool = (
                fp_size == candidate_fp_size
                or candidate.part_name.replace("_", "").replace("-", "").endswith(fp_size)
            )
            value_matches: bool = (norm_value and candidate_value == norm_value)
            if fp_matches and value_matches:
                return (self.CONF_EXACT, "exact")
            if fp_matches:
                return (self.CONF_SIZE, "size")

        # Tier 2 — size only
        if fp_size and candidate_fp_size and fp_size == candidate_fp_size:
            return (self.CONF_SIZE, "size")

        # Tier 3 — prefix (zero-value boost)
        if norm_value == "0":
            return (self.CONF_PREFIX + 0.05, "prefix_zero")
        return (self.CONF_PREFIX, "prefix")

    # ── Primitive selection ──────────────────────────────────────────

    def _select_primitive(
        self,
        candidate: ComponentDef,
        source: ComponentDef,
    ) -> None:
        """Select the best primitive for the fallback-matched candidate."""
        all_prims: list[dict] = (
            candidate.extra_data.get("all_primitives", [])
            if hasattr(candidate, "extra_data") else []
        )
        ptf_rows: list[dict] = (
            candidate.extra_data.get("ptf_rows", [])
            if hasattr(candidate, "extra_data") else []
        )
        if not all_prims or not ptf_rows:
            return

        _norm_val: str = self.normalize_value(source.value)
        if not _norm_val:
            # No value to match — pick first primitive
            candidate.extra_data["selected_primitive_body"] = all_prims[0].get(
                "part_name", ""
            )
            return

        matching_ptf_row: dict | None = None
        for row in ptf_rows:
            row_val: str = self.normalize_value(row.get("value", ""))
            if row_val == _norm_val:
                matching_ptf_row = row
                break

        if matching_ptf_row is not None:
            pkg_type: str = matching_ptf_row.get("package_type", "")
            jedec_type: str = matching_ptf_row.get("jedec_type", "")
            size_code: str = self.extract_pkg_size(pkg_type)
            if not size_code:
                size_code = self.extract_pkg_size(jedec_type)

            if size_code:
                for prim in all_prims:
                    pn: str = prim.get("part_name", "")
                    if size_code in pn:
                        candidate.extra_data["selected_primitive_body"] = pn
                        return

        # Fallback
        candidate.extra_data["selected_primitive_body"] = all_prims[0].get(
            "part_name", ""
        )

    def confidence_threshold(self) -> float:
        """Fallback matching threshold from config."""
        return config.matching.fallback_threshold
