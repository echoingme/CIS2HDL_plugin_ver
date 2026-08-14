"""BatchConversionEngine — queue-based batch conversion for multiple projects.

Provides ProjectSpec, PerProjectReport, and BatchReport data classes along with
the BatchConversionEngine that reuses ConversionEngine.convert() for each project
in a sequential queue with progress callbacks and per-project error isolation.

Usage:
    engine = BatchConversionEngine()
    projects = [
        ProjectSpec(dsn_path=Path("proj1/proj1.dsn"), output_dir=Path("out1/")),
        ProjectSpec(dsn_path=Path("proj2/proj2.dsn"), output_dir=Path("out2/")),
    ]
    report = engine.batch_convert(projects)
    print(f"{report.success_count}/{report.projects_total} succeeded")
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .conversion_engine import ConversionEngine, ConversionReport

logger = logging.getLogger(__name__)


# =============================================================================
#  Data classes
# =============================================================================


@dataclass
class ProjectSpec:
    """Specification for a single project in a batch conversion queue.

    Attributes:
        dsn_path: Path to the input .dsn (or .edf) file.
        output_dir: Output directory for generated HDL files.
        hdl_lib_path: Optional path to HDL component library root.
                      If None, uses the global config default.
        olb_path: Optional path to an .olb library file to parse alongside
                  the .dsn for additional component definitions.
    """

    dsn_path: Path
    output_dir: Path
    hdl_lib_path: Optional[Path] = None
    olb_path: Optional[Path] = None


@dataclass
class PerProjectReport:
    """Report for a single project within a batch conversion.

    Attributes:
        project_name: Name of the project (derived from dsn_path stem).
        success: Whether the conversion succeeded without fatal errors.
        error_message: Error message if the conversion failed (empty on success).
        report: Full ConversionReport from ConversionEngine.convert().
                None if the conversion raised an unhandled exception.
    """

    project_name: str = ""
    success: bool = False
    error_message: str = ""
    report: Optional[ConversionReport] = None


@dataclass
class BatchReport:
    """Aggregated report for an entire batch conversion run.

    Attributes:
        projects_total: Total number of projects submitted for conversion.
        success_count: Number of projects that converted successfully.
        failed_count: Number of projects that failed (errors or exceptions).
        per_project_reports: Per-project reports in submission order.
        elapsed_seconds: Total wall-clock time for the batch run (set by engine).
    """

    projects_total: int = 0
    success_count: int = 0
    failed_count: int = 0
    per_project_reports: list[PerProjectReport] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def all_succeeded(self) -> bool:
        """True when every project in the batch succeeded."""
        return self.failed_count == 0 and self.projects_total > 0

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        return (
            f"BatchReport: {self.success_count}/{self.projects_total} succeeded, "
            f"{self.failed_count} failed"
        )

    # ------------------------------------------------------------------
    #  Batch diagnostics — quality trends & common errors
    # ------------------------------------------------------------------

    def quality_trend(self) -> dict:
        """Aggregate quality trends across all projects in the batch.

        Computes:
            - Average match rate across successful projects.
            - Average quality score.
            - Average pages, instances, nets.
            - Average warning count per project.

        Returns:
            A dictionary with aggregated quality statistics::

                {
                    "projects_total": int,
                    "projects_successful": int,
                    "projects_failed": int,
                    "avg_match_rate": float | None,      # 0.0–1.0
                    "avg_quality_score": float | None,    # 0.0–1.0
                    "avg_pages": float,
                    "avg_instances": float,
                    "avg_nets": float,
                    "avg_warnings": float,
                    "avg_output_files": float,
                }
        """
        from ..ir.match import MatchStrategy

        successful = [
            p for p in self.per_project_reports
            if p.success and p.report is not None
        ]

        match_rates: list[float] = []
        quality_scores: list[float] = []
        pages: list[int] = []
        instances: list[int] = []
        nets: list[int] = []
        warnings: list[int] = []
        output_files: list[int] = []

        for pr in successful:
            rpt = pr.report
            if rpt is None:
                continue

            # Match rate
            match_results = getattr(rpt, "match_results", None) or []
            if match_results:
                auto_matched = sum(
                    1 for m in match_results
                    if getattr(m, "strategy", None) != MatchStrategy.MANUAL
                )
                match_rates.append(auto_matched / len(match_results))

            # Quality score
            quality = getattr(rpt, "quality", None)
            if quality is not None and hasattr(quality, "overall_score"):
                quality_scores.append(float(quality.overall_score))

            # Stats
            pages.append(getattr(rpt, "pages", 0))
            instances.append(getattr(rpt, "instances", 0))
            nets.append(getattr(rpt, "nets", 0))
            warnings.append(len(getattr(rpt, "warnings", []) or []))
            output_files.append(len(getattr(rpt, "output_files", []) or []))

        def _safe_avg(values: list) -> Optional[float]:
            return sum(values) / len(values) if values else None

        return {
            "projects_total": self.projects_total,
            "projects_successful": len(successful),
            "projects_failed": self.failed_count,
            "avg_match_rate": _safe_avg(match_rates),
            "avg_quality_score": _safe_avg(quality_scores),
            "avg_pages": _safe_avg(pages) or 0.0,
            "avg_instances": _safe_avg(instances) or 0.0,
            "avg_nets": _safe_avg(nets) or 0.0,
            "avg_warnings": _safe_avg(warnings) or 0.0,
            "avg_output_files": _safe_avg(output_files) or 0.0,
        }

    def common_errors(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Return the most common error types across all projects.

        Scans all per-project reports and tallies error type keywords
        from both validation errors and string error messages.

        Args:
            top_n: Number of top error types to return (default: 5).

        Returns:
            List of (error_type, count) tuples, sorted descending.
        """
        counter: Counter[str] = Counter()

        for pr in self.per_project_reports:
            if pr.report is None:
                continue

            rpt = pr.report

            # Count error type codes from validation errors
            validation_errors = getattr(rpt, "validation_errors", None) or []
            for err in validation_errors:
                code_str = str(getattr(err, "code", "UNKNOWN"))
                counter[code_str] += 1

            # Count error type codes from stage errors
            stage_errors = getattr(rpt, "stage_errors", None) or {}
            for err_list in stage_errors.values():
                for err in err_list:
                    code_str = str(getattr(err, "code", "UNKNOWN"))
                    counter[code_str] += 1

            # Extract error types from string error messages
            string_errors = getattr(rpt, "errors", None) or []
            for err_text in string_errors:
                err_type = self._classify_error(str(err_text))
                counter[err_type] += 1

            # Count per-project failure if applicable
            if not pr.success and pr.error_message:
                err_type = self._classify_error(pr.error_message)
                counter[err_type] += 1

        return counter.most_common(top_n)

    @staticmethod
    def _classify_error(error_text: str) -> str:
        """Heuristically classify an error message into a type keyword.

        Args:
            error_text: The error message string.

        Returns:
            A short error type keyword (e.g., "PARSE_ERROR").
        """
        text_upper = error_text.upper()
        keywords = [
            ("FILE_NOT_FOUND", "FILE_NOT_FOUND"),
            ("PARSE_ERROR", "PARSE ERROR"),
            ("MATCH_ERROR", "MATCH"),
            ("VALIDATION_ERROR", "VALIDATION"),
            ("WRITE_ERROR", "WRITE"),
            ("DIRECTORY_ERROR", "DIRECTORY"),
            ("PERMISSION", "PERMISSION"),
            ("FATAL", "FATAL"),
            ("SCAN_ERROR", "SCAN"),
            ("GENERATION_ERROR", "GENERATION"),
            ("IO_ERROR", "IO ERROR"),
            ("MEMORY", "MEMORY"),
            ("TIMEOUT", "TIMEOUT"),
        ]
        for label, keyword in keywords:
            if keyword in text_upper:
                return label
        return "UNKNOWN"


