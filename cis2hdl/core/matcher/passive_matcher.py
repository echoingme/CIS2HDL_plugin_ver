"""Phase 2A: PassiveMatcher — deterministic rule-based matching for passives.

Five-level cascading match for C/R/L/D/FB/LED components:

    Level 1: value + size exact match         → PASSIVE_EXACT       (conf=1.00)
             (multi-candidate → JEDEC tiebreak → PASSIVE_EXACT_MULTI  conf=0.95)
    Level 2: value exact, size unknown         → PASSIVE_VALUE_ONLY  (conf=0.80)
    Level 3: value exact, size approximate     → PASSIVE_VALUE_NEAR  (conf=0.70)
    Level 4: size exact, value approximate     → PASSIVE_SIZE_ONLY   (conf=0.60)
    Level 5: prefix-only fallback              → PASSIVE_PREFIX_ONLY (conf=0.40)

Key design principle: Passive components MUST use deterministic rules,
not weighted scoring.  Value and size are boolean constraints — there
is no "partial value match" that other dimensions can compensate for.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.matcher.value_matcher import extract_pkg_size
from cis2hdl.utils.naming import normalize_value

logger = logging.getLogger(__name__)


class PassiveMatcher(MatcherBase):
    """Deterministic rule-based matcher for passive components.

    Does NOT use weighted scoring.  Instead, checks boolean constraints
    (value match? size match?) in five cascading levels.  The first
    level that produces a match wins.

    MATCHER_PRIORITY = 1 (Phase 2A, before ActiveMatcher).
    """

    MATCHER_NAME: ClassVar[str] = "passive"
    MATCHER_PRIORITY: ClassVar[int] = 1

    # Confidence constants per level
    CONF_EXACT: ClassVar[float] = 1.0
    CONF_EXACT_MULTI: ClassVar[float] = 0.95
    CONF_VALUE_ONLY: ClassVar[float] = 0.80
    CONF_VALUE_NEAR: ClassVar[float] = 0.70
    CONF_SIZE_ONLY: ClassVar[float] = 0.60
    CONF_PREFIX_ONLY: ClassVar[float] = 0.40

    # Default package size when CIS footprint is empty
    DEFAULT_PKG_SIZE: ClassVar[str] = "0603"

    # ── Core matching interface ──────────────────────────────────────

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
        src_type: str = "",
    ) -> MatchResult:
        """Match a passive CIS component against typed HDL candidates.

        Args:
            source: CIS source component.
            candidates: HDL candidates (pre-filtered to same type).
            src_type: Type name (e.g. "capacitor", "resistor") — used
                      for prefix-fallback level.

        Returns:
            MatchResult with PASSIVE_* strategy, or no_match if no
            candidate exists.
        """
        if not candidates:
            logger.debug(
                "PassiveMatcher: no candidates for %s (type=%s)",
                source.library_id, src_type,
            )
            return MatchResult.no_match(source.library_id)

        # ── Level 1: value + size exact ──────────────────────────
        result = self._match_value_size_exact(source, candidates)
        if result is not None:
            result.extra_data["_source_value"] = source.value or ""
            self._enrich_result(result, candidates)
            return result

        # ── Level 2: value exact, size unknown ───────────────────
        result = self._match_value_only(source, candidates)
        if result is not None:
            result.extra_data["_source_value"] = source.value or ""
            self._enrich_result(result, candidates)
            return result

        # ── Level 3: value exact, size near ──────────────────────
        result = self._match_value_near_size(source, candidates)
        if result is not None:
            result.extra_data["_source_value"] = source.value or ""
            self._enrich_result(result, candidates)
            return result

        # ── Level 4: size exact, value approximate ───────────────
        result = self._match_size_only(source, candidates)
        if result is not None:
            result.extra_data["_source_value"] = source.value or ""
            self._enrich_result(result, candidates)
            return result

        # ── Level 5: prefix-only fallback ────────────────────────
        result = self._match_prefix_fallback(source, candidates, src_type)
        if result is not None:
            result.extra_data["_source_value"] = source.value or ""
            self._enrich_result(result, candidates)
            return result

        logger.debug(
            "PassiveMatcher: all 5 levels failed for %s (type=%s, %d candidates)",
            source.library_id, src_type, len(candidates),
        )
        return MatchResult.no_match(source.library_id)

    # ── Level 1: value + size exact ──────────────────────────────────

    def _match_value_size_exact(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult | None:
        """Search for candidates with BOTH exact value AND exact size match.

        Returns:
            PASSIVE_EXACT if exactly one candidate matches.
            PASSIVE_EXACT_MULTI if multiple match (JEDEC tiebreak).
            None if no value+size exact match.
        """
        src_value_norm: str = normalize_value(source.value or "")
        src_fp_size: str = extract_pkg_size(source.footprint or "")
        # v2.0: When CIS footprint is empty OR invalid (category name), use CIS JEDEC
        _is_valid_fp: bool = src_fp_size and len(src_fp_size) >= 4 and any(c.isdigit() for c in src_fp_size)
        if not _is_valid_fp and hasattr(source, "extra_data") and source.extra_data:
            jedec_str = source.extra_data.get("jedec_type", "")
            if jedec_str:
                src_fp_size = extract_pkg_size(jedec_str)

        if not src_value_norm:
            logger.debug(
                "PassiveMatcher L1: no normalisable value for %s",
                source.library_id,
            )
            return None

        matched: list[tuple[ComponentDef, str | None, dict]] = []

        for candidate in candidates:
            # Check value in ptf_rows
            ptf_rows: list[dict] = (
                candidate.extra_data.get("ptf_rows", [])
                if hasattr(candidate, "extra_data") else []
            )
            for row in ptf_rows:
                row_val: str = normalize_value(row.get("value", ""))
                if row_val == src_value_norm:
                    pkg_type: str = row.get("package_type", "")
                    jedec_type: str = row.get("jedec_type", "")
                    row_size: str = extract_pkg_size(pkg_type) or extract_pkg_size(jedec_type)

                    # Check size match — only match when BOTH source and
                    # candidate have footprint sizes, AND they match.
                    # Empty CIS footprint → fall through to L2 _match_value_only().
                    if src_fp_size and row_size and src_fp_size == row_size:
                        matched.append((candidate, row_size, row))
                        break

        if not matched:
            logger.debug(
                "PassiveMatcher L1: no value+size exact match for %s "
                "(value=%r, size=%r)",
                source.library_id, src_value_norm, src_fp_size or "<empty>",
            )
            return None

        # Unique match
        if len(matched) == 1:
            best, size_code, matched_row = matched[0]
            self._select_primitive_by_size(best, src_value_norm, size_code)
            pin_mapping: dict[str, str] = self._build_pin_mapping(source, best)
            logger.info(
                "PassiveMatcher L1 EXACT: %s → %s (value=%r, size=%s)",
                source.library_id, best.library_id, src_value_norm, size_code,
            )
            result = MatchResult(
                confidence=self.CONF_EXACT,
                strategy=MatchStrategy.PASSIVE_EXACT,
                source_library_id=source.library_id,
                target_library_id=best.library_id,
                pin_mapping=pin_mapping,
                phase2_strategy_detail=f"value✅ footprint✅",
            )
            result.extra_data["_matched_row"] = matched_row
            result.extra_data["_matched_size"] = size_code
            return result

        # Multiple candidates — JEDEC tiebreak
        best, size_code, matched_row = self._jedec_tiebreak(source, matched)
        self._select_primitive_by_size(best, src_value_norm, size_code)
        pin_mapping = self._build_pin_mapping(source, best)
        logger.info(
            "PassiveMatcher L1 EXACT_MULTI: %s → %s (%d candidates, JEDEC tiebreak)",
            source.library_id, best.library_id, len(matched),
        )
        result = MatchResult(
            confidence=self.CONF_EXACT_MULTI,
            strategy=MatchStrategy.PASSIVE_EXACT_MULTI,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
            phase2_strategy_detail=f"value✅ footprint✅ (JEDEC tiebreak, {len(matched)} candidates)",
            warnings=[
                f"Multiple value+size matches ({len(matched)}). "
                f"Selected via JEDEC_TYPE tiebreak."
            ],
        )
        result.extra_data["_matched_row"] = matched_row
        result.extra_data["_matched_size"] = size_code
        return result

    # ── Level 2: value exact, size unknown ───────────────────────────

    def _match_value_only(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult | None:
        """Search for candidates with exact value match when CIS footprint is empty.

        Returns:
            PASSIVE_VALUE_ONLY if a match is found.
            None otherwise.
        """
        src_value_norm: str = normalize_value(source.value or "")
        src_fp: str = (source.footprint or "").strip()

        # Check if CIS JEDEC provides a valid package size as fallback footprint
        src_fp_size: str = extract_pkg_size(src_fp)
        _is_valid_fp: bool = (
            src_fp_size and len(src_fp_size) >= 4
            and any(c.isdigit() for c in src_fp_size)
        )
        if not _is_valid_fp and hasattr(source, "extra_data"):
            jedec_str = source.extra_data.get("jedec_type", "")
            if jedec_str:
                jedec_size = extract_pkg_size(jedec_str)
                if jedec_size and any(c.isdigit() for c in jedec_size) and len(jedec_size) >= 4:
                    src_fp_size = jedec_size  # Use JEDEC as real size
                    _is_valid_fp = True

        # Only trigger when CIS footprint is empty or invalid (no real size).
        # Skip if JEDEC provides a valid size — let L3 handle comparison.
        if _is_valid_fp:
            return None  # Has valid size → let L3 handle real comparison

        if not src_value_norm:
            return None

        matched: list[tuple[ComponentDef, str, dict]] = []
        for candidate in candidates:
            ptf_rows: list[dict] = (
                candidate.extra_data.get("ptf_rows", [])
                if hasattr(candidate, "extra_data") else []
            )
            for row in ptf_rows:
                row_val: str = normalize_value(row.get("value", ""))
                if row_val == src_value_norm:
                    pkg_type: str = row.get("package_type", "")
                    jedec_type: str = row.get("jedec_type", "")
                    row_size: str = extract_pkg_size(pkg_type) or extract_pkg_size(jedec_type)
                    matched.append((candidate, row_size or self.DEFAULT_PKG_SIZE, row))
                    break

        if not matched:
            return None

        # Select the one with default size (0603) preference
        best: ComponentDef = matched[0][0]
        best_size: str = matched[0][1]
        best_row: dict = matched[0][2]
        for cand, sz, row in matched:
            if sz == self.DEFAULT_PKG_SIZE:
                best, best_size, best_row = cand, sz, row
                break

        self._select_primitive_by_size(best, src_value_norm, best_size)
        pin_mapping = self._build_pin_mapping(source, best)
        logger.info(
            "PassiveMatcher L2 VALUE_ONLY: %s → %s (value=%r, default size=%s)",
            source.library_id, best.library_id, src_value_norm, best_size,
        )
        result = MatchResult(
            confidence=self.CONF_VALUE_ONLY,
            strategy=MatchStrategy.PASSIVE_VALUE_ONLY,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
            phase2_strategy_detail=f"value✅ footprint⚠️(default_{best_size})",
        )
        result.extra_data["_matched_row"] = best_row
        result.extra_data["_matched_size"] = best_size
        return result

    # ── Level 3: value exact, size near ──────────────────────────────

    def _match_value_near_size(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult | None:
        """Search for candidates with exact value but CIS footprint has
        a size that doesn't perfectly match any candidate.

        Returns:
            PASSIVE_VALUE_NEAR if found, None otherwise.
        """
        src_value_norm: str = normalize_value(source.value or "")
        src_fp_size: str = extract_pkg_size(source.footprint or "")
        # v2.0: When CIS footprint is empty OR invalid (category name), use CIS JEDEC
        _is_valid_fp: bool = src_fp_size and len(src_fp_size) >= 4 and any(c.isdigit() for c in src_fp_size)
        if not _is_valid_fp and hasattr(source, "extra_data") and source.extra_data:
            jedec_str = source.extra_data.get("jedec_type", "")
            if jedec_str:
                src_fp_size = extract_pkg_size(jedec_str)

        # Only trigger when we have both value and footprint size
        if not src_value_norm or not src_fp_size:
            return None

        matched: list[tuple[ComponentDef, str, dict]] = []
        for candidate in candidates:
            ptf_rows: list[dict] = (
                candidate.extra_data.get("ptf_rows", [])
                if hasattr(candidate, "extra_data") else []
            )
            for row in ptf_rows:
                row_val: str = normalize_value(row.get("value", ""))
                if row_val == src_value_norm:
                    pkg_type: str = row.get("package_type", "")
                    jedec_type: str = row.get("jedec_type", "")
                    row_size: str = extract_pkg_size(pkg_type) or extract_pkg_size(jedec_type)
                    matched.append((candidate, row_size or "", row))
                    break

        if not matched:
            return None

        # Find the candidate with closest size to src_fp_size
        best, best_size, best_row = self._find_closest_size(src_fp_size, matched)
        self._select_primitive_by_size(best, src_value_norm, best_size)
        pin_mapping = self._build_pin_mapping(source, best)
        logger.info(
            "PassiveMatcher L3 VALUE_NEAR: %s → %s (value=%r, src_size=%s→hdl_size=%s)",
            source.library_id, best.library_id, src_value_norm, src_fp_size, best_size,
        )
        result = MatchResult(
            confidence=self.CONF_VALUE_NEAR,
            strategy=MatchStrategy.PASSIVE_VALUE_NEAR,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
            phase2_strategy_detail=f"value✅ footprint⚠️({src_fp_size}→{best_size})",
        )
        result.extra_data["_matched_row"] = best_row
        result.extra_data["_matched_size"] = best_size
        return result

    # ── Level 4: size exact, value approximate ───────────────────────

    def _match_size_only(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult | None:
        """Search for candidates with matching package size when value
        doesn't match or is missing.

        Returns:
            PASSIVE_SIZE_ONLY if found, None otherwise.
        """
        src_fp_size: str = extract_pkg_size(source.footprint or "")

        if not src_fp_size:
            return None

        matched: list[tuple[ComponentDef, str, dict]] = []
        for candidate in candidates:
            ptf_rows: list[dict] = (
                candidate.extra_data.get("ptf_rows", [])
                if hasattr(candidate, "extra_data") else []
            )
            for row in ptf_rows:
                pkg_type: str = row.get("package_type", "")
                jedec_type: str = row.get("jedec_type", "")
                row_size: str = extract_pkg_size(pkg_type) or extract_pkg_size(jedec_type)
                if row_size and row_size == src_fp_size:
                    matched.append((candidate, row_size, row))
                    break

        if not matched:
            return None

        # Pick the first size-matched candidate (most common primitive)
        best, best_size, best_row = matched[0]
        src_value: str = source.value or ""
        src_value_norm: str = normalize_value(src_value)
        self._select_primitive_by_size(best, src_value_norm or "", best_size)
        pin_mapping = self._build_pin_mapping(source, best)
        logger.info(
            "PassiveMatcher L4 SIZE_ONLY: %s → %s (size=%s)",
            source.library_id, best.library_id, best_size,
        )
        result = MatchResult(
            confidence=self.CONF_SIZE_ONLY,
            strategy=MatchStrategy.PASSIVE_SIZE_ONLY,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
            phase2_strategy_detail=f"value⚠️ footprint✅",
        )
        result.extra_data["_matched_row"] = best_row
        result.extra_data["_matched_size"] = best_size
        return result

    # ── Level 5: prefix-only fallback ────────────────────────────────

    def _match_prefix_fallback(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
        src_type: str,
    ) -> MatchResult | None:
        """Last resort: pick the most generic primitive for the type.

        Returns:
            PASSIVE_PREFIX_ONLY if a candidate exists, None otherwise.
        """
        if not candidates:
            return None

        # Prefer the candidate whose part_name is closest to the type name
        best: ComponentDef = candidates[0]
        for c in candidates:
            if src_type.lower() in c.part_name.lower():
                best = c
                break

        # Select default primitive (prefer 0603, fall back to first)
        all_prims: list[dict] = (
            best.extra_data.get("all_primitives", [])
            if hasattr(best, "extra_data") else []
        )
        selected_prim: str = ""
        if all_prims:
            # Prefer 0603 primitive
            for prim in all_prims:
                pn: str = prim.get("part_name", "")
                if "0603" in pn:
                    selected_prim = pn
                    break
            if not selected_prim:
                selected_prim = all_prims[0].get("part_name", "")
            best.extra_data["selected_primitive_body"] = selected_prim

        pin_mapping = self._build_pin_mapping(source, best)
        logger.info(
            "PassiveMatcher L5 PREFIX_ONLY: %s → %s (type=%s)",
            source.library_id, best.library_id, src_type,
        )
        return MatchResult(
            confidence=self.CONF_PREFIX_ONLY,
            strategy=MatchStrategy.PASSIVE_PREFIX_ONLY,
            source_library_id=source.library_id,
            target_library_id=best.library_id,
            pin_mapping=pin_mapping,
            phase2_strategy_detail=f"type_only⚠️({src_type})",
        )

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _jedec_tiebreak(
        source: ComponentDef,
        matched: list[tuple[ComponentDef, str | None, dict]],
    ) -> tuple[ComponentDef, str | None, dict]:
        """Break ties using JEDEC_TYPE comparison.

        Prefers the candidate whose ptf_rows contain a jedec_type
        matching the source's JEDEC info.  If no JEDEC match, returns
        the first candidate.

        Args:
            source: CIS source component.
            matched: List of (candidate, size_code, ptf_row) tuples.

        Returns:
            The best (candidate, size_code, ptf_row) triple.
        """
        if len(matched) == 1:
            return matched[0]

        src_jedec: str = ""
        if hasattr(source, "extra_data") and source.extra_data:
            src_jedec = (source.extra_data.get("jedec_type") or "").upper()

        if src_jedec:
            for cand, sz, _row in matched:
                ptf_rows: list[dict] = (
                    cand.extra_data.get("ptf_rows", [])
                    if hasattr(cand, "extra_data") else []
                )
                for row in ptf_rows:
                    row_jedec: str = (row.get("jedec_type") or "").upper()
                    if row_jedec and row_jedec == src_jedec:
                        return cand, sz, row

        # No JEDEC match — return first
        return matched[0]

    @staticmethod
    def _find_closest_size(
        target_size: str,
        matched: list[tuple[ComponentDef, str, dict]],
    ) -> tuple[ComponentDef, str, dict]:
        """Find the candidate whose size is numerically closest to target.

        Args:
            target_size: Source footprint size code (e.g. "0402").
            matched: List of (candidate, size_code, ptf_row) tuples.

        Returns:
            The (candidate, size_code, ptf_row) with closest size.
        """
        if len(matched) == 1:
            return matched[0]

        def _size_num(s: str) -> int:
            """Convert size code to integer for comparison."""
            digits = "".join(c for c in s if c.isdigit())
            return int(digits) if digits else 0

        target_num: int = _size_num(target_size)

        best: tuple[ComponentDef, str, dict] = matched[0]
        best_diff: int = abs(_size_num(matched[0][1]) - target_num)

        for cand, sz, row in matched[1:]:
            diff: int = abs(_size_num(sz) - target_num)
            if diff < best_diff:
                best_diff = diff
                best = (cand, sz, row)

        return best

    @staticmethod
    def _select_primitive_by_size(
        candidate: ComponentDef,
        src_value_norm: str,
        size_code: str | None,
    ) -> None:
        """Select the precise primitive for a matched candidate.

        When matching at the directory level (e.g. "capacitor"), this
        method finds the exact primitive whose part_name contains the
        size code.

        Args:
            candidate: The matched HDL ComponentDef.
            src_value_norm: Normalised source value (for ptf row lookup).
            size_code: Package size code (e.g. "0402").
        """
        all_prims: list[dict] = (
            candidate.extra_data.get("all_primitives", [])
            if hasattr(candidate, "extra_data") else []
        )
        if not all_prims:
            return

        # Try to find primitive matching the size code
        if size_code:
            for prim in all_prims:
                pn: str = prim.get("part_name", "")
                if size_code in pn:
                    candidate.extra_data["selected_primitive_body"] = pn
                    logger.debug(
                        "PassiveMatcher primitive: size=%s → '%s'",
                        size_code, pn,
                    )
                    return

        # Fallback: try to find via ptf value → package_type → size
        if src_value_norm:
            ptf_rows: list[dict] = (
                candidate.extra_data.get("ptf_rows", [])
                if hasattr(candidate, "extra_data") else []
            )
            for row in ptf_rows:
                row_val: str = normalize_value(row.get("value", ""))
                if row_val == src_value_norm:
                    pkg_type: str = row.get("package_type", "")
                    jedec_type: str = row.get("jedec_type", "")
                    row_size: str = extract_pkg_size(pkg_type) or extract_pkg_size(jedec_type)
                    if row_size:
                        for prim in all_prims:
                            pn2: str = prim.get("part_name", "")
                            if row_size in pn2:
                                candidate.extra_data["selected_primitive_body"] = pn2
                                return

        # Last resort: pick the first primitive
        candidate.extra_data["selected_primitive_body"] = all_prims[0].get(
            "part_name", ""
        )

    # ── Result enrichment for CSV/HTML reporting ─────────────────────

    @staticmethod
    def _enrich_result(
        result: MatchResult,
        candidates: list[ComponentDef],
    ) -> None:
        """Populate extra_data with HDL-side information from matched ptf_row.

        Uses the exact ptf_row recorded by L1–L4 (``extra_data["_matched_row"]``)
        when available, so hdl_value/footprint/jedec/package_type reflect the
        ACTUAL matched variant — not the first value-matching row (A.5 fix).
        Falls back to the first value-matching row when no row was recorded.
        """
        from cis2hdl.utils.naming import normalize_value

        matched_cand: ComponentDef | None = None
        for c in candidates:
            if c.library_id == result.target_library_id:
                matched_cand = c
                break

        if matched_cand is None:
            return

        src_value_norm = normalize_value(
            result.extra_data.get("_source_value", "")
        )

        ptf_rows = (
            matched_cand.extra_data.get("ptf_rows", [])
            if hasattr(matched_cand, "extra_data") else []
        )

        # v2c: Prefer the exact ptf row recorded by the matcher level.
        matched_row = result.extra_data.get("_matched_row")
        if not isinstance(matched_row, dict):
            matched_row = None

        # Fallback: find the specific ptf row that matched by value
        if matched_row is None and src_value_norm and ptf_rows:
            for row in ptf_rows:
                if normalize_value(row.get("value", "")) == src_value_norm:
                    matched_row = row
                    break

        if matched_row is not None:
            result.extra_data["hdl_value"] = matched_row.get("value", "")
            result.extra_data["hdl_footprint"] = (
                matched_row.get("package_type", "")
                or matched_row.get("jedec_type", "")
            )
            result.extra_data["hdl_jedec"] = matched_row.get("jedec_type", "")
            result.extra_data["hdl_package_type"] = matched_row.get("package_type", "")
        else:
            result.extra_data["hdl_value"] = getattr(matched_cand, "value", "") or ""
            result.extra_data["hdl_footprint"] = getattr(matched_cand, "footprint", "") or ""
            hd = ""
            pkg = ""
            for row in ptf_rows:
                if row.get("jedec_type"): hd = row["jedec_type"]
                if row.get("package_type"): pkg = row["package_type"]
                if hd and pkg: break
            result.extra_data["hdl_jedec"] = hd
            result.extra_data["hdl_package_type"] = pkg

        result.extra_data["hdl_category"] = getattr(matched_cand, "category", "") or ""
        result.extra_data["hdl_pin_count"] = getattr(matched_cand, "pin_count", 0) or 0

        sel_prim = matched_cand.extra_data.get("selected_primitive_body", "")
        result.extra_data["selected_primitive"] = sel_prim

    def confidence_threshold(self) -> float:
        """Passive matcher threshold — 0.40 (prefix-only is minimum acceptable)."""
        return 0.40
