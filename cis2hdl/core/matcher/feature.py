"""FeatureExtractMatcher — regex-based component feature extraction.

Extracts structured features (resistance/capacitance values, footprint,
pin count) from component names/values and compares them for matching.
Runs at priority 3 (after ExactMatcher and FuzzyNameMatcher).
"""

from __future__ import annotations

import logging
import re

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.exceptions import CIS2HDLMatchError
from cis2hdl.core.config import config
from cis2hdl.utils.naming import normalize_value

logger = logging.getLogger(__name__)


class FeatureExtractMatcher(MatcherBase):
    """Feature-based component matcher using regex extraction.

    Extracts structured features from part_name and value fields:
    - Resistance values (e.g. "10K", "4.7K", "100Ω")
    - Capacitance values (e.g. "0.1uF", "10pF", "100nF")
    - Footprint string
    - Pin count

    Features are compared via _feature_similarity() and the best match
    above the confidence threshold is returned.
    """

    MATCHER_NAME: str = "feature"
    MATCHER_PRIORITY: int = 3

    # ------------------------------------------------------------------
    #  Regex patterns for value extraction
    # ------------------------------------------------------------------

    RES_PATTERN: re.Pattern = re.compile(
        r"(\d+\.?\d*)\s*([KM]?)\s*Ω?",
        re.IGNORECASE,
    )
    """Extract resistance: group(1)=numeric, group(2)=multiplier (K/M)."""

    CAP_PATTERN: re.Pattern = re.compile(
        r"(\d+\.?\d*)\s*([pnum]?)\s*F",
        re.IGNORECASE,
    )
    """Extract capacitance: group(1)=numeric, group(2)=unit prefix (p/n/u/m)."""

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Match source against candidates by comparing extracted features.

        Args:
            source: The CIS component to match.
            candidates: HDL candidate components.

        Returns:
            MatchResult of best feature match above threshold, or no_match.
        """
        if not candidates:
            logger.debug("Feature: no candidates for %s", source.library_id)
            return MatchResult.no_match(source.library_id)

        src_features: dict = self._extract(source)

        # P0-2: When source has no electrical features (type is empty),
        # return no_match immediately to avoid random matches on
        # signal names, GPIO pins, pure numbers, and other non-electrical
        # components that happen to share pin counts.
        if not src_features.get("type"):
            logger.debug(
                "Feature: no electrical features for '%s', skipping",
                source.library_id,
            )
            return MatchResult.no_match(source.library_id)

        best_match: ComponentDef | None = None
        best_sim: float = 0.0

        for candidate in candidates:
            cand_features: dict = self._extract(candidate)
            sim: float = self._feature_similarity(src_features, cand_features)

            # Boost confidence when normalized values match
            src_norm: str = normalize_value(source.value)
            cand_norm: str = normalize_value(candidate.value)
            if src_norm and cand_norm and src_norm == cand_norm:
                sim += 0.25  # Significant boost for exact value match
                sim = min(sim, 1.0)  # Cap at 1.0

            if sim > best_sim:
                best_sim = sim
                best_match = candidate

        if best_match is None or best_sim < self.confidence_threshold():
            logger.debug(
                "Feature: no match above threshold for %s (best_sim=%.2f)",
                source.library_id,
                best_sim,
            )
            return MatchResult.no_match(source.library_id)

        pin_mapping: dict[str, str] = self._build_pin_mapping(
            source, best_match
        )

        logger.debug(
            "Feature match: %s -> %s (sim=%.2f)",
            source.library_id,
            best_match.library_id,
            best_sim,
        )

        return MatchResult(
            confidence=best_sim,
            strategy=MatchStrategy.FEATURE,
            source_library_id=source.library_id,
            target_library_id=best_match.library_id,
            pin_mapping=pin_mapping,
        )

    def confidence_threshold(self) -> float:
        """Feature extraction threshold from config."""
        return config.matching.feature_threshold

    # ------------------------------------------------------------------
    #  Feature extraction
    # ------------------------------------------------------------------

    def _extract(self, comp: ComponentDef) -> dict:
        """Extract structured features from a component definition.

        Searches both part_name and value fields for electrical values
        (resistance, capacitance).  Also records footprint and pin count.

        Args:
            comp: A ComponentDef to extract features from.

        Returns:
            Dict with keys: type, value_num, value_mult, footprint, pin_count.
        """
        features: dict = {
            "type": "",
            "value_num": "",
            "value_mult": "",
            "footprint": comp.footprint,
            "pin_count": comp.pin_count,
        }

        # Search text: value field is the canonical source for electrical
        # values (resistance, capacitance, inductance).  Part name is
        # used as a fallback only when value is explicitly set — this
        # prevents false positives from signal names, GPIO labels, and
        # internal IDs that happen to contain digits (e.g. "HSI0_CLK_2G"
        # matching "0" as a resistor, "3V3_PER" matching "3V3" as resistor).
        search_texts: list[str] = []
        if comp.value:
            search_texts.append(comp.value)
            # Part name provides additional context (e.g. "INDUCTOR_0402")
            search_texts.append(comp.part_name)
        # When value is empty, do NOT search part_name — empty features
        # trigger P0-2 early-return to avoid random matches.

        combined: str = " | ".join(search_texts) if search_texts else ""

        # Try resistance pattern
        res_m: re.Match | None = self.RES_PATTERN.search(combined)
        if res_m:
            features["type"] = "resistor"
            features["value_num"] = res_m.group(1)
            features["value_mult"] = res_m.group(2).upper() if res_m.group(2) else ""
            return features

        # Try capacitance pattern
        cap_m: re.Match | None = self.CAP_PATTERN.search(combined)
        if cap_m:
            features["type"] = "capacitor"
            features["value_num"] = cap_m.group(1)
            features["value_mult"] = cap_m.group(2).lower() if cap_m.group(2) else ""
            return features

        # Try to detect inductor
        if re.search(r"\d+\.?\d*\s*[uµnm]?H", combined, re.IGNORECASE):
            features["type"] = "inductor"
            return features

        # Try to detect connector
        if re.search(r"conn|header|socket|jack|plug", combined, re.IGNORECASE):
            features["type"] = "connector"
            return features

        return features

    # ------------------------------------------------------------------
    #  Feature similarity
    # ------------------------------------------------------------------

    def _feature_similarity(self, a: dict, b: dict) -> float:
        """Compute similarity score between two feature dictionaries.

        Scoring weights:
          - type match:    0.40
          - value match:   0.30
          - footprint:     0.15
          - pin_count:     0.15

        Args:
            a: Features from source component.
            b: Features from candidate component.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        score: float = 0.0

        # --- Type match (0.40) ---
        type_a: str = a.get("type", "")
        type_b: str = b.get("type", "")
        if type_a and type_b and type_a == type_b:
            score += 0.40

        # --- Value match (0.30) ---
        num_a: str = a.get("value_num", "")
        num_b: str = b.get("value_num", "")
        mult_a: str = a.get("value_mult", "")
        mult_b: str = b.get("value_mult", "")
        if num_a and num_b:
            if num_a == num_b and mult_a.upper() == mult_b.upper():
                score += 0.30
            elif num_a == num_b:
                score += 0.20  # Same number, different multiplier
            else:
                # Attempt numeric proximity (within 20%)
                try:
                    fa: float = float(num_a)
                    fb: float = float(num_b)
                    if fa > 0 and fb > 0:
                        ratio: float = min(fa, fb) / max(fa, fb)
                        if ratio >= 0.8:
                            score += 0.15
                except (ValueError, ZeroDivisionError):
                    pass

        # --- Footprint match (0.15) ---
        fp_a: str = a.get("footprint", "")
        fp_b: str = b.get("footprint", "")
        if fp_a and fp_b and fp_a == fp_b:
            score += 0.15

        # --- Pin count match (0.15) ---
        pc_a: int = a.get("pin_count", 0)
        pc_b: int = b.get("pin_count", 0)
        if pc_a and pc_b and pc_a == pc_b:
            score += 0.15

        return score

