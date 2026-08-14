"""ConversionQualityEstimator — four-dimensional quality assessment.

Evaluates conversion quality across four dimensions:
  - Logic completeness    (weight 0.40): devices, pins, nets
  - Coordinate availability (weight 0.25): instance positions, wire paths
  - Match coverage        (weight 0.20): how many components matched successfully
  - Symbol fidelity       (weight 0.15): quality of symbol graphics

Produces a QualityReport with per-dimension scores and actionable summary.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from cis2hdl.core.ir.design import DesignIR
    from cis2hdl.core.ir.match import MatchResult

logger = logging.getLogger(__name__)


# ── QualityReport ───────────────────────────────────────────────────────────


@dataclass
class QualityReport:
    """Four-dimensional conversion quality report.

    Each score is in the range [0.0, 1.0]. The overall score is a weighted
    sum of the four dimensions.

    Attributes:
        logic_score: Completeness of device/pin/net data.
        coordinate_score: Availability of position/wire coordinate data.
        match_score: Coverage of component matching.
        symbol_score: Fidelity of symbol graphics.
        overall_score: Weighted aggregate score.
        matched_count: Number of successfully matched components.
        total_count: Total number of components to match.
    """

    logic_score: float = 0.0
    coordinate_score: float = 0.0
    match_score: float = 0.0
    symbol_score: float = 0.0
    overall_score: float = 0.0
    matched_count: int = 0
    total_count: int = 0

    def summary(self) -> str:
        """Human-readable single-line quality summary.

        Returns:
            Summary string with overall score and grade.
        """
        if self.overall_score >= 0.90:
            grade = "A (优秀)"
        elif self.overall_score >= 0.75:
            grade = "B (良好)"
        elif self.overall_score >= 0.60:
            grade = "C (一般)"
        elif self.overall_score >= 0.40:
            grade = "D (较差)"
        else:
            grade = "F (不可用)"

        return (
            f"转换质量: {self.overall_score:.0%} [{grade}] "
            f"匹配: {self.matched_count}/{self.total_count}, "
            f"逻辑={self.logic_score:.0%} 坐标={self.coordinate_score:.0%} "
            f"匹配={self.match_score:.0%} 符号={self.symbol_score:.0%}"
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary for reporting."""
        return {
            "logic_score": round(self.logic_score, 4),
            "coordinate_score": round(self.coordinate_score, 4),
            "match_score": round(self.match_score, 4),
            "symbol_score": round(self.symbol_score, 4),
            "overall_score": round(self.overall_score, 4),
            "matched_count": self.matched_count,
            "total_count": self.total_count,
            "summary": self.summary(),
        }


# ── ConversionQualityEstimator ──────────────────────────────────────────────


