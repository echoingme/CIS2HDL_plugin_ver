"""ValueMatcher — electrical value matching via part.ptf data.

Compares normalised electrical values (resistance, capacitance, inductance)
from the CIS CrossRef CSV against HDL part.ptf table rows.  Runs at
priority 3, after FeatureExtractMatcher and before FallbackMatcher.

Matching algorithm:
    1. Extract the source (CIS) refdes prefix + value from CrossRef CSV
       (e.g. ``"C"`` + ``"0.2P"`` → capacitance 0.2 pF).
    2. For each HDL candidate, search ``extra_data["ptf_rows"]`` for a row
       whose VALUE matches the normalised CIS value.
    3. If exactly one candidate matches → confidence=1.0, strategy=VALUE.
    4. If no match → no_match.

Also exports ``extract_pkg_size()`` as a standalone utility for extracting
package size codes from footprint strings — used by FallbackMatcher and
other matchers for size-based comparison.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.config import config
from cis2hdl.utils.naming import normalize_value

logger = logging.getLogger(__name__)


# ── Compiled regex patterns for package size extraction ──────────────────

_RE_PKG_SIZE = re.compile(r"(\d{4})")
_RE_BGA = re.compile(r"BGA\s*(\d+)", re.IGNORECASE)
_RE_SOT_QFN = re.compile(r"\b(SOT|QFN|MLF|TO-?\d+)", re.IGNORECASE)


def extract_pkg_size(footprint_str: str) -> str:
    """Extract package size code from a footprint string.

    Used across matchers to normalise footprint sizes for comparison.

    Args:
        footprint_str: Footprint string (e.g. "HSC0402-HDTB", "SR0402",
                       "BGA96-32-1609W", "SOT23-5").

    Returns:
        Package size code string:
        - BGA → "BGA96" (BGA + number)
        - 4-digit sizes → "0402", "0603" (imperial metric)
        - IC packages → "SOT", "QFN", "MLF", "TO-xxx"
        - None matched → first 10 characters of input
        - Empty input → ""

    Examples:
        >>> extract_pkg_size("HSC0402-HDTB")
        "0402"
        >>> extract_pkg_size("SR0402")
        "0402"
        >>> extract_pkg_size("BGA96-32-1609W")
        "BGA96"
        >>> extract_pkg_size("SOT23-5")
        "SOT"
        >>> extract_pkg_size("")
        ""
    """
    if not footprint_str:
        return ""

    bga = _RE_BGA.search(footprint_str)
    if bga:
        return f"BGA{bga.group(1)}"

    size = _RE_PKG_SIZE.search(footprint_str)
    if size:
        return size.group(1)

    other = _RE_SOT_QFN.search(footprint_str)
    if other:
        return other.group(1)

    return footprint_str[:10]


class ValueMatcher(MatcherBase):
    """Electrical value matcher using part.ptf table data.

    Compares normalised CIS values against HDL part.ptf VALUE columns
    for precise electrical matching.  Designed to catch components where
    name-based matching fails but electrical values are known.

    MATCHER_PRIORITY = 3 (after FeatureExtractMatcher, before FallbackMatcher).
    """

    MATCHER_NAME: ClassVar[str] = "value"
    MATCHER_PRIORITY: ClassVar[int] = 3

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Match source against candidates by comparing normalised values.

        Args:
            source: The CIS component to match.
            candidates: HDL candidate components.

        Returns:
            MatchResult with confidence=1.0 if a unique value match is
            found, else no_match.
        """
        if not candidates:
            logger.debug("Value: no candidates for %s", source.library_id)
            return MatchResult.no_match(source.library_id)

        src_value: str = normalize_value(source.value)
        if not src_value:
            logger.debug(
                "Value: source '%s' has no normalisable value",
                source.library_id,
            )
            return MatchResult.no_match(source.library_id)

        matched_candidates: list[ComponentDef] = []

        for candidate in candidates:
            # Search candidate's ptf_rows (from part.ptf) for VALUE match
            ptf_rows: list[dict] = candidate.extra_data.get("ptf_rows", [])
            if not ptf_rows:
                # Fall back to candidate.value field
                cand_value: str = normalize_value(candidate.value)
                if cand_value and cand_value == src_value:
                    matched_candidates.append(candidate)
                continue

            for row in ptf_rows:
                row_value: str = normalize_value(row.get("value", ""))
                if row_value and row_value == src_value:
                    matched_candidates.append(candidate)
                    logger.debug(
                        "Value: '%s' matched via ptf_rows: '%s' == '%s'",
                        candidate.library_id,
                        row.get("value", ""),
                        source.value,
                    )
                    break

        if not matched_candidates:
            logger.debug(
                "Value: no value match for '%s' (value=%r) in %d candidates",
                source.library_id,
                source.value,
                len(candidates),
            )
            return MatchResult.no_match(source.library_id)

        if len(matched_candidates) == 1:
            best: ComponentDef = matched_candidates[0]
            self._select_primitive_by_value(best, src_value)
            pin_mapping: dict[str, str] = self._build_pin_mapping(source, best)

            # v0.8.1: Only warn when ptf value materially differs from source
            matched_ptf_value = src_value
            for row in best.extra_data.get("ptf_rows", []):
                if normalize_value(row.get("value", "")) == src_value:
                    matched_ptf_value = row.get("value", "")
                    break

            _warnings: list[str] = []
            _src_norm = normalize_value(source.value or "")
            _ptf_norm = normalize_value(matched_ptf_value or "")
            if _src_norm and _ptf_norm and _src_norm != _ptf_norm:
                _warnings.append(
                    f"Value mismatch: '{source.value}' → '{matched_ptf_value}' (ptf)"
                )
            else:
                logger.debug(
                    "Value match OK: '%s' == '%s' (ptf)",
                    source.value, matched_ptf_value,
                )

            logger.info(
                "Value match: %s → %s (value=%r)",
                source.library_id,
                best.library_id,
                source.value,
            )
            return MatchResult(
                confidence=1.0,
                strategy=MatchStrategy.VALUE,
                source_library_id=source.library_id,
                target_library_id=best.library_id,
                pin_mapping=pin_mapping,
                warnings=_warnings,
            )

        # Multiple matches — ambiguous, return first with reduced confidence
        best = matched_candidates[0]
        # v0.7.0: Select precise primitive even in ambiguous case
        self._select_primitive_by_value(best, src_value)
        pin_mapping: dict[str, str] = self._build_pin_mapping(source, best)
        conf = 1.0 / len(matched_candidates)

        if conf < self.confidence_threshold():
            return MatchResult.no_match(source.library_id)

        logger.info(
            "Value match (ambiguous, %d candidates): %s → %s (value=%r, conf=%.2f)",
            len(matched_candidates),
            source.library_id,
            best.library_id,
            source.value,
            conf,
        )
        return MatchResult(
            confidence=conf,
            strategy=MatchStrategy.VALUE,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
            warnings=[
                f"Ambiguous value match: {len(matched_candidates)} candidates "
                f"share value '{source.value}'"
            ],
        )

    def match_typed(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
        type_name: str,
    ) -> MatchResult:
        """Match source against candidates WITHIN a specific type.

        v2.0: Forces all candidates to belong to *type_name* via
        category/phys_des_prefix/part_name triple check.  Candidates
        that don't match the type are excluded BEFORE value comparison.

        This prevents cross-type value collisions (e.g. "0" matching
        both 0Ω resistor and 0-value diode).

        Args:
            source: The CIS component to match.
            candidates: HDL candidate components (may be cross-type).
            type_name: Required type name (e.g. "capacitor", "diode").

        Returns:
            MatchResult if a unique value match is found within the type,
            else no_match.
        """
        if not candidates:
            return MatchResult.no_match(source.library_id)

        # ── Filter candidates to those matching the type ──────────
        type_lower: str = type_name.lower()
        typed_candidates: list[ComponentDef] = []

        for candidate in candidates:
            if self._matches_type(candidate, type_lower):
                typed_candidates.append(candidate)

        if not typed_candidates:
            logger.debug(
                "Value.match_typed: no candidates match type '%s' for %s",
                type_name, source.library_id,
            )
            return MatchResult.no_match(source.library_id)

        # ── Delegate to standard value matching on filtered pool ──
        return self.match(source, typed_candidates)

    @staticmethod
    def _matches_type(candidate: ComponentDef, type_name: str) -> bool:
        """Check if a candidate belongs to a given type.

        Uses three strategies (OR logic):
            1. candidate.category equals type_name
            2. candidate.phys_des_prefix maps to this type
            3. candidate.part_name contains type_name

        Args:
            candidate: HDL candidate ComponentDef.
            type_name: Expected type name in lowercase.

        Returns:
            True if the candidate matches the type.
        """
        type_lower: str = type_name.lower()

        # Check 1: category
        category: str = (getattr(candidate, "category", "") or "").lower()
        if category == type_lower:
            return True

        # Check 2: phys_des_prefix
        phys_prefix: str = (getattr(candidate, "phys_des_prefix", "") or "").lower()
        # Common phys_des_prefix → type mappings
        _PREFIX_MAP: dict[str, str] = {
            "capacitor": "capacitor", "cap": "capacitor",
            "resistor": "resistor", "res": "resistor",
            "inductor": "inductor", "ind": "inductor",
            "diode": "diode", "zener": "zener",
            "led": "led", "ic": "IC",
            "connector": "connector", "con": "connector",
            "crystal": "crystal", "xtal": "crystal",
            "oscillator": "oscillator",
            "transformer": "transformer",
            "switch": "switch", "fuse": "fuse",
            "relay": "relay",
            "test_point": "test_point", "mark": "mark",
            "ferrite_bead": "ferrite_bead", "ferrite": "ferrite_bead",
            "transistor": "transistor", "mosfet": "mosfet",
            "voltage_regulator": "voltage_regulator",
        }
        if _PREFIX_MAP.get(phys_prefix, "") == type_lower:
            return True

        # Check 3: part_name contains type_name
        part_name: str = (getattr(candidate, "part_name", "") or "").lower()
        if type_lower in part_name:
            return True

        return False

    def confidence_threshold(self) -> float:
        """Value matching threshold — 0.90 (high confidence required)."""
        return 0.90

    # ------------------------------------------------------------------
    #  Primitive selection from ptf value match
    # ------------------------------------------------------------------

    @staticmethod
    def _select_primitive_by_value(
        candidate: ComponentDef,
        src_value_norm: str,
    ) -> None:
        """Select the precise primitive for a value-matched candidate.

        When ValueMatcher matches a directory-level ComponentDef (e.g.
        "capacitor") via ptf_rows value matching, this method finds the
        exact primitive (e.g. "CAPACITOR_0402") whose package_type size
        code corresponds to the matched ptf row.

        The selected primitive's part_name is stored in
        ``candidate.extra_data["selected_primitive_body"]`` for
        downstream use by csa_writer.

        Args:
            candidate: The matched HDL ComponentDef (directory level).
            src_value_norm: Normalised source value for ptf row lookup.
        """
        all_prims: list[dict] = candidate.extra_data.get("all_primitives", [])
        ptf_rows: list[dict] = candidate.extra_data.get("ptf_rows", [])
        if not all_prims or not ptf_rows:
            return

        # Find the ptf row that matches the source value
        matching_row: dict | None = None
        for row in ptf_rows:
            row_val: str = normalize_value(row.get("value", ""))
            if row_val == src_value_norm:
                matching_row = row
                break

        if matching_row is None:
            return

        pkg_type: str = matching_row.get("package_type", "")
        jedec_type: str = matching_row.get("jedec_type", "")

        # Extract size code (e.g. "0402" from "C0402" or "CAP_0402")
        size_code: str = _extract_size(pkg_type) or _extract_size(jedec_type)
        if not size_code:
            return

        # Find primitive whose part_name contains the size code
        for prim in all_prims:
            pn: str = prim.get("part_name", "")
            if size_code in pn:
                candidate.extra_data["selected_primitive_body"] = pn
                logger.debug(
                    "ValueMatcher primitive: value='%s' → pkg='%s' "
                    "→ primitive='%s'",
                    src_value_norm, pkg_type, pn,
                )
                return


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

# Matches 4-digit imperial package size codes (0402, 0603, 0805, 1206, ...)
_RE_SIZE = re.compile(r"(\d{4})")


def _extract_size(text: str) -> str:
    """Extract a 4-digit package size from a string like 'C0402' or 'CAP_0402'.

    Args:
        text: Package type or jedec type string.

    Returns:
        The 4-digit size code, or '' if none found.
    """
    if not text:
        return ""
    m = _RE_SIZE.search(text)
    return m.group(1) if m else ""
