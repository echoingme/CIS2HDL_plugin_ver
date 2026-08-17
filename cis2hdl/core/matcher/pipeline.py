"""MatcherPipeline — two-phase component matching pipeline (v2.0).

Phase 1: Type hypothesis generation (refdes → ordered type list)
Phase 1.5: Candidate pool construction (type-filtered HDL candidates)
Phase 2A: PassiveMatcher — deterministic rule matching (C/R/L/D/FB/LED)
Phase 2B: ActiveMatcher — within-type scoring (IC/connector/crystal/...)

final_conf = phase1_prior_conf × phase2_within_conf

Also includes ManualMatchResolver for handling unmatched components
via user interaction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from cis2hdl.core.db.component_db import ComponentDB
from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.ir.match import MatchResult, MatchStrategy
from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.matcher.exact import ExactMatcher
from cis2hdl.core.matcher.fallback import FallbackMatcher
from cis2hdl.core.matcher.feature import FeatureExtractMatcher
from cis2hdl.core.matcher.fuzzy import FuzzyNameMatcher
from cis2hdl.core.matcher.value_matcher import ValueMatcher
from cis2hdl.core.matcher.prefix_filter import extract_prefix
from cis2hdl.core.matcher.match_config import MatchConfig
from cis2hdl.core.matcher.scoring import PrefixAffinityCalculator
from cis2hdl.core.matcher.type_hypothesis import (
    TypeHypothesis,
    TypeHypothesisGenerator,
)
from cis2hdl.core.matcher.candidate_pool import (
    CandidatePool,
    CandidatePoolBuilder,
    TypeCandidateSet,
)
from cis2hdl.core.matcher.passive_matcher import PassiveMatcher
from cis2hdl.core.matcher.active_matcher import ActiveMatcher

logger = logging.getLogger(__name__)

# Default path for persisting user mapping rules
DEFAULT_RULES_PATH: Path = Path.home() / ".cis2hdl" / "mappings.yaml"

# v2.0 thresholds
NEEDS_REVIEW_THRESHOLD: float = 0.40
STOP_SEARCH_THRESHOLD: float = 0.75


class ManualMatchResolver(MatcherBase):
    """Last-resort matcher: presents candidates for manual user resolution.

    When all automatic matchers fail, this resolver produces a
    MatchResult with strategy=MANUAL and confidence=0.0, along with
    a list of candidate library_ids for the GUI to display.
    """

    MATCHER_NAME: str = "manual"
    MATCHER_PRIORITY: int = 99

    def __init__(self) -> None:
        """Initialise the resolver with an empty match map."""
        super().__init__()
        self._match_map: dict[str, dict[str, str]] = {}

    def match(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Return a MANUAL result with candidate list for user review."""
        if source.library_id in self._match_map:
            stored: dict[str, str] = self._match_map[source.library_id]
            return MatchResult(
                confidence=1.0,
                strategy=MatchStrategy.MANUAL,
                source_library_id=source.library_id,
                target_library_id=stored["target_library_id"],
                warnings=[
                    f"Pre-existing manual mapping applied "
                    f"(confirmed by '{stored['confirmed_by']}' at "
                    f"{stored['timestamp']})."
                ],
            )

        return MatchResult(
            confidence=0.0,
            strategy=MatchStrategy.MANUAL,
            source_library_id=source.library_id,
            target_library_id="",
            candidates=[c.library_id for c in candidates],
            warnings=[
                f"Automatic matching failed for '{source.part_name}'. "
                f"{len(candidates)} candidates available for manual review."
            ],
        )

    def confidence_threshold(self) -> float:
        return 1.0

    def resolve(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        return self.match(source, candidates)

    def accept(
        self,
        source_library_id: str,
        target_library_id: str,
    ) -> MatchResult:
        """Accept a manual match after user confirmation."""
        logger.info(
            "Manual match accepted: %s → %s",
            source_library_id,
            target_library_id,
        )
        timestamp: str = datetime.now(timezone.utc).isoformat()
        self._match_map[source_library_id] = {
            "target_library_id": target_library_id,
            "confirmed_by": "user",
            "timestamp": timestamp,
        }
        return MatchResult(
            confidence=1.0,
            strategy=MatchStrategy.MANUAL,
            source_library_id=source_library_id,
            target_library_id=target_library_id,
        )

    def export_rules(self, output_path: Path) -> int:
        """Export all confirmed user mapping decisions to a YAML file."""
        import yaml as _yaml

        mappings: list[dict[str, str]] = []
        for src_id, entry in self._match_map.items():
            mappings.append({
                "source_library_id": src_id,
                "target_library_id": entry["target_library_id"],
                "confirmed_by": entry.get("confirmed_by", "user"),
                "timestamp": entry.get("timestamp", ""),
            })

        data: dict[str, list[dict[str, str]]] = {"mappings": mappings}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            _yaml.safe_dump(data, fh, default_flow_style=False,
                            allow_unicode=True, sort_keys=False)
        logger.info("Exported %d mapping rule(s) to %s", len(mappings), output_path)
        return len(mappings)

    def import_rules(self, input_path: Path) -> int:
        """Import user mapping decisions from a YAML file."""
        import yaml as _yaml

        if not input_path.exists():
            raise FileNotFoundError(f"Rules file not found: {input_path}")

        with open(input_path, "r", encoding="utf-8") as fh:
            data: Any = _yaml.safe_load(fh)

        if data is None:
            return 0

        if not isinstance(data, dict) or "mappings" not in data:
            raise ValueError(
                f"Invalid rules file format in {input_path}: "
                f"expected a dict with 'mappings' key"
            )

        mappings: list[dict[str, Any]] = data["mappings"]
        imported: int = 0
        for entry in mappings:
            src_id: Optional[str] = entry.get("source_library_id")
            tgt_id: Optional[str] = entry.get("target_library_id")
            if not src_id or not tgt_id:
                continue
            self._match_map[src_id] = {
                "target_library_id": tgt_id,
                "confirmed_by": entry.get("confirmed_by", "imported"),
                "timestamp": entry.get("timestamp", ""),
            }
            imported += 1

        logger.info("Imported %d mapping rule(s) from %s", imported, input_path)
        return imported

    def save_rules(self, config_path: Optional[Path] = None) -> int:
        """Persist the current match map to disk."""
        target: Path = config_path if config_path is not None else DEFAULT_RULES_PATH
        count: int = self.export_rules(target)
        logger.info("Saved %d mapping rule(s) to %s", count, target)
        return count

    @property
    def match_map(self) -> dict[str, dict[str, str]]:
        return dict(self._match_map)

    def clear_rules(self) -> None:
        count: int = len(self._match_map)
        self._match_map.clear()
        logger.info("Cleared %d mapping rule(s)", count)

    def has_rule(self, source_library_id: str) -> bool:
        return source_library_id in self._match_map


# ── Passive types reference (imported from prefix_filter) ────────────
PASSIVE_TYPES: frozenset[str] = frozenset({
    "capacitor", "resistor", "inductor", "diode",
    "zener", "ferrite_bead", "led",
})


def _pick_primitive(cand: ComponentDef) -> str:
    """Pick the best primitive part_name for a candidate (v2c B.#9).

    Priority: ``selected_primitive_body`` (already chosen by the matcher),
    then the first primitive whose part_name contains a digit (size code),
    then the first primitive.

    Args:
        cand: HDL candidate ComponentDef.

    Returns:
        Primitive part_name string (may be empty).
    """
    if not hasattr(cand, "extra_data"):
        return ""
    extra = cand.extra_data
    sel: str = extra.get("selected_primitive_body", "") or ""
    if sel:
        return sel
    all_prims: list[dict] = extra.get("all_primitives", []) or []
    if not all_prims:
        return ""
    for prim in all_prims:
        pn: str = prim.get("part_name", "") or ""
        if any(ch.isdigit() for ch in pn):
            return pn
    return all_prims[0].get("part_name", "") or ""


class MatcherPipeline:
    """Two-phase component matching pipeline (v2.0).

    Phase 1: TypeHypothesisGenerator → ordered type hypotheses
    Phase 1.5: CandidatePoolBuilder → type-filtered candidate pools
    Phase 2: PassiveMatcher (passive) or ActiveMatcher (active)
             → within-type match with final_conf = prior × within

    Usage:
        pipeline = MatcherPipeline()
        results = pipeline.run_batch(cis_components, hdl_db)
    """

    def __init__(self) -> None:
        """Initialize pipeline with two-phase matching architecture."""
        # v2.0: Phase 1/1.5 are initialised lazily in run_batch()
        # to get fresh config and affinity per batch.
        self._passive_matcher = PassiveMatcher()
        self._active_matcher = ActiveMatcher()
        self._manual: ManualMatchResolver = ManualMatchResolver()

    # ── Batch matching (v2.0 two-phase architecture) ─────────────────

    def run_batch(
        self,
        sources: list[ComponentDef],
        db: ComponentDB,
    ) -> list[MatchResult]:
        """Run the two-phase pipeline for multiple source components.

        For each source:
        1. Phase 1: Generate type hypotheses (refdes + PST + value + learned)
        2. Phase 1.5: Build type-filtered candidate pools
        3. Phase 2: Search type pools in priority order
           - Passive types → PassiveMatcher (deterministic rules)
           - Active types → ActiveMatcher (within-type scoring)
        4. final_conf = phase1_prior × phase2_within
        5. Stop when final_conf ≥ 0.75 or PASSIVE_EXACT found
        6. All types exhausted → NEEDS_REVIEW

        Args:
            sources: List of CIS ComponentDef objects.
            db: HDL ComponentDB.

        Returns:
            List of MatchResult, one per source.
        """
        # ── Initialise Phase 1 components ─────────────────────────
        config = MatchConfig.instance()
        affinity_calc = PrefixAffinityCalculator()
        type_gen = TypeHypothesisGenerator(config, affinity_calc)
        # Phase XVIII R4/Q1: 候选只限 hdl_lib（用户决策；matching.hdl_lib_only）。
        from cis2hdl.core.config import config as _cfg
        _hdl_lib_only = bool(
            getattr(getattr(_cfg.routing, "matching", None), "hdl_lib_only", True)
        )
        pool_builder = CandidatePoolBuilder(db, hdl_lib_only=_hdl_lib_only)

        results: list[MatchResult] = []

        for source in sources:
            result = self._match_single(
                source, type_gen, pool_builder, affinity_calc
            )
            results.append(result)

        # ── Persist learned affinities ─────────────────────────────
        try:
            affinity_calc.save()
        except Exception as exc:
            logger.debug("Failed to save affinity matrix: %s", exc)

        # ── Summary ────────────────────────────────────────────────
        matched: int = sum(
            1 for r in results
            if r.strategy != MatchStrategy.MANUAL
            and r.strategy != MatchStrategy.NEEDS_REVIEW
        )
        needs_review: int = sum(
            1 for r in results
            if r.strategy == MatchStrategy.NEEDS_REVIEW
        )
        logger.info(
            "run_batch: %d/%d matched, %d needs review, %d manual",
            matched, len(results), needs_review,
            len(results) - matched - needs_review,
        )

        return results

    # ── Single component matching ────────────────────────────────────

    def _match_single(
        self,
        source: ComponentDef,
        type_gen: TypeHypothesisGenerator,
        pool_builder: CandidatePoolBuilder,
        affinity_calc: PrefixAffinityCalculator,
    ) -> MatchResult:
        """Match a single source component using two-phase architecture.

        Args:
            source: CIS source component.
            type_gen: Phase 1 type hypothesis generator.
            pool_builder: Phase 1.5 candidate pool builder.
            affinity_calc: Prefix affinity calculator for learning.

        Returns:
            MatchResult with full phase1/phase2/top3 metadata.
        """
        # ── Get refdes ────────────────────────────────────────────
        refdes: str = (
            getattr(source, "refdes", "")
            or source.part_name
            or source.library_id
        )
        prefix: str = extract_prefix(refdes)
        value: str = getattr(source, "value", "") or ""

        # ── Get PST data ──────────────────────────────────────────
        pst_data: dict | None = None
        extra = getattr(source, "extra_data", {}) or {}
        if extra:
            jedec_type = extra.get("pst_jedec_type") or extra.get("jedec_type") or ""
            pst_part_name = extra.get("pst_part_name") or ""
            if jedec_type or pst_part_name:
                pst_data = {
                    "jedec_type": jedec_type,
                    "part_name": pst_part_name,
                }

        # ── Phase 1: Type hypotheses ──────────────────────────────
        hypotheses: list[TypeHypothesis] = type_gen.generate(
            refdes, value, pst_data
        )

        if not hypotheses:
            logger.warning(
                "Phase 1: no type hypotheses for %s (refdes=%s)",
                source.library_id, refdes,
            )
            return MatchResult(
                confidence=0.0,
                strategy=MatchStrategy.NEEDS_REVIEW,
                source_library_id=source.library_id,
                error_note=f"No type hypotheses generated for prefix '{prefix}'",
            )

        # ── Phase 1.5: Candidate pool ─────────────────────────────
        pool: CandidatePool = pool_builder.build(hypotheses)

        # ── Phase 2: Search type pools in priority order ───────────
        all_type_results: list[dict] = []  # For top-3 generation
        best_result: MatchResult | None = None
        best_final_conf: float = 0.0

        # Load fixed prefix bindings (e.g. LB→ferrite_bead, LED→led)
        match_config = MatchConfig.instance()
        fixed_prefixes: dict[str, str] = match_config.fixed_prefixes
        is_fixed_prefix: bool = prefix in fixed_prefixes
        fixed_type: str = fixed_prefixes.get(prefix, "")

        for type_set in pool.iter_in_priority_order():
            type_name: str = type_set.type_name
            candidates: list[ComponentDef] = type_set.candidates

            if not candidates:
                logger.debug(
                    "Phase 2: no candidates for type '%s' (source=%s)",
                    type_name, source.library_id,
                )
                continue

            # Choose matcher based on type
            if type_name.lower() in PASSIVE_TYPES:
                phase2_result: MatchResult = self._passive_matcher.match(
                    source, candidates, type_name
                )
            else:
                phase2_result: MatchResult = self._active_matcher.match(
                    source, candidates, type_name
                )

            # Compute final confidence
            phase2_conf: float = phase2_result.confidence
            final_conf: float = type_set.prior_conf * phase2_conf

            # Track for top-3
            if phase2_result.target_library_id:
                # Phase XII R5: carry the ACTUAL matched part.ptf row data
                # (from PassiveMatcher._enrich_result) into the entry so the
                # top-3 candidate row for the SELECTED match shows the same
                # value/jedec/package_type/footprint as the main row — not
                # ptf_rows[0] (which may be a different variant, e.g. C102
                # matched 8.2PF/0201-RF/C0201 while ptf_rows[0] is
                # 100NF/0402C-S/C0402).
                _mrow = phase2_result.extra_data.get("_matched_row")
                _mrow = _mrow if isinstance(_mrow, dict) else {}
                all_type_results.append({
                    "type": type_name,
                    "library_id": phase2_result.target_library_id,
                    "part_name": "",
                    "primitive": "",
                    "final_conf": round(final_conf, 4),
                    "match_dims": getattr(phase2_result, "phase2_strategy_detail", ""),
                    "value": _mrow.get("value", ""),
                    "jedec": _mrow.get("jedec_type", ""),
                    "package_type": _mrow.get("package_type", ""),
                    "footprint": (
                        _mrow.get("package_type", "")
                        or _mrow.get("jedec_type", "")
                    ),
                })

            # Check stop conditions
            is_passive_exact: bool = (
                phase2_result.strategy == MatchStrategy.PASSIVE_EXACT
            )

            if final_conf > best_final_conf:
                best_final_conf = final_conf
                # Enrich result with phase info
                phase2_result.phase1_type = type_name
                phase2_result.phase1_prior_conf = type_set.prior_conf
                phase2_result.phase2_within_conf = phase2_conf
                phase2_result.confidence = final_conf
                best_result = phase2_result

            # Stop early if excellent match found
            if is_passive_exact:
                logger.debug(
                    "Phase 2: PASSIVE_EXACT stop for %s (type=%s, conf=%.2f)",
                    source.library_id, type_name, final_conf,
                )
                break

            # Stop early if this is a fixed-prefix binding (e.g. LB→ferrite_bead)
            # and we got ANY match from the target type — don't try second-priority.
            if is_fixed_prefix and type_name == fixed_type and phase2_result.target_library_id:
                logger.debug(
                    "Phase 2: fixed-prefix stop for %s (prefix=%s, type=%s, conf=%.2f)",
                    source.library_id, prefix, type_name, final_conf,
                )
                break

            if final_conf >= STOP_SEARCH_THRESHOLD:
                logger.debug(
                    "Phase 2: threshold stop for %s (type=%s, conf=%.2f)",
                    source.library_id, type_name, final_conf,
                )
                break

        # ── Post-processing ───────────────────────────────────────
        if best_result is not None and best_final_conf >= NEEDS_REVIEW_THRESHOLD:
            # Generate top-3 from all type results
            best_result.top3_candidates = self._generate_cross_type_top3(
                all_type_results, pool
            )

            # Record learning
            if best_result.phase1_type:
                affinity_calc.record_match(prefix, best_result.phase1_type)

            return best_result

        # All types exhausted without good match → NEEDS_REVIEW
        if best_result is not None:
            best_result.strategy = MatchStrategy.NEEDS_REVIEW
            best_result.top3_candidates = self._generate_cross_type_top3(
                all_type_results, pool
            )
            best_result.error_note = (
                f"All type hypotheses exhausted. "
                f"Best: {best_result.phase1_type} conf={best_final_conf:.2f}"
            )
            return best_result

        return MatchResult(
            confidence=0.0,
            strategy=MatchStrategy.NEEDS_REVIEW,
            source_library_id=source.library_id,
            error_note=f"No match found after exhausting {len(hypotheses)} type hypotheses",
            top3_candidates=self._generate_cross_type_top3(all_type_results, pool),
        )

    # ── Cross-type top-3 generation ──────────────────────────────────

    @staticmethod
    def _generate_cross_type_top3(
        all_results: list[dict],
        pool: Optional[CandidatePool] = None,
    ) -> list[dict]:
        """Generate top-3 candidates across all type pools.

        v2c (B.#9/A.4): When a CandidatePool is provided, each entry is
        enriched with ``part_name`` / ``primitive`` / ``value`` /
        ``footprint`` / ``jedec`` / ``package_type`` / ``pin_count``
        looked up from the pool's candidates.  This fixes the previously
        empty ``part_name``/``primitive`` in cross-type top-3 entries.

        Args:
            all_results: List of per-type match summaries.
            pool: CandidatePool (optional) used to enrich entries.

        Returns:
            Top 3 sorted by final_conf descending.
        """
        sorted_results: list[dict] = sorted(
            all_results,
            key=lambda x: x.get("final_conf", 0.0),
            reverse=True,
        )
        top3: list[dict] = sorted_results[:3]

        if pool is not None:
            lookup: dict[str, ComponentDef] = {}
            for type_set in pool.type_sets:
                for cand in type_set.candidates:
                    lookup.setdefault(cand.library_id, cand)

            for entry in top3:
                cand = lookup.get(entry.get("library_id", ""))
                if cand is None:
                    continue
                if not entry.get("part_name"):
                    entry["part_name"] = getattr(cand, "part_name", "") or ""
                if not entry.get("primitive"):
                    entry["primitive"] = _pick_primitive(cand)
                ptf_rows: list[dict] = (
                    cand.extra_data.get("ptf_rows", [])
                    if hasattr(cand, "extra_data") else []
                )
                # Phase XII R5: ptf_rows[0] is only a FALLBACK — when the
                # entry was already enriched with the actual matched row
                # (from _match_single via PassiveMatcher._matched_row) keep
                # that data so the selected candidate row matches the main
                # row exactly.  Empty fields are still filled from ptf_rows[0].
                row0: dict = ptf_rows[0] if ptf_rows else {}
                if not entry.get("value"):
                    entry["value"] = (
                        row0.get("value", "") or getattr(cand, "value", "") or ""
                    )
                if not entry.get("footprint"):
                    entry["footprint"] = (
                        row0.get("package_type", "")
                        or row0.get("jedec_type", "")
                        or getattr(cand, "footprint", "")
                        or ""
                    )
                if not entry.get("jedec"):
                    entry["jedec"] = row0.get("jedec_type", "")
                if not entry.get("package_type"):
                    entry["package_type"] = row0.get("package_type", "")
                if not entry.get("pin_count"):
                    entry["pin_count"] = getattr(cand, "pin_count", 0) or 0

        return top3

    # ── Single-component matching (backward compat) ──────────────────

    def run(
        self,
        source: ComponentDef,
        candidates: list[ComponentDef],
    ) -> MatchResult:
        """Run pipeline for a single component (v1.0 compat interface).

        v2.0: Delegates to the full two-phase pipeline via run_batch.
        For direct single-component matching, the caller should use
        run_batch([source], db) instead.
        """
        logger.warning(
            "MatcherPipeline.run() called directly. "
            "Use run_batch([source], db) for v2.0 two-phase matching."
        )
        # Fallback to manual resolver for backward compat
        return self._manual.resolve(source, candidates)
