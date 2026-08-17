"""DiagnosticPipeline — six-stage diagnostic orchestration.

Orchestrates the full diagnostic flow:
  Stage 1: FileInventory — scan and classify input files
  Stage 2: ProjectFileValidator — three-layer file validation
  Stage 3: DependencyResolver — resolve OLB dependencies
  Stage 4: ConversionReadinessEvaluator — assess readiness
  Stage 5: ConversionQualityEstimator — four-dimensional quality scoring
  Stage 6: ErrorDiagnosisEngine — aggregate and diagnose all errors

Errors accumulate across stages; no stage failure blocks subsequent stages.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from .diagnostic_report import (
    DiagnosisError,
    DiagnosticReport,
    Severity,
)
from .file_inventory import FileInventory
from .file_validator import ProjectFileValidator, DependencyResolver
from .error_diagnosis import ErrorDiagnosisEngine
from .recovery import FileRecoveryStrategy
from .quality import ConversionQualityEstimator
from .olb_integrity import OLBIntegrityChecker

logger = logging.getLogger(__name__)

# ── Stage dispatch tables ────────────────────────────────────────────────

_STAGE_HANDLERS: dict[str, str] = {
    "file_inventory": "_run_file_inventory",
    "file_validation": "_run_file_validation",
    "dependency_resolution": "_run_dependency_resolution",
    "olb_integrity": "_run_olb_integrity",
    "recovery_evaluation": "_run_recovery_evaluation",
    "readiness": "_run_readiness",
    "quality": "_run_quality",
    "error_diagnosis": "_run_error_diagnosis",
}


def _make_project_inventory() -> Any:
    """Lazy-import factory for ProjectInventory fallback."""
    from .diagnostic_report import ProjectInventory
    return ProjectInventory()


def _make_readiness_report() -> Any:
    """Lazy-import factory for ReadinessReport fallback."""
    from .diagnostic_report import ReadinessReport
    return ReadinessReport()


def _make_quality_report() -> Any:
    """Lazy-import factory for QualityReport fallback."""
    from .quality import QualityReport
    return QualityReport()


_STAGE_FALLBACKS: dict[str, Callable[[DiagnosisError], Any]] = {
    "file_inventory": lambda _: _make_project_inventory(),
    "file_validation": lambda e: [e],
    "dependency_resolution": lambda e: ([], [e]),
    "recovery_evaluation": lambda _: [],
    "readiness": lambda _: _make_readiness_report(),
    "quality": lambda _: _make_quality_report(),
    "error_diagnosis": lambda _: DiagnosticReport(),
}


class DiagnosticPipeline:
    """Six-stage diagnostic pipeline for pre-conversion validation.

    Usage:
        pipeline = DiagnosticPipeline()
        report = pipeline.run([Path("project.dsn"), Path("lib.olb")])
        print(report.to_summary_text())

    The pipeline can also take DesignIR and MatchResult for quality estimation:
        pipeline.set_design(design)
        pipeline.set_matches(matches)
        report = pipeline.run(input_files)
    """

    def __init__(self) -> None:
        """Initialize all six stages."""
        self.file_inventory = FileInventory()
        self.file_validator = ProjectFileValidator()
        self.dep_resolver = DependencyResolver()
        self.olb_checker = OLBIntegrityChecker()
        self.readiness_evaluator = None  # Lazy import to avoid circular deps
        self.quality = ConversionQualityEstimator()
        self.error_engine = ErrorDiagnosisEngine()
        self.recovery_strategy = FileRecoveryStrategy()

        # Optional data for quality estimation
        self._design = None
        self._matches: list[Any] = []

        # Accumulated errors across stages
        self._all_errors: list[DiagnosisError] = []

    def set_design(self, design: Any) -> None:
        """Set the design IR for quality estimation (Stage 5).

        Args:
            design: DesignIR instance.
        """
        self._design = design

    def set_matches(self, matches: list[Any]) -> None:
        """Set match results for quality estimation (Stage 5).

        Args:
            matches: List of MatchResult instances.
        """
        self._matches = matches

    def run(self, input_files: list[Path]) -> DiagnosticReport:
        """Run the full six-stage diagnostic pipeline.

        Args:
            input_files: List of input file paths to validate.

        Returns:
            A complete DiagnosticReport with all findings.
        """
        self._all_errors = []
        logger.info("DiagnosticPipeline starting with %d input files", len(input_files))

        # ══════════════════════════════════════════════════════════════
        # Stage 1: File Inventory
        # ══════════════════════════════════════════════════════════════
        logger.info("Stage 1/6: FileInventory")
        inventory = self.run_stage("file_inventory", input_files)

        # ══════════════════════════════════════════════════════════════
        # Stage 2: File Validation (three layers)
        # ══════════════════════════════════════════════════════════════
        logger.info("Stage 2/6: ProjectFileValidator")
        validation_errors = self.run_stage("file_validation", inventory)
        self._all_errors.extend(validation_errors)
        inventory.errors.extend(validation_errors)

        # ══════════════════════════════════════════════════════════════
        # Stage 3: Dependency Resolution
        # ══════════════════════════════════════════════════════════════
        logger.info("Stage 3/6: DependencyResolver")
        missing_olbs, dep_errors = self.run_stage("dependency_resolution", inventory)
        self._all_errors.extend(dep_errors)
        inventory.errors.extend(dep_errors)

        # ══════════════════════════════════════════════════════════════
        # Stage 3.5: OLB Integrity (if OLB files present)
        # ══════════════════════════════════════════════════════════════
        olb_errors: list[DiagnosisError] = []
        for key, status in inventory.files.items():
            if status.file_type == "OLB" and status.state.value == "FOUND_OK":
                logger.info("Stage 3.5/6: OLBIntegrityChecker for %s", status.path.name)
                try:
                    olb_errs = self.olb_checker.check(status.path)
                    olb_errors.extend(olb_errs)
                    self._all_errors.extend(olb_errs)
                    inventory.errors.extend(olb_errs)
                except Exception as exc:
                    logger.warning("OLB integrity check failed for %s: %s", status.path.name, exc)

        # ══════════════════════════════════════════════════════════════
        # Stage 3.8: Recovery Evaluation (if applicable)
        # ══════════════════════════════════════════════════════════════
        recovery_paths = self.run_stage("recovery_evaluation", inventory)

        # ══════════════════════════════════════════════════════════════
        # Stage 4: Readiness Evaluation
        # ══════════════════════════════════════════════════════════════
        logger.info("Stage 4/6: ReadinessEvaluator")
        readiness_report = self.run_stage("readiness", inventory)

        # ══════════════════════════════════════════════════════════════
        # Stage 5: Quality Estimation
        # ══════════════════════════════════════════════════════════════
        logger.info("Stage 5/6: QualityEstimator")
        quality_report = self.run_stage("quality", inventory)

        # ══════════════════════════════════════════════════════════════
        # Stage 6: Error Diagnosis (aggregate everything)
        # ══════════════════════════════════════════════════════════════
        logger.info("Stage 6/6: ErrorDiagnosis")
        diagnostic_report = self.run_stage("error_diagnosis", inventory, readiness_report, quality_report)

        logger.info(
            "DiagnosticPipeline complete: %s",
            diagnostic_report.to_summary_text(),
        )
        return diagnostic_report

    def run_stage(self, stage_name: str, *args: Any) -> Any:
        """Run a single diagnostic stage by name.

        Args:
            stage_name: Stage identifier:
                "file_inventory", "file_validation", "dependency_resolution",
                "recovery_evaluation", "readiness", "quality", "error_diagnosis"
            *args: Stage-specific arguments.

        Returns:
            Stage-specific result.

        Raises:
            ValueError: If stage_name is unknown.
        """
        handler_name = _STAGE_HANDLERS.get(stage_name)
        if handler_name is None:
            raise ValueError(f"Unknown diagnostic stage: {stage_name}")
        try:
            return getattr(self, handler_name)(*args)
        except Exception as exc:
            logger.error(
                "Stage '%s' failed with exception: %s", stage_name, exc, exc_info=True
            )
            error = ErrorDiagnosisEngine.classify(exc)
            self._all_errors.append(error)
            return self._stage_fallback(stage_name, error)

    def _stage_fallback(self, stage_name: str, error: DiagnosisError) -> Any:
        """Return appropriate fallback value for a failed stage via dict dispatch.

        Args:
            stage_name: The stage that failed.
            error: The classified DiagnosisError.

        Returns:
            Stage-specific fallback value, or None if stage unknown.
        """
        factory = _STAGE_FALLBACKS.get(stage_name)
        if factory is not None:
            return factory(error)
        return None

    # ── Stage implementations ───────────────────────────────────────────

    def _run_file_inventory(self, input_files: list[Path]) -> Any:
        """Stage 1: Scan and classify input files."""
        from .diagnostic_report import ProjectInventory
        inventory = self.file_inventory.scan(input_files)

        # Also attempt DSN internal inventory if a DSN file is present
        for status in inventory.files.values():
            if status.file_type == "DSN" and status.state.value == "FOUND_OK":
                try:
                    from .file_inventory import DSNInternalInventoryBuilder
                    builder = DSNInternalInventoryBuilder()
                    inventory.dsn_internal = builder.build(status.path)
                except Exception as exc:
                    logger.warning("DSN internal inventory failed: %s", exc)
                break

        return inventory

    def _run_file_validation(self, inventory: Any) -> list[DiagnosisError]:
        """Stage 2: Three-layer file validation."""
        return self.file_validator.full_validate(inventory)

    def _run_dependency_resolution(self, inventory: Any) -> tuple[list[str], list[DiagnosisError]]:
        """Stage 3: Resolve OLB dependencies."""
        return self.dep_resolver.resolve_olb_dependencies(inventory)

    def _run_recovery_evaluation(self, inventory: Any) -> list[Any]:
        """Stage 3.5: Evaluate recovery paths."""
        return self.recovery_strategy.evaluate(inventory)

    def _run_readiness(self, inventory: Any) -> Any:
        """Stage 4: Evaluate conversion readiness."""
        from .diagnostic_report import ConversionReadinessEvaluator, ReadinessReport
        if self.readiness_evaluator is None:
            self.readiness_evaluator = ConversionReadinessEvaluator()
        return self.readiness_evaluator.evaluate(inventory)

    def _run_quality(self, inventory: Any) -> Any:
        """Stage 5: Estimate conversion quality."""
        if self._design is not None and self._matches:
            return self.quality.estimate(self._design, self._matches)
        else:
            logger.debug("No design/matches set — returning default QualityReport")
            from .quality import QualityReport as QR
            return QR()

    def _run_error_diagnosis(
        self,
        inventory: Any,
        readiness_report: Any,
        quality_report: Any,
    ) -> DiagnosticReport:
        """Stage 6: Aggregate and diagnose all errors."""
        # Aggregate all accumulated errors
        all_errors = list(self._all_errors)

        # Add inventory errors
        if hasattr(inventory, 'errors'):
            all_errors.extend(inventory.errors)

        # Diagnose
        report = self.error_engine.diagnose(all_errors)

        # Attach inventory and readiness
        report.inventory = inventory

        # Override readiness with quality scores if available
        if quality_report and hasattr(quality_report, 'overall_score'):
            report.readiness.overall_score = quality_report.overall_score
            report.readiness.logic_score = quality_report.logic_score
            report.readiness.coordinate_score = quality_report.coordinate_score
            report.readiness.matchability_score = quality_report.match_score
            report.readiness.symbol_score = quality_report.symbol_score

        # Add recovery suggestions
        recovery_suggestions = self.error_engine.suggest_recovery(report)
        for suggestion in recovery_suggestions:
            if suggestion not in report.readiness.suggestions:
                report.readiness.suggestions.append(suggestion)

        return report
