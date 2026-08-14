"""Phase 2B: ActiveMatcher — within-type weighted scoring for non-passive components.

Used for IC, connector, crystal, switch, transformer, mark, and other
non-passive component types.  Unlike MultiScorer (removed), this matcher:

1. Only operates within a SINGLE type pool — candidates are pre-filtered
   by CandidatePoolBuilder.
2. Uses 5 dimensions (prefix removed — it's a hard constraint from Phase 1):
   - footprint:  0.30  — package size extracted from footprint
   - value:      0.15  — normalised electrical value
   - jedec:      0.20  — JEDEC_TYPE match
   - pin_count:  0.20  — pin count proximity
   - part_name:  0.15  — substring overlap

3. Runs a matcher chain (Exact → Fuzzy → Feature → Value → Fallback)
   within the type pool, then scores the top results with 5-dim weighting.

4. final_conf = phase1_prior_conf × phase2_within_conf (set by Pipeline).
"""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.matcher.exact import ExactMatcher
from cis2hdl.core.matcher.fallback import FallbackMatcher
from cis2hdl.core.matcher.feature import FeatureExtractMatcher
from cis2hdl.core.matcher.fuzzy import FuzzyNameMatcher
from cis2hdl.core.matcher.match_config import MatchConfig
from cis2hdl.core.matcher.value_matcher import ValueMatcher, extract_pkg_size
from cis2hdl.utils.naming import normalize_value

logger = logging.getLogger(__name__)


def _is_placeholder_name(part_name: str, comp: ComponentDef) -> bool:
    """Whether a part_name is a generic refdes placeholder (v2c).

    Catalog-derived CIS components often carry ``part_name == library_id``
    (e.g. J10 → part_name "J10"), with the real part identity living in the
    VALUE field (e.g. "MJ8-M2").  Such placeholder names carry no matching
    signal, so scoring should fall back to the value string.

    Args:
        part_name: Source part_name string.
        comp: The source ComponentDef (for library_id/refdes comparison).

    Returns:
        True when part_name equals library_id or refdes (case-insensitive).
    """
    lower: str = (part_name or "").lower().strip()
    if not lower:
        return False
    lib: str = (getattr(comp, "library_id", "") or "").lower().strip()
    refdes: str = (getattr(comp, "refdes", "") or "").lower().strip()
    if lib and lower == lib:
        return True
    if refdes and lower == refdes:
        return True
    return False


