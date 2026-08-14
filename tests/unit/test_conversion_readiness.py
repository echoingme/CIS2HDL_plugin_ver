"""Unit tests for ConversionReadinessEvaluator."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from cis2hdl.core.diagnostics.diagnostic_report import (
    Severity,
    FileState,
    FileStatus,
    DSNInternalInventory,
    ProjectInventory,
    ConversionReadinessEvaluator,
)


# ── ConversionReadinessEvaluator Tests ────────────────────────────────────


class TestConversionReadinessEvaluator:
    """ConversionReadinessEvaluator tests."""

    def test_empty_inventory_not_convertible(self) -> None:
        """Empty inventory → cannot convert."""
        evaluator = ConversionReadinessEvaluator()
        inv = ProjectInventory()
        report = evaluator.evaluate(inv)
        assert not report.can_convert
        assert report.recommended_path == "BLOCKED"

    def test_full_inventory_convertible(self) -> None:
        """Fully populated inventory → can convert."""
        evaluator = ConversionReadinessEvaluator()
        inv = ProjectInventory()

        # Simulate a fully-parsed DSN
        inv.dsn_internal = DSNInternalInventory(
            total_pages=3,
            pages_parsed=3,
            total_instances=42,
            instances_parsed=42,
            cache_entries=10,
            strlst_entries=200,
            has_root=True,
            has_views=True,
            has_pages=True,
            has_cache=True,
            has_library=True,
            has_hierarchy=True,
        )

        # Add a found DSN file
        inv.files["project.dsn"] = FileStatus(
            path=Path("project.dsn"),
            file_type="DSN",
            state=FileState.FOUND_OK,
            data_quality=0.95,
        )

        report = evaluator.evaluate(inv)
        assert report.logic_score > 0.5
        assert report.coordinate_score > 0.0
        assert report.can_convert or report.can_convert_with_degradation

    def test_four_scores_in_range(self) -> None:
        """All four scores are in [0.0, 1.0]."""
        evaluator = ConversionReadinessEvaluator()
        inv = ProjectInventory()
        inv.dsn_internal = DSNInternalInventory(
            total_pages=1,
            pages_parsed=1,
            cache_entries=1,
        )
        inv.files["test.dsn"] = FileStatus(
            path=Path("test.dsn"),
            file_type="DSN",
            state=FileState.FOUND_OK,
        )
        report = evaluator.evaluate(inv)
        for score in [report.logic_score, report.coordinate_score, report.matchability_score, report.symbol_score]:
            assert 0.0 <= score <= 1.0, f"Score {score} out of range"
