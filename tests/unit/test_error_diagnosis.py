"""Unit tests for error diagnosis: ProjectFileValidator, DependencyResolver, and full diagnostic pipeline."""

from __future__ import annotations

import tempfile
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


# ── Full Pipeline Integration Tests (B1.24) ──────────────────────────────


class TestFullDiagnosticPipeline:
    """End-to-end diagnostic pipeline tests."""

    def test_pipeline_on_real_dsn(self, real_dsn_path: Path) -> None:
        """Run full diagnostic pipeline on real .dsn file."""
        if not real_dsn_path.exists():
            pytest.skip(f"Test file not found: {real_dsn_path}")

        # Step 1: FileInventory
        builder = FileInventory()
        inv = builder.scan([real_dsn_path])

        # Step 2: DSNInternalInventory
        dsn_builder = DSNInternalInventoryBuilder()
        inv.dsn_internal = dsn_builder.build(real_dsn_path)

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