class ConversionQualityEstimator:
    """Four-dimensional conversion quality estimator.

    Weights (from system design):
        logic      0.40 — device definitions, pin counts, net connectivity
        coordinate 0.25 — instance placement, wire routing coordinates
        match      0.20 — component matching success rate
        symbol     0.15 — symbol graphic fidelity

    Usage:
        estimator = ConversionQualityEstimator()
        report = estimator.estimate(design, matches)
        print(report.summary())
    """

    WEIGHTS: ClassVar[dict[str, float]] = {
        "logic": 0.40,
        "coordinate": 0.25,
        "match": 0.20,
        "symbol": 0.15,
    }

    def estimate(
        self,
        design: "DesignIR",
        matches: "list[MatchResult]",
    ) -> QualityReport:
        """Estimate conversion quality from design IR and match results.

        Args:
            design: The parsed DesignIR containing pages, instances, and nets.
            matches: List of MatchResult entries from the matching pipeline.

        Returns:
            A QualityReport with all four dimension scores.
        """
        report = QualityReport()

        # ── Logic completeness ───────────────────────────────────────
        report.logic_score = self._logic_completeness(design)

        # ── Coordinate availability ──────────────────────────────────
        report.coordinate_score = self._coordinate_availability(design)

        # ── Match coverage ───────────────────────────────────────────
        # Phase XII R1: use page-summed instance counts instead of
        # design.all_instances (a cached_property that may hold stale
        # pre-rebuild values when the ConversionEngine replaces page
        # instances from the ComponentCatalog).
        report.total_count = sum(len(p.instances) for p in design.pages)
        report.matched_count = self._count_matched_instances(design, matches)
        report.match_score = self._match_coverage(matches, design)

        # ── Symbol fidelity ──────────────────────────────────────────
        report.symbol_score = self._symbol_fidelity(matches)

        # ── Overall weighted score ───────────────────────────────────
        report.overall_score = (
            report.logic_score * self.WEIGHTS["logic"]
            + report.coordinate_score * self.WEIGHTS["coordinate"]
            + report.match_score * self.WEIGHTS["match"]
            + report.symbol_score * self.WEIGHTS["symbol"]
        )

        logger.info(
            "Quality: overall=%.2f logic=%.2f coord=%.2f match=%.2f sym=%.2f "
            "(%d/%d matched)",
            report.overall_score,
            report.logic_score,
            report.coordinate_score,
            report.match_score,
            report.symbol_score,
            report.matched_count,
            report.total_count,
        )

        return report

    def _logic_completeness(self, design: "DesignIR") -> float:
        """Calculate logic completeness score.

        Factors:
          - Number of pages parsed vs total
          - Number of instances with valid library_ids
          - Number of nets with connections
          - Component DB coverage

        Args:
            design: The DesignIR.

        Returns:
            Score from 0.0 to 1.0.
        """
        if not design.pages:
            return 0.0

        # Page factor: how many pages have content
        pages_with_content = sum(
            1 for page in design.pages
            if page.instances or page.nets
        )
        page_factor = pages_with_content / max(len(design.pages), 1)

        # Instance factor: instances with valid library_ids
        # (page-summed — see R1 note in estimate())
        total_instances = sum(len(p.instances) for p in design.pages)
        if total_instances == 0:
            return page_factor * 0.5  # Pages exist but no instances

        instances_with_lib = sum(
            1 for page in design.pages
            for inst in page.instances
            if inst.library_id
        )
        inst_factor = instances_with_lib / total_instances

        # Net factor: nets with connections
        total_nets = sum(len(p.nets) for p in design.pages)
        if total_nets == 0:
            net_factor = 0.5  # No nets but instances exist — possible
        else:
            nets_with_connections = sum(
                1 for page in design.pages
                for net in page.nets
                if net.connections
            )
            net_factor = nets_with_connections / total_nets

        # Combined logic score
        return page_factor * 0.3 + inst_factor * 0.4 + net_factor * 0.3

    def _coordinate_availability(self, design: "DesignIR") -> float:
        """Calculate coordinate availability score.

        Checks how many instances have non-zero coordinates and how many
        wires have coordinate data.

        Args:
            design: The DesignIR.

        Returns:
            Score from 0.0 to 1.0.
        """
        total_instances = sum(len(p.instances) for p in design.pages)
        if total_instances == 0:
            return 1.0  # No instances = no coordinate loss

        instances_with_coords = sum(
            1 for page in design.pages
            for inst in page.instances
            if inst.loc_x != 0 or inst.loc_y != 0
        )

        inst_coord_ratio = instances_with_coords / total_instances

        # Wire coordinates
        total_wires = sum(len(page.wires) for page in design.pages)
        if total_wires == 0:
            return inst_coord_ratio  # Only instance coords matter

        wires_with_coords = sum(
            1 for page in design.pages
            for wire in page.wires
            if (wire.start_x != 0 or wire.start_y != 0
                or wire.end_x != 0 or wire.end_y != 0)
        )
        wire_coord_ratio = wires_with_coords / max(total_wires, 1)

        return inst_coord_ratio * 0.6 + wire_coord_ratio * 0.4

    def _match_coverage(
        self,
        matches: "list[MatchResult]",
        design: "DesignIR",
    ) -> float:
        """Calculate match coverage score.

        Factors:
          - Ratio of instances that have a match result
          - Average confidence of matched instances
          - Match strategy distribution (exact > fuzzy > feature > manual)

        Args:
            matches: List of MatchResult entries.
            design: The DesignIR.

        Returns:
            Score from 0.0 to 1.0.
        """
        total_instances = sum(len(p.instances) for p in design.pages)
        if total_instances == 0:
            return 1.0

        if not matches:
            return 0.0

        matched_count = self._count_matched_instances(design, matches)
        coverage_ratio = matched_count / total_instances

        # Average confidence
        confidences = [m.confidence for m in matches if m.confidence > 0]
        avg_confidence = sum(confidences) / max(len(confidences), 1)

        # Strategy bonus: higher for exact/fuzzy, lower for manual
        from cis2hdl.core.ir.match import MatchStrategy
        strategy_scores = {
            MatchStrategy.EXACT: 1.0,
            MatchStrategy.FUZZY: 0.8,
            MatchStrategy.FEATURE: 0.6,
            MatchStrategy.MANUAL: 0.3,
            MatchStrategy.POWER_SYMBOL: 1.0,
        }
        avg_strategy = sum(
            strategy_scores.get(m.strategy, 0.5)
            for m in matches
        ) / max(len(matches), 1)

        return coverage_ratio * 0.5 + avg_confidence * 0.3 + avg_strategy * 0.2

    def _symbol_fidelity(self, matches: "list[MatchResult]") -> float:
        """Calculate symbol fidelity score.

        Based on match confidence and strategy — higher confidence matches
        typically mean better symbol data from HDL library.

        Args:
            matches: List of MatchResult entries.

        Returns:
            Score from 0.0 to 1.0.
        """
        if not matches:
            return 0.0

        from cis2hdl.core.ir.match import MatchStrategy

        # Exact matches likely have full symbol fidelity
        # Fuzzy matches may have slight differences
        # Feature/manual matches may have degraded symbol data
        strategy_scores = {
            MatchStrategy.EXACT: 0.95,
            MatchStrategy.FUZZY: 0.75,
            MatchStrategy.FEATURE: 0.55,
            MatchStrategy.MANUAL: 0.30,
            MatchStrategy.POWER_SYMBOL: 0.95,
        }

        total_score = sum(
            strategy_scores.get(m.strategy, 0.3) * m.confidence
            for m in matches
            if m.confidence > 0
        )
        return total_score / max(len(matches), 1)

    @staticmethod
    def _count_matched(matches: "list[MatchResult]") -> int:
        """Count the number of successfully matched components.

        A match is considered successful if it has a non-empty target_library_id
        and confidence > 0.

        Args:
            matches: List of MatchResult entries.

        Returns:
            Number of successfully matched components.
        """
        return sum(
            1 for m in matches
            if m.target_library_id and m.confidence > 0
        )

    @staticmethod
    def _count_matched_instances(
        design: "DesignIR",
        matches: "list[MatchResult]",
    ) -> int:
        """Count instances that have a successful match result.

        Phase XII R1/R2: the old ``_count_matched`` counted unique
        MatchResults, which UNDERSTATES coverage when many instances
        share one result key — e.g. 305 power symbol instances
        (GND/DGND/VCC_CIRCLE) share only 3 deterministic MatchResults,
        so 917/1219 was reported instead of 1219/1219.

        This counts actual page instances: an instance is "matched" when
        a MatchResult exists for its refdes OR its library_id (case-
        insensitive), with a non-empty target and confidence > 0.

        Args:
            design: The DesignIR (post-rebuild page instances).
            matches: List of MatchResult entries.

        Returns:
            Number of design instances with a successful match.
        """
        matched_keys: set[str] = {
            getattr(m, "source_library_id", "").upper()
            for m in matches
            if m.target_library_id and m.confidence > 0
        }
        if not matched_keys:
            return 0
        count = 0
        for page in design.pages:
            for inst in page.instances:
                refdes = getattr(inst, "refdes", "") or ""
                lib_id = getattr(inst, "library_id", "") or ""
                if refdes.upper() in matched_keys or lib_id.upper() in matched_keys:
                    count += 1
        return count