# =============================================================================
#  Progress callback protocol
# =============================================================================

#: Called when starting a project: (project_name: str) -> None
OnProjectStart = Callable[[str], None]

#: Called when a project completes: (report: PerProjectReport) -> None
OnProjectComplete = Callable[[PerProjectReport], None]

#: Called to report overall batch progress: (current: int, total: int) -> None
OnBatchProgress = Callable[[int, int], None]


# =============================================================================
#  BatchConversionEngine
# =============================================================================


class BatchConversionEngine:
    """Sequential batch conversion engine for multiple CIS projects.

    Wraps a single ``ConversionEngine`` instance and calls its ``convert()``
    method for each ``ProjectSpec`` in the queue.  Individual project failures
    are isolated — they do not interrupt the remaining queue.

    Progress callbacks allow GUI integration (e.g., for a progress bar).

    Usage::

        engine = BatchConversionEngine()
        projects = [
            ProjectSpec(Path("a.dsn"), Path("out_a/")),
            ProjectSpec(Path("b.dsn"), Path("out_b/"), hdl_lib_path=Path("/lib")),
        ]
        batch_report = engine.batch_convert(
            projects,
            on_project_start=lambda name: print(f"Starting {name}"),
            on_project_complete=lambda r: print(f"  → {'OK' if r.success else 'FAIL'}"),
            on_batch_progress=lambda cur, tot: print(f"[{cur}/{tot}]"),
        )
    """

    def __init__(self) -> None:
        """Create a BatchConversionEngine with a shared ConversionEngine.

        Each batch_convert() call creates a fresh ConversionEngine internally
        to guarantee clean state between batches.
        """
        pass  # Engine is created lazily per batch_convert() call

    # ------------------------------------------------------------------
    #  batch_convert — primary entry point
    # ------------------------------------------------------------------

    def batch_convert(
        self,
        projects: list[ProjectSpec],
        on_project_start: Optional[OnProjectStart] = None,
        on_project_complete: Optional[OnProjectComplete] = None,
        on_batch_progress: Optional[OnBatchProgress] = None,
    ) -> BatchReport:
        """Convert a list of projects sequentially.

        Each project is converted via ``ConversionEngine.convert()``.
        If a single project raises an exception, the error is recorded
        in its ``PerProjectReport`` and the queue continues to the next
        project.

        Args:
            projects: List of ProjectSpec entries defining the batch.
            on_project_start: Optional callback invoked before each project.
            on_project_complete: Optional callback invoked after each project.
            on_batch_progress: Optional callback invoked with (current, total)
                               between projects.

        Returns:
            BatchReport with aggregated statistics and per-project details.
        """
        import time as _time

        total: int = len(projects)
        logger.info("Batch conversion started: %d project(s)", total)

        t_start: float = _time.monotonic()

        # Create a fresh engine for this batch
        engine: ConversionEngine = ConversionEngine()

        batch_report: BatchReport = BatchReport(projects_total=total)

        for idx, spec in enumerate(projects, start=1):
            per_project: PerProjectReport = PerProjectReport(
                project_name=spec.dsn_path.stem,
            )

            # ── Notify project start ────────────────────────────────
            if on_project_start is not None:
                try:
                    on_project_start(per_project.project_name)
                except Exception:
                    pass  # Never let callback exceptions break the queue

            # ── Notify batch progress ───────────────────────────────
            if on_batch_progress is not None:
                try:
                    on_batch_progress(idx, total)
                except Exception:
                    pass

            # ── Run conversion ──────────────────────────────────────
            try:
                logger.info(
                    "[%d/%d] Converting: %s → %s",
                    idx, total,
                    spec.dsn_path, spec.output_dir,
                )

                conversion_report: ConversionReport = engine.convert(
                    input_path=spec.dsn_path,
                    output_dir=spec.output_dir,
                    hdl_lib_path=spec.hdl_lib_path,
                )

                per_project.report = conversion_report

                if conversion_report.success:
                    per_project.success = True
                    batch_report.success_count += 1
                    logger.info(
                        "[%d/%d] %s: SUCCESS (%d output files)",
                        idx, total,
                        per_project.project_name,
                        len(conversion_report.output_files),
                    )
                else:
                    per_project.success = False
                    per_project.error_message = (
                        f"{len(conversion_report.errors)} error(s)"
                    )
                    batch_report.failed_count += 1
                    logger.warning(
                        "[%d/%d] %s: FAILED — %s",
                        idx, total,
                        per_project.project_name,
                        per_project.error_message,
                    )

            except Exception as exc:
                per_project.success = False
                per_project.error_message = str(exc)
                batch_report.failed_count += 1
                logger.exception(
                    "[%d/%d] %s: EXCEPTION — %s",
                    idx, total,
                    per_project.project_name,
                    exc,
                )

            # ── Store per-project report ────────────────────────────
            batch_report.per_project_reports.append(per_project)

            # ── Notify project complete ─────────────────────────────
            if on_project_complete is not None:
                try:
                    on_project_complete(per_project)
                except Exception:
                    pass

        # ── Finalise ────────────────────────────────────────────────
        t_end: float = _time.monotonic()
        batch_report.elapsed_seconds = round(t_end - t_start, 3)

        logger.info(
            "Batch conversion finished: %s (%.1fs)",
            batch_report.summary(),
            batch_report.elapsed_seconds,
        )
        return batch_report

    # ------------------------------------------------------------------
    #  Convenience: validate project specs without converting
    # ------------------------------------------------------------------

    @staticmethod
    def validate_specs(projects: list[ProjectSpec]) -> list[str]:
        """Validate all project specs and return a list of error messages.

        Does NOT perform conversion — only checks that all specified
        paths exist and are readable.

        Args:
            projects: List of ProjectSpec entries to validate.

        Returns:
            List of error message strings (empty if all specs are valid).
        """
        errors: list[str] = []

        for idx, spec in enumerate(projects, start=1):
            if not spec.dsn_path.exists():
                errors.append(
                    f"Project {idx} ('{spec.dsn_path}'): "
                    f"DSN file does not exist"
                )
            if spec.hdl_lib_path is not None and not spec.hdl_lib_path.exists():
                errors.append(
                    f"Project {idx} ('{spec.dsn_path}'): "
                    f"HDL library path '{spec.hdl_lib_path}' does not exist"
                )
            if spec.olb_path is not None and not spec.olb_path.exists():
                errors.append(
                    f"Project {idx} ('{spec.dsn_path}'): "
                    f"OLB file '{spec.olb_path}' does not exist"
                )

        return errors
