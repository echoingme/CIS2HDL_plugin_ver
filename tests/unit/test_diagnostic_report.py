"""Unit tests for DiagnosticReport data model."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from cis2hdl.core.diagnostics.diagnostic_report import (
    Severity,
    FileState,
    FileStatus,
    DiagnosisError,
    DiagnosticReport,
    ProjectInventory,
    DSNInternalInventory,
    ReadinessReport,
    ConversionReadinessEvaluator,
)


# ── DiagnosticReport Tests ─────────────────────────────────────────────────


class TestDiagnosticReport:
    """DiagnosticReport data model tests."""

    def test_empty_report(self) -> None:
        """Empty report has zero counts."""
        report = DiagnosticReport()
        assert report.error_count == 0
        assert report.warning_count == 0
        assert report.fatal_count == 0

    def test_report_with_errors(self) -> None:
        """Report correctly counts errors by severity."""
        report = DiagnosticReport()
        report.errors.append(
            DiagnosisError(code=1, severity=Severity.FATAL, category="FILE", message="DSN missing")
        )
        report.errors.append(
            DiagnosisError(code=3, severity=Severity.ERROR, category="FILE", message="OLB corrupt")
        )
        report.warnings.append(
            DiagnosisError(code=4, severity=Severity.WARNING, category="FILE", message="Old version")
        )

        assert report.fatal_count == 1
        assert report.error_count == 2
        assert report.warning_count == 1

    def test_json_serialization(self) -> None:
        """Report serializes to valid JSON."""
        inv = ProjectInventory()
        rp = ReadinessReport(
            can_convert=True,
            logic_score=0.9,
            coordinate_score=0.8,
            matchability_score=0.7,
            symbol_score=0.6,
            overall_score=0.75,
        )
        report = DiagnosticReport(inventory=inv, readiness=rp)
        json_str = report.to_json()
        assert "can_convert" in json_str
        assert "true" in json_str
        assert "logic" in json_str

    def test_summary_text(self) -> None:
        """Summary text includes key metrics."""
        rp = ReadinessReport(can_convert=True, overall_score=0.85)
        report = DiagnosticReport(readiness=rp)
        summary = report.to_summary_text()
        assert "READY" in summary
        assert "85%" in summary

    def test_errors_grouped_by_category(self) -> None:
        """all_errors_grouped groups by category."""
        report = DiagnosticReport()
        report.errors.append(
            DiagnosisError(code=1, severity=Severity.ERROR, category="FILE", message="e1")
        )
        report.errors.append(
            DiagnosisError(code=11, severity=Severity.ERROR, category="PARSE", message="e2")
        )
        report.warnings.append(
            DiagnosisError(code=21, severity=Severity.WARNING, category="NET", message="w1")
        )

        groups = report.all_errors_grouped()
        assert "FILE" in groups
        assert "PARSE" in groups
        assert "NET" in groups
        assert len(groups["FILE"]) == 1
        assert len(groups["PARSE"]) == 1
        assert len(groups["NET"]) == 1
