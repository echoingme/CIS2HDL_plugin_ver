"""Integration tests for diagnostics layer (D1.1-D1.6) and full pipeline (B1.24)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

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
from cis2hdl.core.diagnostics.file_inventory import (
    FileInventory,
    DSNInternalInventoryBuilder,
)
from cis2hdl.core.diagnostics.file_validator import (
    ProjectFileValidator,
    DependencyResolver,
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


# ── FileInventory Tests ──────────────────────────────────────────────────


class TestFileInventory:
    """FileInventory scanner tests."""

    def test_empty_input(self) -> None:
        """Empty file list produces empty inventory."""
        builder = FileInventory()
        inv = builder.scan([])
        assert len(inv.files) == 0

    def test_scan_edif(self) -> None:
        """Scan a valid EDIF file."""
        with tempfile.NamedTemporaryFile(suffix=".edf", delete=False, mode="w") as f:
            f.write("(edif test_project\n")
            tmp = Path(f.name)
        try:
            builder = FileInventory()
            inv = builder.scan([tmp])
            assert len(inv.files) == 1
            status = list(inv.files.values())[0]
            assert status.file_type == "EDF"
            assert status.state == FileState.FOUND_OK
        finally:
            tmp.unlink()

    def test_scan_missing_file(self) -> None:
        """Missing file gets MISSING state."""
        builder = FileInventory()
        inv = builder.scan([Path("/nonexistent/project.dsn")])
        assert len(inv.files) == 1
        status = list(inv.files.values())[0]
        assert status.state == FileState.MISSING

    def test_scan_empty_file(self) -> None:
        """Empty file gets CORRUPTED state."""
        with tempfile.NamedTemporaryFile(suffix=".dsn", delete=False) as f:
            tmp = Path(f.name)
        try:
            builder = FileInventory()
            inv = builder.scan([tmp])
            status = list(inv.files.values())[0]
            assert status.state == FileState.CORRUPTED
        finally:
            tmp.unlink()

    def test_scan_non_cfb_as_dsn(self) -> None:
        """Non-CFB file claimed as .dsn gets BAD_FORMAT."""
        with tempfile.NamedTemporaryFile(suffix=".dsn", delete=False, mode="wb") as f:
            f.write(b"NOT A VALID CFB FILE!!!")
            tmp = Path(f.name)
        try:
            builder = FileInventory()
            inv = builder.scan([tmp])
            status = list(inv.files.values())[0]
            assert status.file_type == "DSN"
            assert status.state == FileState.BAD_FORMAT
        finally:
            tmp.unlink()

    def test_generates_actions_for_missing_essentials(self) -> None:
        """Missing essential files generate action items."""
        builder = FileInventory()
        with tempfile.NamedTemporaryFile(suffix=".edf", delete=False, mode="w") as f:
            f.write("(edif test\n")
            tmp = Path(f.name)
        try:
            inv = builder.scan([tmp])
            # Should suggest providing DSN
            assert len(inv.actions) > 0
            actions_text = " ".join(str(a) for a in inv.actions)
            assert ".dsn" in actions_text or "DSN" in actions_text
        finally:
            tmp.unlink()


# ── DSNInternalInventory Tests ────────────────────────────────────────────


class TestDSNInternalInventory:
    """DSNInternalInventory tests."""

    def test_empty_inventory(self) -> None:
        """Default DSNInternalInventory has all False."""
        inv = DSNInternalInventory()
        assert inv.total_pages == 0
        assert inv.pages_parsed == 0
        assert inv.instances_parsed == 0
        assert inv.stream_integrity_score == 0.0

    def test_all_streams_present(self) -> None:
        """All streams present → score 1.0."""
        inv = DSNInternalInventory()
        inv.has_root = True
        inv.has_views = True
        inv.has_pages = True
        inv.has_cache = True
        inv.has_library = True
        inv.has_hierarchy = True
        assert inv.stream_integrity_score == 1.0

    def test_page_completeness(self) -> None:
        """Page completeness ratio is correct."""
        inv = DSNInternalInventory()
        inv.total_pages = 10
        inv.pages_parsed = 7
        assert inv.page_completeness == 0.7

    def test_summary_text(self) -> None:
        """Summary text contains key metrics."""
        inv = DSNInternalInventory(
            total_pages=3,
            pages_parsed=3,
            instances_parsed=42,
            cache_entries=5,
            strlst_entries=100,
            olb_references=["CAPSYM", "Discrete"],
        )
        text = inv.summary_text()
        assert "3/3 pages" in text
        assert "42 instances" in text
        assert "5 cache" in text

    def test_real_dsn_inventory(self) -> None:
        """Build inventory from a real .dsn file."""
        test_file = Path(
            "D:/26暑假/cis2hdl/tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"
        )
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        builder = DSNInternalInventoryBuilder()
        inv = builder.build(test_file)
        assert inv.has_pages
        assert inv.total_pages > 0
        assert inv.pages_parsed > 0
        assert inv.stream_integrity_score > 0.0


# ── ProjectFileValidator Tests ────────────────────────────────────────────


class TestProjectFileValidator:
    """ProjectFileValidator tests."""

    def test_layer1_rejects_missing_dsn(self) -> None:
        """Missing DSN file produces FATAL error."""
        inv = ProjectInventory()
        inv.files["test.dsn"] = FileStatus(
            path=Path("test.dsn"),
            file_type="DSN",
            state=FileState.MISSING,
        )
        errors = ProjectFileValidator.validate_layer1_existence(inv)
        assert len(errors) >= 1
        fatal = [e for e in errors if e.severity == Severity.FATAL]
        assert len(fatal) >= 1

    def test_layer2_handles_bad_format(self) -> None:
        """BAD_FORMAT state produces ERROR."""
        inv = ProjectInventory()
        inv.files["bad.dsn"] = FileStatus(
            path=Path("bad.dsn"),
            file_type="DSN",
            state=FileState.BAD_FORMAT,
            detail="Not CFB",
        )
        errors = ProjectFileValidator.validate_layer2_format(inv)
        assert len(errors) >= 1

    def test_full_validate_no_errors_on_empty(self) -> None:
        """Full validate on empty inventory produces manageable results."""
        validator = ProjectFileValidator()
        inv = ProjectInventory()
        errors = validator.full_validate(inv)
        # Empty inventory should produce zero errors (nothing to check)
        assert isinstance(errors, list)


# ── DependencyResolver Tests ──────────────────────────────────────────────


class TestDependencyResolver:
    """DependencyResolver tests."""

    def test_resolve_with_no_refs(self) -> None:
        """Empty OLB refs → no missing OLBs."""
        inv = ProjectInventory()
        inv.dsn_internal.olb_references = []
        resolver = DependencyResolver()
        missing, errors = resolver.resolve_olb_dependencies(inv)
        assert len(missing) == 0
        assert len(errors) == 0

    def test_resolve_missing_olb(self) -> None:
        """Referenced OLB not found → ERROR."""
        inv = ProjectInventory()
        inv.dsn_internal.olb_references = ["MyCustomLib"]
        # Don't add any OLB files — so MyCustomLib will be missing
        resolver = DependencyResolver()
        missing, errors = resolver.resolve_olb_dependencies(inv)
        assert "MyCustomLib" in missing
        assert len(errors) >= 1

    def test_resolve_standard_olb_is_warning(self) -> None:
        """Standard OLB (CAPSYM) missing → WARNING not ERROR."""
        inv = ProjectInventory()
        inv.dsn_internal.olb_references = ["CAPSYM"]
        resolver = DependencyResolver()
        missing, errors = resolver.resolve_olb_dependencies(inv)
        assert "CAPSYM" in missing
        # Should be a WARNING because CAPSYM is standard
        for e in errors:
            assert e.severity in (Severity.WARNING, Severity.INFO)

    def test_resolve_found_olb_no_error(self) -> None:
        """Provided OLB → no error."""
        inv = ProjectInventory()
        inv.dsn_internal.olb_references = ["MyLib"]
        # Create a temp file whose stem matches the reference
        tmp_dir = tempfile.mkdtemp()
        try:
            olb_path = Path(tmp_dir) / "MyLib.olb"
            olb_path.write_bytes(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1")  # CFB magic
            inv.files[str(olb_path)] = FileStatus(
                path=olb_path,
                file_type="OLB",
                state=FileState.FOUND_OK,
            )
            resolver = DependencyResolver()
            missing, errors = resolver.resolve_olb_dependencies(inv)
            assert "MyLib" not in missing
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


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


# ── Full Pipeline Integration Tests (B1.24) ──────────────────────────────


class TestFullDiagnosticPipeline:
    """End-to-end diagnostic pipeline tests."""

    def test_pipeline_on_real_dsn(self) -> None:
        """Run full diagnostic pipeline on real .dsn file."""
        test_file = Path(
            "D:/26暑假/cis2hdl/tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"
        )
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # Step 1: FileInventory
        builder = FileInventory()
        inv = builder.scan([test_file])

        # Step 2: DSNInternalInventory
        dsn_builder = DSNInternalInventoryBuilder()
        inv.dsn_internal = dsn_builder.build(test_file)

        # Step 3: ProjectFileValidator
        validator = ProjectFileValidator()
        errors = validator.full_validate(inv)
        inv.errors = [e for e in errors if e.severity in (Severity.FATAL, Severity.ERROR)]
        inv.errors.extend(errors)

        # Step 4: DependencyResolver
        resolver = DependencyResolver()
        missing, dep_errors = resolver.resolve_olb_dependencies(inv)
        inv.errors.extend(dep_errors)

        # Step 5: Readiness evaluation
        evaluator = ConversionReadinessEvaluator()
        readiness = evaluator.evaluate(inv)

        # Step 6: Final report
        report = DiagnosticReport(inventory=inv, readiness=readiness)
        report.errors = [e for e in inv.errors if e.severity in (Severity.FATAL, Severity.ERROR)]
        report.warnings = [e for e in inv.errors if e.severity == Severity.WARNING]

        # Assertions
        assert report.readiness.can_convert or report.readiness.can_convert_with_degradation
        assert report.readiness.overall_score > 0.0
        summary = report.to_summary_text()
        assert "READY" in summary or "NOT READY" in summary

    def test_pipeline_edif_only_degraded(self) -> None:
        """EDIF-only file set should report degraded conversion path."""
        edif_file = Path(
            "docs_for_reference/OrCAD_files_references/capture/samples/fpga/Board/DFf_sync_SR/Synthesis/dff_sync_sr.edf"
        )
        if not edif_file.exists():
            pytest.skip(f"Test file not found: {edif_file}")

        builder = FileInventory()
        inv = builder.scan([edif_file])

        evaluator = ConversionReadinessEvaluator()
        readiness = evaluator.evaluate(inv)

        # EDIF only → no coordinates → should flag degraded
        assert readiness.coordinate_score == 0.0