class ActiveMatcher(MatcherBase):
    """Within-type scoring matcher for non-passive components.

    Runs a classic matcher chain (Exact → Fuzzy → Feature → Value →
    Fallback) within a single type pool, then scores candidates with
    5 dimensions that are meaningful within a type.

    MATCHER_PRIORITY = 2 (Phase 2B, after PassiveMatcher).
    """

    MATCHER_NAME: ClassVar[str] = "active"
    MATCHER_PRIORITY: ClassVar[int] = 2

    # Within-type 5-dimension weights (prefix removed — hard constraint)
    WITHIN_TYPE_WEIGHTS: dict[str, float] = {
        "footprint": 0.30,
        "value": 0.15,
        "jedec": 0.20,
        "pin_count": 0.20,
        "part_name": 0.15,
    }

    # Minimum within-type score to accept
    MIN_WITHIN_SCORE: float = 0.50

    # How many top-scored candidates to pass to the chain
    TOP_N: int = 20

    def __init__(self) -> None:
        """Initialise with internal matcher chain."""
        super().__init__()
        self._exact = ExactMatcher()
        self._fuzzy = FuzzyNameMatcher()
        self._feature = FeatureExtractMatcher()
        self._value = ValueMatcher()
        self._fallback = FallbackMatcher()

    # ── Core matching interface ──────────────────────────────────────

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
        src_type: str = "",
    ) -> MatchResult:
        """Match a CIS component within a typed candidate pool.

        Args:
            source: CIS source component.
            candidates: HDL candidates (pre-filtered to same type).
            src_type: Type name (e.g. "IC", "connector").

        Returns:
            MatchResult with ACTIVE_WITHIN_TYPE strategy, or no_match.
        """
        if not candidates:
            logger.debug(
                "ActiveMatcher: no candidates for %s (type=%s)",
                source.library_id, src_type,
            )
            return MatchResult.no_match(source.library_id)

        # ── Step 1: Score all candidates within type ───────────────
        scored: list[tuple[ComponentDef, float, dict[str, float]]] = []

        for candidate in candidates:
            dims: dict[str, float] = self._score_dims(source, candidate)
            total: float = sum(
                dims[k] * self.WITHIN_TYPE_WEIGHTS[k]
                for k in self.WITHIN_TYPE_WEIGHTS
            )
            scored.append((candidate, total, dims))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return MatchResult.no_match(source.library_id)

        # ── Step 2: Run matcher chain on top-N ─────────────────────
        top_candidates: list[ComponentDef] = [
            c for c, _s, _d in scored[:self.TOP_N]
        ]

        chain_result: MatchResult = self._run_chain(source, top_candidates)

        # ── Step 3: Compute within-type confidence ─────────────────
        best_candidate: ComponentDef = top_candidates[0]
        best_score: float = scored[0][1]
        best_dims: dict[str, float] = scored[0][2]

        # If chain produced a HIGH-QUALITY match (not just fallback), use its target.
        # FallbackMatcher only does prefix matching — it doesn't consider
        # footprint/pin_count/value. When chain falls to fallback, prefer
        # the top-scored candidate (which considers all dimensions).
        chain_strategy = chain_result.strategy if chain_result else None
        use_chain: bool = (
            chain_result.confidence > 0
            and chain_result.target_library_id
            and chain_strategy not in (None, MatchStrategy.MANUAL, MatchStrategy.FALLBACK)
        )
        if use_chain:
            # Find the chain's target in scored list
            for cand, s, d in scored:
                if cand.library_id == chain_result.target_library_id:
                    best_candidate = cand
                    best_score = s
                    best_dims = d
                    break

        # Use the BEST of chain result and scoring (but for fallback, scoring wins)
        if use_chain and chain_result.confidence > best_score:
            within_conf = chain_result.confidence
        else:
            within_conf = best_score
        within_conf = max(within_conf, self.MIN_WITHIN_SCORE)
        within_conf = min(within_conf, 1.0)

        # ── Step 3.5: Footprint wildcard rescue (v2c A.6) ──────────
        # Only rescues when the CIS footprint has no usable size AND the
        # normal within-type score is below the wildcard confidence (0.85).
        # Semantics: max(normal, wildcard) — a strong normal match wins.
        wildcard_cand, wildcard_name_score = self._match_footprint_wildcard(
            source, candidates
        )
        wildcard_used: bool = (
            wildcard_cand is not None
            and wildcard_name_score >= 0.5
            and 0.85 > within_conf
        )
        if wildcard_used:
            best_candidate = wildcard_cand
            within_conf = 0.85
            logger.info(
                "ActiveMatcher wildcard: %s → %s (footprint empty, "
                "part_name=%.2f, within_conf=0.85)",
                source.library_id, best_candidate.library_id, wildcard_name_score,
            )

        # ── Step 4: Build match_dims string ────────────────────────
        if wildcard_used:
            match_dims: str = "footprint* wildcard part_name✅ pin_count✅"
        else:
            match_dims = self._build_match_dims(best_dims)

        # ── Step 5: Select primitive ───────────────────────────────
        self._select_primitive(best_candidate, source)
        pin_mapping: dict[str, str] = self._build_pin_mapping(source, best_candidate)

        logger.info(
            "ActiveMatcher: %s → %s (type=%s, within_conf=%.2f, dims=%s)",
            source.library_id,
            best_candidate.library_id,
            src_type,
            within_conf,
            match_dims,
        )

        result = MatchResult(
            confidence=within_conf,
            strategy=MatchStrategy.ACTIVE_WITHIN_TYPE,
            source_library_id=source.library_id,
            target_library_id=best_candidate.library_id,
            pin_mapping=pin_mapping,
            phase2_strategy_detail=match_dims,
        )

        # ── Step 6: Generate top-3, store source value, enrich ────
        result.extra_data["_source_value"] = source.value or ""
        result.top3_candidates = self._generate_top3(source, candidates)
        self._enrich_result(result, candidates)

        return result

    # ── Matcher chain ────────────────────────────────────────────────

    def _run_chain(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Run the classic matcher chain on top candidates.

        Returns:
            MatchResult from the first matcher that meets its threshold,
            or a no_match result if all fail.
        """
        chain: list[MatcherBase] = [
            self._exact,
            self._fuzzy,
            self._feature,
            self._value,
            self._fallback,
        ]

        for matcher in chain:
            result: MatchResult = matcher.match(source, candidates)
            if result.confidence >= matcher.confidence_threshold():
                logger.debug(
                    "ActiveMatcher chain: %s matched by %s (conf=%.2f)",
                    source.library_id, matcher.MATCHER_NAME, result.confidence,
                )
                return result

        return MatchResult.no_match(source.library_id)

    # ── 5-dimension scoring ──────────────────────────────────────────

    def _score_dims(
        self,
        source: ComponentDef,
        candidate: ComponentDef,
    ) -> dict[str, float]:
        """Score all 5 dimensions for a (source, candidate) pair.

        Returns:
            Dict of dimension_name → score (0.0–1.0).
        """
        return {
            "footprint": self._score_footprint(source, candidate),
            "value": self._score_value(source, candidate),
            "jedec": self._score_jedec(source, candidate),
            "pin_count": self._score_pin_count(source, candidate),
            "part_name": self._score_part_name(source, candidate),
        }

    @staticmethod
    def _score_footprint(source: ComponentDef, candidate: ComponentDef) -> float:
        """Compare package sizes from footprints."""
        src_fp: str = getattr(source, "footprint", "") or ""
        cand_fp: str = getattr(candidate, "footprint", "") or ""

        if not src_fp or not cand_fp:
            return 0.5  # neutral

        src_size: str = extract_pkg_size(src_fp)
        cand_size: str = extract_pkg_size(cand_fp)

        if not src_size or not cand_size:
            return 0.5

        if src_size == cand_size:
            return 1.0

        # Partial match
        if src_size in cand_size or cand_size in src_size:
            return 0.7

        # Same leading digits
        src_digits: str = "".join(c for c in src_size if c.isdigit())
        cand_digits: str = "".join(c for c in cand_size if c.isdigit())
        if src_digits and src_digits == cand_digits:
            return 0.6

        return 0.2

    @staticmethod
    def _score_value(source: ComponentDef, candidate: ComponentDef) -> float:
        """Normalised electrical value comparison."""
        src_val: str = normalize_value(getattr(source, "value", "") or "")
        cand_val: str = normalize_value(getattr(candidate, "value", "") or "")

        if not src_val or not cand_val:
            return 0.5

        if src_val == cand_val:
            return 1.0

        # Check ptf_rows
        ptf_rows: list[dict] = (
            candidate.extra_data.get("ptf_rows", [])
            if hasattr(candidate, "extra_data") else []
        )
        for row in ptf_rows:
            row_val: str = normalize_value(row.get("value", ""))
            if row_val and row_val == src_val:
                return 0.9

        return 0.0

    @staticmethod
    def _score_jedec(source: ComponentDef, candidate: ComponentDef) -> float:
        """JEDEC_TYPE match.

        v2c: A single-sided missing JEDEC is neutral (0.5), not a penalty
        (was 0.4) — an empty CIS JEDEC should not drag down confidence for
        otherwise plausible candidates (A.6/J10).
        """
        src_jedec: str = ""
        cand_jedec: str = ""

        if hasattr(source, "extra_data") and source.extra_data:
            src_jedec = source.extra_data.get("jedec_type", "")
        if not src_jedec:
            src_jedec = getattr(source, "jedec_type", "") or ""

        if hasattr(candidate, "extra_data") and candidate.extra_data:
            ptf_rows: list[dict] = candidate.extra_data.get("ptf_rows", [])
            if ptf_rows:
                cand_jedec = ptf_rows[0].get("jedec_type", "")
        if not cand_jedec:
            cand_jedec = getattr(candidate, "jedec_type", "") or ""

        if not src_jedec and not cand_jedec:
            return 0.5
        if not src_jedec or not cand_jedec:
            return 0.5  # v2c: single-sided missing → neutral
        if src_jedec.upper() == cand_jedec.upper():
            return 1.0
        return 0.0

    @staticmethod
    def _score_pin_count(source: ComponentDef, candidate: ComponentDef) -> float:
        """Pin count proximity (normalised).

        v2c: Unknown CIS pin count (src_pins == 0) is neutral (0.5), not a
        heavy penalty (was 1 - 54/54 = 0.0 for J10).  Unknown candidate pin
        count is likewise neutral.  Only when BOTH sides are known does the
        proximity metric apply.
        """
        src_pins: int = getattr(source, "pin_count", 0) or 0
        cand_pins: int = getattr(candidate, "pin_count", 0) or 0

        if src_pins == 0 and cand_pins == 0:
            return 1.0
        if src_pins == 0 or cand_pins == 0:
            return 0.5  # v2c: unknown side → neutral

        max_pins: int = max(src_pins, cand_pins, 1)
        diff: int = abs(src_pins - cand_pins)
        return 1.0 - (diff / max_pins)

    @staticmethod
    def _score_part_name(source: ComponentDef, candidate: ComponentDef) -> float:
        """Token overlap between part names, with alias expansion.

        Splits BOTH part names on ``[_-\\s]+``, then scores the fraction of
        source tokens that appear in the candidate name — either directly or
        via a configured alias (``MatchConfig.part_name_aliases``).  This lets
        mixed alphanumeric names such as "MJ8-M2" match "rj45_2x2_led" via
        the alias mj8 → rj45 (A.6).

        v2c placeholder fallback: when the source part_name is a generic
        refdes placeholder (equals library_id/refdes, e.g. J10 → "J10"),
        the VALUE string (e.g. "MJ8-M2") is used as the name source instead.

        v2c guarantee: "STM32F407_VGT6" vs "STM32F407_VET6" still scores 0.5
        (1 of 2 tokens match; no aliases apply).
        """
        src_name: str = getattr(source, "part_name", "") or ""
        cand_name: str = getattr(candidate, "part_name", "") or ""

        if src_name and _is_placeholder_name(src_name, source):
            value_fallback: str = getattr(source, "value", "") or ""
            if value_fallback:
                src_name = value_fallback

        if not src_name or not cand_name:
            return 0.5

        src_lower: str = src_name.lower()
        cand_lower: str = cand_name.lower()

        src_tokens: list[str] = [
            t for t in re.split(r"[_\-\s]+", src_lower) if t
        ]

        if not src_tokens:
            return 0.5

        aliases: dict[str, list[str]] = MatchConfig.instance().part_name_aliases

        matched: int = 0
        for token in src_tokens:
            if token in cand_lower:
                matched += 1
                continue
            for alias_word in aliases.get(token, []):
                if alias_word and alias_word in cand_lower:
                    matched += 1
                    break
        return matched / len(src_tokens)

    # ── Footprint wildcard rescue (v2c A.6) ─────────────────────────

    def _match_footprint_wildcard(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> tuple[ComponentDef | None, float]:
        """Rescue path for components with an empty/invalid CIS footprint.

        When the CIS footprint carries no usable package size (e.g. J10 with
        footprint=""), normal footprint scoring cannot discriminate.  This
        method looks for a candidate whose part-name token score (with alias
        expansion) is >= 0.5 AND whose pin count is compatible, then reports
        it as a high-confidence (0.85) wildcard match.

        Trigger gate:
            source footprint is empty OR ``extract_pkg_size`` yields no
            4-digit numeric size.

        Pin compatibility:
            src.pin_count == 0 OR cand.pin_count == 0 OR
            |diff| / max(pins) <= 0.3

        Rescue-only semantics:
            The caller applies ``max(normal_within, wildcard_within)`` — a
            strong normal match (>= 0.85) is never overridden.

        Args:
            source: CIS source component.
            candidates: HDL candidates in the same type pool.

        Returns:
            (best_candidate, best_name_score) or (None, 0.0) when the
            wildcard path does not apply.
        """
        src_fp: str = getattr(source, "footprint", "") or ""
        src_size: str = extract_pkg_size(src_fp)
        size_valid: bool = (
            bool(src_size)
            and len(src_size) >= 4
            and any(c.isdigit() for c in src_size)
        )
        if size_valid:
            return None, 0.0  # A usable size exists → normal scoring applies

        best_cand: ComponentDef | None = None
        best_score: float = 0.0

        for candidate in candidates:
            name_score: float = self._score_part_name(source, candidate)
            if name_score < 0.5:
                continue

            src_pins: int = getattr(source, "pin_count", 0) or 0
            cand_pins: int = getattr(candidate, "pin_count", 0) or 0
            if src_pins and cand_pins:
                diff: float = abs(src_pins - cand_pins)
                if diff / max(src_pins, cand_pins) > 0.3:
                    continue

            if name_score > best_score:
                best_score = name_score
                best_cand = candidate
            elif name_score == best_score and best_cand is not None:
                # Tiebreak: prefer the more specific part (larger pin count),
                # e.g. rj45_2x2_led (54 pins) over generic rj45 (12 pins).
                if (getattr(candidate, "pin_count", 0) or 0) > (
                    getattr(best_cand, "pin_count", 0) or 0
                ):
                    best_cand = candidate

        if best_cand is None or best_score < 0.5:
            return None, 0.0
        return best_cand, best_score

    # ── Match dims builder ───────────────────────────────────────────

    @staticmethod
    def _build_match_dims(dims: dict[str, float]) -> str:
        """Build human-readable match dimension string.

        Format: "footprint✅ value⚠️ jedec❌ pin_count✅ part_name⚠️"

        Args:
            dims: Dict of dimension → score (0.0–1.0).

        Returns:
            Formatted string with emoji indicators.
        """
        parts: list[str] = []
        for dim_name in ("footprint", "value", "jedec", "pin_count", "part_name"):
            score: float = dims.get(dim_name, 0.0)
            if score >= 0.9:
                parts.append(f"{dim_name}✅")
            elif score >= 0.6:
                parts.append(f"{dim_name}⚠️")
            elif score >= 0.4:
                parts.append(f"{dim_name}⚠️(neutral)")
            else:
                parts.append(f"{dim_name}❌")
        return " ".join(parts)

    # ── Top-3 generation ─────────────────────────────────────────────

    def _generate_top3(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> list[dict]:
        """Generate top-3 candidates within this type pool.

        Args:
            source: CIS source component.
            candidates: All candidates in this type pool.

        Returns:
            List of up to 3 dicts with keys:
            {type, library_id, part_name, primitive, final_conf, match_dims}.
        """
        scored: list[tuple[ComponentDef, float, dict[str, float]]] = []
        for candidate in candidates:
            dims: dict[str, float] = self._score_dims(source, candidate)
            total: float = sum(
                dims[k] * self.WITHIN_TYPE_WEIGHTS[k]
                for k in self.WITHIN_TYPE_WEIGHTS
            )
            scored.append((candidate, total, dims))

        scored.sort(key=lambda x: x[1], reverse=True)

        top3: list[dict] = []
        for cand, total, dims in scored[:3]:
            ptf_rows: list[dict] = (
                cand.extra_data.get("ptf_rows", [])
                if hasattr(cand, "extra_data") else []
            )
            row0: dict = ptf_rows[0] if ptf_rows else {}
            top3.append({
                "type": getattr(cand, "category", ""),
                "library_id": cand.library_id,
                "part_name": cand.part_name,
                "primitive": (
                    cand.extra_data.get("selected_primitive_body", "")
                    if hasattr(cand, "extra_data") else ""
                ),
                "final_conf": round(total, 4),
                "match_dims": self._build_match_dims(dims),
                # v2c (A.4): candidate-row enrichment keys
                "value": row0.get("value", "") or getattr(cand, "value", "") or "",
                "footprint": (
                    row0.get("package_type", "")
                    or row0.get("jedec_type", "")
                    or getattr(cand, "footprint", "")
                    or ""
                ),
                "jedec": row0.get("jedec_type", ""),
                "package_type": row0.get("package_type", ""),
                "pin_count": getattr(cand, "pin_count", 0) or 0,
            })

        return top3

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _select_primitive(
        candidate: ComponentDef,
        source: ComponentDef,
    ) -> None:
        """Select the best primitive for the matched candidate."""
        all_prims: list[dict] = (
            candidate.extra_data.get("all_primitives", [])
            if hasattr(candidate, "extra_data") else []
        )
        if not all_prims:
            return

        src_fp: str = getattr(source, "footprint", "") or ""
        src_fp_size: str = extract_pkg_size(src_fp)

        # Try to match by footprint size
        if src_fp_size:
            for prim in all_prims:
                pn: str = prim.get("part_name", "")
                if src_fp_size in pn:
                    candidate.extra_data["selected_primitive_body"] = pn
                    return

        # Fallback: first primitive
        candidate.extra_data["selected_primitive_body"] = all_prims[0].get(
            "part_name", ""
        )

    # ── Result enrichment for CSV/HTML reporting ─────────────────────

    @staticmethod
    def _enrich_result(
        result: MatchResult,
        candidates: list[ComponentDef],
    ) -> None:
        """Populate extra_data with HDL-side info from matched ptf_row."""
        from cis2hdl.utils.naming import normalize_value

        matched_cand: ComponentDef | None = None
        for c in candidates:
            if c.library_id == result.target_library_id:
                matched_cand = c
                break

        if matched_cand is None:
            return

        src_value_norm = normalize_value(result.extra_data.get("_source_value", ""))
        ptf_rows = matched_cand.extra_data.get("ptf_rows", []) if hasattr(matched_cand, "extra_data") else []

        matched_row = None
        if src_value_norm and ptf_rows:
            for row in ptf_rows:
                if normalize_value(row.get("value", "")) == src_value_norm:
                    matched_row = row
                    break

        if matched_row is not None:
            result.extra_data["hdl_value"] = matched_row.get("value", "")
            result.extra_data["hdl_footprint"] = matched_row.get("package_type", "") or matched_row.get("jedec_type", "")
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
            result.extra_data["hdl_package_type"] = pkg or result.extra_data["hdl_footprint"]

        result.extra_data["hdl_category"] = getattr(matched_cand, "category", "") or ""
        result.extra_data["hdl_pin_count"] = getattr(matched_cand, "pin_count", 0) or 0
        sel_prim = matched_cand.extra_data.get("selected_primitive_body", "") if hasattr(matched_cand, "extra_data") else ""
        result.extra_data["selected_primitive"] = sel_prim

        for entry in result.top3_candidates:
            if not entry.get("primitive"):
                for c in candidates:
                    if c.library_id == entry.get("library_id") or c.part_name == entry.get("part_name"):
                        sel = c.extra_data.get("selected_primitive_body", "") if hasattr(c, "extra_data") else ""
                        if sel:
                            entry["primitive"] = sel
                            break

    def confidence_threshold(self) -> float:
        """Active matcher threshold — 0.50 minimum within-type score."""
        return self.MIN_WITHIN_SCORE
