"""ConversionEngine — six-stage conversion pipeline controller.

Phase II full pipeline:
    Stage 1: Diagnose   — DiagnosticPipeline.run()  → DiagnosticReport
    Stage 2: Parse      — ParserRegistry             → DesignIR
    Stage 3: Scan       — HDLLibScanner.scan()       → ComponentDB
    Stage 4: Match      — MatcherPipeline.run_batch()→ list[MatchResult]
    Stage 5: Validate   — ValidatorRegistry          → list[DiagnosisError]
    Stage 6: Generate   — WriterRegistry             → output files

Also performs post-generation quality estimation via ConversionQualityEstimator.

Usage:
    engine = ConversionEngine()
    # Full pipeline
    report = engine.convert(Path("design.dsn"), Path("output/"))
    # Or with explicit HDL lib
    report = engine.convert(Path("design.dsn"), Path("output/"),
                            hdl_lib_path=Path("/hdl_lib"))
"""

from __future__ import annotations

import logging
import re
import shutil as _shutil
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..config import config as cfg
from ..db.component_db import ComponentDB
from ..writer.error_logger import ConversionLogger
from ..pipeline_config import PipelineConfig
from ...plugins.context import ConversionContext
from ...plugins.manager import build_plugin_manager
from .plugin_host import PluginHost
from ..diagnostics import (
    DiagnosisError,
    DiagnosticPipeline,
    DiagnosticReport,
    ConversionQualityEstimator,
    ConversionReadinessEvaluator,
    QualityReport,
    Severity,
)
from ..ir.component import ComponentDef, ComponentInstanceIR, PinDef
from ..ir.design import DesignIR, PageIR
from ..ir.match import MatchResult, MatchStrategy
from ..matcher import MatcherPipeline, ManualMatchResolver
from ..parser.base import ParserRegistry
from ..parser.edif_parser import EDIFParser
from ..parser.dsn.dsn_parser import DSNParser
from ..parser.olb.olb_parser import OLBParser
from ..parser.hdl_scanner import HDLLibScanner
from ..parser.cross_ref_parser import CrossRefEntry, CrossRefParser
from ..parser.component_catalog import ComponentCatalog
from ..validator import ValidatorRegistry, PinValidator, NetNameValidator, PowerPinValidator
from ..writer.base import WriterRegistry
from ..writer.cpm_writer import CPMWriter
from ..writer.cdslib_writer import CDSLibWriter
from ..writer.csa_writer import CSAWriter
from ..writer.output_manager import OutputManager
from ..writer.sch_writer import SCHWriter
from ..writer.scr_writer import ScrWriter
from ..writer.xcon_writer import XconWriter

logger = logging.getLogger(__name__)


# =============================================================================
#  Progress callback protocol
# =============================================================================

#: Progress callback signature: (stage_name: str, progress_pct: float, message: str) -> None
ProgressCallback = Callable[[str, float, str], None]


# =============================================================================
#  _Countable — thin wrapper for registries that need count()
# =============================================================================


class _Countable:
    """Adds a ``count()`` method to class-level registries that only have
    internal dicts (``_parsers`` / ``_writers`` / ``_validators``).

    Used so that ``engine.parser_registry.count()`` works without modifying
    the original registry classes (which may be owned by other tasks).
    """

    __slots__ = ("_reg", "_attr")

    def __init__(self, registry_cls: type, internal_attr: str) -> None:
        self._reg = registry_cls
        self._attr = internal_attr

    def count(self) -> int:
        """Return the number of registered items."""
        return len(getattr(self._reg, self._attr, {}))

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attribute lookups to the underlying registry."""
        return getattr(self._reg, name)


# =============================================================================
#  ConversionReport
# =============================================================================


@dataclass
class ConversionReport:
    """Summary of a complete six-stage conversion operation.

    Attributes:
        project_name: Name of the converted project.
        pages: Number of schematic pages.
        instances: Total component instances across all pages.
        nets: Total nets across all pages.
        output_files: Paths to all generated output files.
        errors: Human-readable error messages (FATAL/ERROR).
        warnings: Human-readable warning messages.
        diagnostic_report: Full diagnostic report from Stage 1.
        match_results: All match results from Stage 4.
        validation_errors: All validation errors from Stage 5.
        quality: Quality estimation report (post-generation).
        manual_matches: Match results requiring manual review.
        stage_errors: Per-stage accumulated DiagnosisError lists.
        hdl_components_scanned: Number of HDL components found by scanner.
    """

    project_name: str = ""
    pages: int = 0
    instances: int = 0
    nets: int = 0
    output_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Phase II additions
    diagnostic_report: Optional[DiagnosticReport] = None
    match_results: list[MatchResult] = field(default_factory=list)
    validation_errors: list[DiagnosisError] = field(default_factory=list)
    quality: Optional[QualityReport] = None
    manual_matches: list[MatchResult] = field(default_factory=list)
    stage_errors: dict[str, list[DiagnosisError]] = field(default_factory=dict)
    hdl_components_scanned: int = 0
    # Phase XII R8: default fallback component per type, built from the
    # scanned HDL ComponentDB (type → {value, footprint, jedec, package_type}).
    # Rendered as a compact table in the HTML report.
    fallback_table: dict[str, dict[str, str]] = field(default_factory=dict)
    # Performance timing (populated when benchmark mode is enabled)
    stage_timings: dict[str, float] = field(default_factory=dict)
    total_elapsed: float = 0.0

    @property
    def success(self) -> bool:
        """True when there are zero fatal/error-level issues."""
        return len(self.errors) == 0

    @property
    def has_fatal(self) -> bool:
        """True when at least one stage reported a FATAL error."""
        for err_list in self.stage_errors.values():
            for err in err_list:
                if err.severity == Severity.FATAL:
                    return True
        if self.diagnostic_report is not None:
            if self.diagnostic_report.fatal_count > 0:
                return True
        return False

    def _aggregate_errors(self) -> None:
        """Move DiagnosisError entries into .errors / .warnings string lists."""
        for err_list in self.stage_errors.values():
            for err in err_list:
                if err.severity in (Severity.FATAL, Severity.ERROR):
                    self.errors.append(str(err))
                else:
                    self.warnings.append(str(err))

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED ({len(self.errors)} errors)"
        parts = [
            f"ConversionReport[{status}]",
            f"project='{self.project_name}'",
            f"pages={self.pages} instances={self.instances} nets={self.nets}",
            f"outputs={len(self.output_files)}",
        ]
        if self.match_results:
            matched = sum(
                1 for m in self.match_results
                if m.strategy != MatchStrategy.MANUAL
            )
            parts.append(f"matched={matched}/{len(self.match_results)}")
        if self.quality is not None:
            parts.append(f"quality={self.quality.overall_score:.0%}")
        return " ".join(parts)

    def benchmark_report(self) -> str:
        """Generate a detailed performance benchmark report.

        Returns:
            Multi-line string with per-stage timings and total elapsed time.
        """
        if not self.stage_timings:
            return "No benchmark data available."

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("PERFORMANCE BENCHMARK REPORT")
        lines.append("=" * 60)
        total: float = self.total_elapsed if self.total_elapsed > 0 else 1e-9

        stage_order: list[str] = [
            "diagnose", "parse", "scan", "match", "validate", "generate",
        ]
        for stage_name in stage_order:
            elapsed = self.stage_timings.get(stage_name, 0.0)
            pct = elapsed / total * 100
            bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
            lines.append(f"  {stage_name:<10} {elapsed:>8.3f}s ({pct:>5.1f}%) {bar}")

        lines.append("-" * 60)
        lines.append(f"  {'TOTAL':<10} {total:>8.3f}s")
        lines.append("=" * 60)

        # Identify slowest stage
        if self.stage_timings:
            slowest = max(self.stage_timings, key=self.stage_timings.get)
            slowest_time = self.stage_timings[slowest]
            lines.append(f"  Slowest stage: '{slowest}' ({slowest_time:.3f}s, {slowest_time/total*100:.1f}%)")
        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
#  ConversionEngine
# =============================================================================

def _bootstrap_parsers() -> None:
    """Register all available parsers if not already registered."""
    if not ParserRegistry._parsers:
        ParserRegistry.register(EDIFParser())
        ParserRegistry.register(DSNParser())
        ParserRegistry.register(OLBParser())


def _bootstrap_writers() -> None:
    """Register all available writers if not already registered."""
    if not WriterRegistry._writers:
        WriterRegistry.register(CPMWriter())
        WriterRegistry.register(CDSLibWriter())
        WriterRegistry.register(SCHWriter())
        WriterRegistry.register(CSAWriter())
        WriterRegistry.register(XconWriter())


def _bootstrap_validators() -> None:
    """Register all available validators if not already registered."""
    if ValidatorRegistry.count() == 0:
        ValidatorRegistry.register(PinValidator())
        ValidatorRegistry.register(NetNameValidator())
        ValidatorRegistry.register(PowerPinValidator())


def _bootstrap_all() -> None:
    """Run all bootstrap registrations."""
    _bootstrap_parsers()
    _bootstrap_writers()
    _bootstrap_validators()


# Run bootstrap at module import time
_bootstrap_all()


# =============================================================================
#  ConversionEngine
# =============================================================================


class ConversionEngine:
    """Six-stage conversion pipeline: Diagnose → Parse → Scan → Match → Validate → Generate.

    The engine integrates all Phase I and Phase II modules into a single
    unified pipeline.  Each stage is exposed as a public method so callers
    (GUI, CLI, tests) can run stages individually or call ``convert()``
    for the full pipeline.

    Usage::

        engine = ConversionEngine()
        report = engine.convert(Path("design.dsn"), Path("output/"))

        # With progress callback (for GUI QThread):
        def on_progress(stage, pct, msg):
            print(f"[{stage}] {pct:.0%} — {msg}")
        report = engine.convert(
            Path("design.dsn"), Path("output/"),
            hdl_lib_path=Path("/hdl_lib"),
            progress_callback=on_progress,
        )
    """

    def __init__(
        self,
        plugin_manager: Optional[Any] = None,
        pipeline_cfg: Optional[PipelineConfig] = None,
    ) -> None:
        # ── S2 plugin 模式（None = legacy 模式，默认等价 FR9） ────
        self._pm = plugin_manager
        """PluginManager | None；None = legacy 模式（默认，929 等价）。"""
        self._pipeline_cfg = pipeline_cfg
        self._host = PluginHost(self)
        """钩子调用器（plugin_host.py）。"""

        # ── Phase I registries (wrapped for count() support) ──────
        self.parser_registry = _Countable(ParserRegistry, "_parsers")
        self.writer_registry = _Countable(WriterRegistry, "_writers")
        self.diagnostic_pipeline = DiagnosticPipeline()

        # ── Phase II components ────────────────────────────────────
        self.matcher = MatcherPipeline()
        self._manual_resolver = ManualMatchResolver()
        self.validator_registry = _Countable(ValidatorRegistry, "_validators")

        # ── Quality estimator (used post-generation) ───────────────
        self._quality_estimator = ConversionQualityEstimator()

        # ── Cached state (populated during pipeline execution) ─────
        self._hdl_db: Optional[ComponentDB] = None

    # ═══════════════════════════════════════════════════════════════════
    #  Stage 1: Diagnose
    # ═══════════════════════════════════════════════════════════════════

    def diagnose(self, input_files: list[Path]) -> DiagnosticReport:
        """Run the six-stage diagnostic pipeline on the given input files.

        Args:
            input_files: List of input file paths (e.g., [project.dsn, lib.olb]).

        Returns:
            A complete DiagnosticReport with all findings.
        """
        logger.info("Stage 1/6: Diagnose — %d input file(s)", len(input_files))
        report = self.diagnostic_pipeline.run(input_files)
        logger.info("Diagnose complete: %s", report.to_summary_text())
        return report

    # ═══════════════════════════════════════════════════════════════════
    #  Stage 2: Parse
    # ═══════════════════════════════════════════════════════════════════

    def parse(self, input_path: Path) -> DesignIR:
        """Parse an input file into a DesignIR using the appropriate parser.

        Args:
            input_path: Path to the input file (.dsn or .edf).

        Returns:
            A fully populated DesignIR instance.

        Raises:
            KeyError: If no parser is registered for the file extension.
            Exception: If parsing fails (wrapped and re-raised).
        """
        logger.info("Stage 2/6: Parse — %s", input_path)
        parser = ParserRegistry.get_for_file(input_path)
        design: DesignIR = parser.parse(input_path)
        logger.info(
            "Parse complete: project='%s', pages=%d, instances=%d, nets=%d",
            design.project_name or input_path.stem,
            len(design.pages),
            sum(len(p.instances) for p in design.pages),
            sum(len(p.nets) for p in design.pages),
        )
        return design

    # ═══════════════════════════════════════════════════════════════════
    #  Stage 3: HDL Library Scan
    # ═══════════════════════════════════════════════════════════════════

    def scan_hdl_library(self, lib_path: Optional[Path] = None) -> ComponentDB:
        """Scan the HDL component library and build a ComponentDB.

        If *lib_path* is not provided, uses the path from the global Config
        singleton (``config.hdl_lib.hdl_lib_path``).

        Args:
            lib_path: Root directory of the HDL component library.

        Returns:
            ComponentDB containing all discovered HDL components.

        Raises:
            FileNotFoundError: If the library path does not exist.
            NotADirectoryError: If the library path is not a directory.
        """
        if lib_path is None:
            hdl_lib_path_str = cfg.hdl_lib.hdl_lib_path
            if not hdl_lib_path_str:
                raise FileNotFoundError(
                    "HDL library path is not configured. "
                    "Set config.hdl_lib.hdl_lib_path or pass lib_path explicitly."
                )
            lib_path = Path(hdl_lib_path_str)

        logger.info("Stage 3/6: Scan HDL Library — %s", lib_path)

        scanner = HDLLibScanner(
            chips_encoding=cfg.hdl_lib.chips_prt_encoding,
            symbol_encoding=cfg.hdl_lib.symbol_css_encoding,
            ptf_encoding=cfg.hdl_lib.part_ptf_encoding,
            recursive=cfg.hdl_lib.recursive_scan,
            exclude_dirs=list(cfg.hdl_lib.exclude_dirs),
        )
        db = scanner.scan(lib_path)
        self._hdl_db = db

        stats = scanner.stats()
        logger.info(
            "Scan complete: %d components indexed (%d dirs scanned)",
            stats["total_components_found"],
            stats["total_dirs_scanned"],
        )
        return db

    # ═══════════════════════════════════════════════════════════════════
    #  Stage 4: Component Matching
    # ═══════════════════════════════════════════════════════════════════

    def match(
        self,
        design: DesignIR,
        hdl_db: ComponentDB,
        cross_ref_map: Optional[dict] = None,
        cis_components: Optional[list[ComponentDef]] = None,
    ) -> list[MatchResult]:
        """Run the matching pipeline for all CIS components.

        Extracts unique component definitions from the DesignIR (or uses
        the pre-extracted ``cis_components`` list when provided) and
        matches each against the HDL component database.

        Args:
            design: The parsed DesignIR containing CIS component definitions.
            hdl_db: The HDL ComponentDB from ``scan_hdl_library()``.
            cross_ref_map: Optional refdes→CrossRefEntry map for enriching
                component definitions with real refdes and values.
            cis_components: Optional pre-extracted ComponentDef list.
                When provided, skips the DesignIR extraction step.

        Returns:
            List of MatchResult, one per unique CIS component.
        """
        logger.info("Stage 4/6: Match — %d HDL candidates available", len(hdl_db))

        # Extract unique CIS ComponentDef objects from the design
        if cis_components is None:
            cis_components = self._extract_cis_components(design, cross_ref_map)

        if not cis_components:
            logger.warning("No CIS components to match — design may be empty")
            return []

        logger.info("Matching %d unique CIS component(s) against HDL library", len(cis_components))

        # Run batch matching
        results = self.matcher.run_batch(cis_components, hdl_db)

        # Log summary
        matched = sum(1 for r in results if r.strategy != MatchStrategy.MANUAL)
        manual = sum(1 for r in results if r.strategy == MatchStrategy.MANUAL)
        logger.info(
            "Match complete: %d matched, %d need manual review (total %d)",
            matched, manual, len(results),
        )
        return results

    # ═══════════════════════════════════════════════════════════════════
    #  Stage 5: Validate
    # ═══════════════════════════════════════════════════════════════════

    def validate(
        self,
        design: DesignIR,
        matches: list[MatchResult],
    ) -> list[DiagnosisError]:
        """Run all validators against every match result.

        Validators are executed in priority order. Each validator's
        ``can_validate()`` is checked before running ``validate()``.

        Args:
            design: The parsed DesignIR for context.
            matches: List of MatchResult entries from Stage 4.

        Returns:
            Aggregated list of all DiagnosisError entries from all validators.
        """
        logger.info("Stage 5/6: Validate — %d match(es) to validate", len(matches))

        if not matches:
            logger.info("No matches to validate")
            return []

        errors = ValidatorRegistry.run_all_batch(matches, design)

        # Log summary by severity
        fatal = sum(1 for e in errors if e.severity == Severity.FATAL)
        err = sum(1 for e in errors if e.severity == Severity.ERROR)
        warn = sum(1 for e in errors if e.severity == Severity.WARNING)
        logger.info(
            "Validate complete: %d FATAL, %d ERROR, %d WARNING",
            fatal, err, warn,
        )
        return errors

    # ═══════════════════════════════════════════════════════════════════
    #  Stage 6: Generate
    # ═══════════════════════════════════════════════════════════════════

    def generate(
        self,
        design: DesignIR,
        matches: list[MatchResult],
        output_dir: Path,
    ) -> ConversionReport:
        """Generate HDL output files using Cadence DEHDL directory structure.

        Uses OutputManager for proper Cadence DEHDL Project Manager layout:
            output_root/<cell>.cpm              ← Project Manager file
            output_root/cds.lib                 ← Library definitions
            output_root/temp/                   ← Temp directory
            output_root/worklib/<cell>/sch_1/pageN.csa   ← Page files (CSA native)
            output_root/worklib/<cell>/sch_1/<cell>.con  ← Constraint file
            output_root/worklib/<cell>/sch_1/module_order.dat ← Module order

        Args:
            design: The parsed DesignIR.
            matches: Match results (used for component library references).
            output_dir: Output root directory.

        Returns:
            ConversionReport with output file paths and any generation errors.
        """
        logger.info("Stage 6/6: Generate → %s", output_dir)
        report = ConversionReport()

        output_dir.mkdir(parents=True, exist_ok=True)

        project_name = getattr(design, "project_name", "") or "project"

        # ── Create OutputManager ────────────────────────────────────
        output_mgr = OutputManager(
            project_name=project_name,
            output_root=output_dir,
        )
        report.project_name = output_mgr.cell_name

        # ── Setup directory structure ───────────────────────────────
        try:
            output_mgr.setup_directory_structure()
        except Exception as exc:
            msg = f"Directory setup error: {exc}"
            report.errors.append(msg)
            logger.exception("Failed to create output directory structure")
            return report

        # ── Copy HDL library into output ─────────────────────────────
        hdl_lib_src = getattr(self, '_last_hdl_lib_path', None)
        if hdl_lib_src and Path(hdl_lib_src).exists():
            hdl_dst = output_dir / "hdl_lib"
            if not hdl_dst.exists():
                try:
                    _shutil.copytree(hdl_lib_src, hdl_dst, symlinks=True)
                    logger.info("Copied HDL library: %d files",
                                sum(1 for _ in hdl_dst.rglob("*")))
                except Exception as exc:
                    logger.warning("Could not copy hdl_lib: %s", exc)
        elif not (output_dir / "hdl_lib").exists():
            report.warnings.append(
                "No HDL library copied — cds.lib references ./hdl_lib "
                "which must exist alongside the project."
            )

        # ── Project-level files (.cpm, cds.lib) ─────────────────────
        try:
            proj_files = output_mgr.generate_all_project_files()
            report.output_files.extend(str(p) for p in proj_files)
            logger.debug("Project files generated: %d file(s)", len(proj_files))
        except Exception as exc:
            msg = f"Project file error: {exc}"
            report.errors.append(msg)
            logger.exception("Failed to generate project files")

        # ── Phase XI P0-B/P0-C: shared connectivity-model writers ──
        # con / xcon (design-level), csv / cpc (page-level), csa (page
        # native with LASTPIN/WIRE/DOT/SIG_NAME).  All writers consume the
        # single DesignConnectivity model so identifiers never drift.
        try:
            from ..writer.connectivity_model import ConnectivityModelBuilder
            from ..writer.con_writer import ConWriter
            from ..writer.xcon_writer import XconWriter
            from ..writer.csv_writer import PageCsvWriter
            from ..writer.cpc_writer import CpcWriter
            from ..writer.csa_writer import CSAWriter

            conn = ConnectivityModelBuilder(
                design,
                matches=matches,
                hdl_db=self._hdl_db,
                hdl_lib_name=cfg.output.hdl_lib_dir or "hdl_lib",
            ).build()

            csa_writer = CSAWriter(
                hdl_lib_name=cfg.output.hdl_lib_dir or "hdl_lib",
                hdl_lib_path=self._last_hdl_lib_path,
                routing_cfg=cfg.routing,
            )
            if self._hdl_db:
                csa_writer._component_db = self._hdl_db
            if hasattr(csa_writer, "set_matches"):
                csa_writer.set_matches(matches)
            # Phase XVIII R4: CrossRef CSV 属性注入（缺失时回退 props）。
            if hasattr(csa_writer, "set_crossref_map"):
                csa_writer.set_crossref_map(
                    getattr(self, "_last_cross_ref_map", None) or {}
                )

            p0_files: list[Path] = []
            p0_files.extend(ConWriter().write_with_manager(conn, output_mgr))
            p0_files.extend(XconWriter().write_with_manager(conn, output_mgr))
            p0_files.extend(PageCsvWriter().write_all_with_manager(conn, output_mgr))
            p0_files.extend(CpcWriter().write_all_with_manager(conn, output_mgr))
            if cfg.app.emit_csa_wires:
                p0_files.extend(csa_writer.write_all_with_conn(conn, output_mgr))
            else:
                from ..writer.csa_writer import CSAWriter as _LegacyCSA
                _legacy = _LegacyCSA()
                for _page in design.pages:
                    p0_files.extend(_legacy.write_with_manager(_page, output_mgr))
            report.output_files.extend(str(p) for p in p0_files)
            logger.info(
                "P0 writers: %d file(s) (con/xcon/csv/cpc/csa), "
                "conn model: %d cells / %d nets / %d instances / %d pins",
                len(p0_files),
                conn.cell_count, conn.net_count,
                conn.instance_count, conn.pin_count,
            )
            ConversionLogger.log_info(
                "GEN",
                f"连通性模型: {conn.cell_count} cells, {conn.net_count} nets, "
                f"{conn.instance_count} instances, {conn.pin_count} pins",
            )
        except Exception as exc:
            msg = f"P0 writer error: {exc}"
            report.errors.append(msg)
            logger.exception("Phase XI P0 writers failed")

        # ── Remaining cell-level support files ─────────────────────
        # (.dcf, module_order.dat, page.map, master.tag — the new
        # ConWriter/XconWriter/CpcWriter already wrote con/xcon/cpc.)
        try:
            page_count = len(design.pages)
            cell_files: list[Path] = [
                output_mgr.write_dcf(output_mgr.cell_name),
                output_mgr.write_module_order(
                    output_mgr.library_alias, output_mgr.cell_name,
                ),
                output_mgr.write_page_map(
                    pages=design.pages, num_pages=page_count,
                ),
                output_mgr._write_master_tag(page_count),
            ]
            report.output_files.extend(str(p) for p in cell_files)
        except Exception as exc:
            msg = f"Cell support files error: {exc}"
            report.errors.append(msg)
            logger.exception("Cell support files generation failed")

        # ── .scr placement scripts (DEHDL console interaction) ──────
        try:
            # Build match lookup: source_library_id → MatchResult
            scr_match_lookup: dict[str, object] = {}
            for m in matches:
                sid = getattr(m, 'source_library_id', '')
                if sid:
                    scr_match_lookup[sid] = m
            scr_writer = ScrWriter()
            scr_files = scr_writer.write_all(
                pages=design.pages,
                sch_dir=output_mgr.sch_dir,
                match_lookup=scr_match_lookup,
            )
            report.output_files.extend(str(p) for p in scr_files)
            logger.info("Generated %d .scr file(s)", len(scr_files))
        except Exception as exc:
            msg = f".scr writer error: {exc}"
            report.errors.append(msg)
            logger.exception(".scr writer failed")

        logger.info(
            "Generate complete: %d output file(s), %d error(s)",
            len(report.output_files), len(report.errors),
        )

        # v0.8.2: Deduplicate output_files (same .csa may be written
        # multiple times for xref.* dynamically-created pages)
        report.output_files = list(dict.fromkeys(report.output_files))
        return report

    # ═══════════════════════════════════════════════════════════════════
    #  Stage runner helper
    # ═══════════════════════════════════════════════════════════════════

    def _run_stage(
        self,
        stage_name: str,
        fn: Callable,
        *args: Any,
        progress_callback: Optional[ProgressCallback] = None,
        fatal_errors: Optional[list] = None,
        stage_errors: Optional[dict] = None,
    ) -> Any:
        """Execute a single pipeline stage with unified error handling.

        Args:
            stage_name: Stage name (e.g., ``"diagnose"``, ``"parse"``).
            fn: Stage handler function to call.
            *args: Positional arguments forwarded to ``fn``.
            progress_callback: Optional progress callback for GUI updates.
            fatal_errors: Optional list to append error message strings to.
            stage_errors: Optional dict to append ``DiagnosisError`` entries
                to, keyed by ``stage_name``.

        Returns:
            The return value of ``fn(*args)`` on success, or ``None`` on failure.
        """
        try:
            return fn(*args)
        except Exception as exc:
            msg = f"{stage_name.capitalize()} stage error: {exc}"
            logger.exception("%s stage failed", stage_name)

            ConversionLogger.log_error(
                stage_name.upper(), msg,
                file_path=str(args[0]) if args else "",
            )

            if fatal_errors is not None:
                fatal_errors.append(msg)

            if stage_errors is not None:
                err = DiagnosisError(
                    code=0,
                    severity=Severity.ERROR,
                    category="ENGINE",
                    message=msg,
                )
                stage_errors.setdefault(stage_name, []).append(err)

            if progress_callback is not None:
                try:
                    progress_callback(
                        stage_name, 0.0,
                        f"{stage_name.capitalize()} FAILED: {exc}",
                    )
                except Exception:
                    pass

            return None

    # ═══════════════════════════════════════════════════════════════════
    #  Pipeline stage methods
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _report_progress(
        pc: Optional[ProgressCallback],
        stage_name: str,
        pct: float,
        msg: str,
    ) -> None:
        """Safe progress callback wrapper — never lets a callback crash
        the pipeline."""
        if pc is not None:
            try:
                pc(stage_name, pct, msg)
            except Exception:
                pass

    def _stage_diagnose(
        self,
        input_path: Path,
        report: ConversionReport,
        pc: Optional[ProgressCallback],
    ) -> bool:
        """Stage 1: Diagnose input files.

        Returns:
            True to continue pipeline, False to abort.
        """
        self._report_progress(pc, "diagnose", 0.0, "Starting diagnostic analysis…")
        diagnostic_report = self._run_stage(
            "diagnose", self.diagnose, [input_path],
            progress_callback=pc,
            stage_errors=report.stage_errors,
        )
        if diagnostic_report is None:
            report._aggregate_errors()
            self._report_progress(pc, "diagnose", 0.15, "Diagnose FAILED")
            return False

        report.diagnostic_report = diagnostic_report
        report.stage_errors.setdefault("diagnose", []).extend(
            diagnostic_report.errors
        )
        report.stage_errors.setdefault("diagnose", []).extend(
            diagnostic_report.warnings
        )

        if diagnostic_report.fatal_count > 0:
            fatal_msgs = [
                str(e) for e in diagnostic_report.errors
                if e.severity == Severity.FATAL
            ]
            report.errors.extend(fatal_msgs)
            report._aggregate_errors()
            self._report_progress(
                pc, "diagnose", 0.15,
                f"ABORTED: {diagnostic_report.fatal_count} FATAL error(s)",
            )
            logger.warning(
                "Conversion aborted at Stage 1: %d FATAL error(s)",
                diagnostic_report.fatal_count,
            )
            return False

        self._report_progress(pc, "diagnose", 0.15, "Diagnostic analysis complete")
        return True

    def _stage_parse(
        self,
        input_path: Path,
        report: ConversionReport,
        pc: Optional[ProgressCallback],
    ) -> Optional["DesignIR"]:
        """Stage 2: Parse input file → DesignIR.

        Returns:
            DesignIR on success, None to abort.
        """
        self._report_progress(pc, "parse", 0.15, "Parsing input file…")
        design = self._run_stage(
            "parse", self.parse, input_path,
            progress_callback=pc,
            stage_errors=report.stage_errors,
        )
        if design is None:
            report._aggregate_errors()
            self._report_progress(pc, "parse", 0.30, "Parse FAILED")
            return None

        report.project_name = design.project_name or input_path.stem
        report.pages = len(design.pages)  # initial DSN pages
        report.instances = sum(len(p.instances) for p in design.pages)
        report.nets = sum(len(p.nets) for p in design.pages)
        self._report_progress(
            pc, "parse", 0.30,
            f"Parsed: {report.pages} page(s), {report.instances} instance(s)",
        )
        return design

    def _stage_scan(
        self,
        hdl_lib_path: Optional[Path],
        report: ConversionReport,
        pc: Optional[ProgressCallback],
        extra_lib_paths: Optional[list[Path]] = None,
    ) -> ComponentDB:
        """Stage 3: Scan HDL component library → ComponentDB.

        Phase XIV D4 方案 B：``--extra-hdl-lib`` 挂载额外库目录 ——
        ``_stage_scan`` 支持多根目录，主库与额外库各自扫描后合并
        （practice hdl_lib 格式与 fixtures 一致，SymbolCssParser 直接兼容）。

        Returns:
            ComponentDB (merged; may be empty if library unavailable).
        """
        self._report_progress(pc, "scan", 0.30, "Scanning HDL component library…")

        effective_lib_path = hdl_lib_path
        if effective_lib_path is None:
            hdl_path_str = cfg.hdl_lib.hdl_lib_path
            if hdl_path_str:
                effective_lib_path = Path(hdl_path_str)

        if effective_lib_path is not None and effective_lib_path.exists():
            hdl_db = self._run_stage(
                "scan", self.scan_hdl_library, effective_lib_path,
                progress_callback=pc,
                stage_errors=report.stage_errors,
            )
            if hdl_db is None:
                hdl_db = ComponentDB()
                self._report_progress(pc, "scan", 0.45, "Scan FAILED")
            else:
                report.hdl_components_scanned = len(hdl_db)
                self._report_progress(
                    pc, "scan", 0.45,
                    f"Scanned: {len(hdl_db)} HDL component(s)",
                )
        else:
            logger.warning("No HDL library path configured or path not found")
            hdl_db = ComponentDB()
            report.warnings.append(
                "HDL library not available — skipping component matching. "
                "Configure hdl_lib_path in Settings."
            )
            self._report_progress(pc, "scan", 0.45,
                                  "HDL library not available — skipping")

        # ── Phase XIV D4: extra HDL library roots (方案 B) ────────
        for extra in extra_lib_paths or []:
            if extra is None or not Path(extra).exists():
                report.warnings.append(
                    f"Extra HDL library not found: {extra} — skipped"
                )
                continue
            try:
                extra_db = self._run_stage(
                    "scan", self.scan_hdl_library, Path(extra),
                    progress_callback=pc,
                    stage_errors=report.stage_errors,
                )
                if extra_db is None:
                    continue
                merged = 0
                for comp in extra_db.list_all():
                    try:
                        hdl_db.add(comp)
                        merged += 1
                    except Exception:
                        continue
                report.hdl_components_scanned = len(hdl_db)
                logger.info(
                    "Extra HDL library %s: %d component(s) merged",
                    extra, merged,
                )
            except Exception as exc:
                logger.warning("Extra HDL library scan failed %s: %s", extra, exc)

        self._hdl_db = hdl_db
        return hdl_db

    def _stage_match(
        self,
        design: "DesignIR",
        hdl_db: ComponentDB,
        report: ConversionReport,
        pc: Optional[ProgressCallback],
        cross_ref_map: Optional[dict] = None,
    ) -> list:
        """Stage 4: Match CIS components → HDL components.

        Uses ComponentCatalog (from CrossRef CSV) as the primary source
        for component identity.  Falls back to _extract_cis_components
        when no catalog is available.

        Returns:
            List of MatchResult objects.
        """
        self._report_progress(pc, "match", 0.45, "Matching components…")
        if len(hdl_db) > 0:
            # ── v0.5.0: Use ComponentCatalog when available ──────────
            catalog = design.metadata.get("component_catalog")
            if catalog is not None:
                cis_components = catalog.to_component_defs()
                logger.info(
                    "Using ComponentCatalog: %d source components from catalog",
                    len(cis_components),
                )
                # v2.0: Inject PST JEDEC into ComponentDef extra_data for PassiveMatcher
                # (Catalog doesn't carry JEDEC; must read from PST-enriched instances)
                _jedec_injected = 0
                for _comp in cis_components:
                    for _pg in design.pages:
                        for _inst in _pg.instances:
                            if _inst.refdes.upper() == _comp.library_id.upper():
                                _ij = _inst.extra_data.get("pst_jedec_type", "") if hasattr(_inst, "extra_data") else ""
                                if _ij:
                                    _comp.extra_data["jedec_type"] = _ij
                                    _jedec_injected += 1
                                break
                        else:
                            continue
                        break
                if _jedec_injected:
                    logger.info("v2.0: Injected PST JEDEC into %d ComponentDefs (of %d)",
                        _jedec_injected, len(cis_components))
            else:
                cis_components = self._extract_cis_components(design, cross_ref_map)

            match_results = self._run_stage(
                "match", self.match, design, hdl_db,
                cross_ref_map, cis_components,
                progress_callback=pc,
                stage_errors=report.stage_errors,
            )
            if match_results is None:
                match_results = []
                self._report_progress(pc, "match", 0.70, "Match FAILED")
            else:
                report.match_results = match_results
                report.manual_matches = [
                    m for m in match_results
                    if m.strategy == MatchStrategy.MANUAL
                ]
                auto_matched = sum(
                    1 for m in match_results
                    if m.strategy != MatchStrategy.MANUAL
                )
                self._report_progress(
                    pc, "match", 0.70,
                    f"Matched: {auto_matched}/{len(match_results)}",
                )
        else:
            catalog = design.metadata.get("component_catalog")
            if catalog is not None:
                cis_components = catalog.to_component_defs()
            else:
                cis_components = self._extract_cis_components(design, cross_ref_map)
            match_results = [
                MatchResult(
                    confidence=0.0,
                    strategy=MatchStrategy.MANUAL,
                    source_library_id=c.library_id,
                    candidates=[],
                    warnings=["HDL library not available for matching"],
                )
                for c in cis_components
            ]
            report.match_results = match_results
            report.manual_matches = [
                m for m in match_results
                if m.strategy == MatchStrategy.MANUAL
            ]
            self._report_progress(
                pc, "match", 0.70,
                f"Manual: {len(match_results)} component(s)",
            )
        return match_results

    # ── Phase XII R2: power symbol match results ─────────────────────

    #: Power symbol library_id (uppercase, as stored on instances) →
    #: HDL library directory used as the deterministic target.
    _POWER_TARGET_MAP: dict[str, str] = {
        "GND": "gnd_power",
        "DGND": "gnd_power",
        "GND_POWER": "gnd_power",
        "GND_SIGNAL": "gnd_power",
        "GND_EARTH": "gnd_earth",
        "GND_CHASSIS": "gnd_earth",
        "VCC_CIRCLE": "vcc_circle",
        "VCC_BAR": "vcc_circle",
        "VCC_ARROW": "vcc_circle",
    }

    @staticmethod
    def _is_power_symbol(library_id: str) -> bool:
        """Return True when a library_id is a CIS power symbol cell."""
        return (library_id or "").lower() in {
            "gnd", "dgnd", "vcc_circle", "gnd_power", "gnd_earth",
            "gnd_signal", "vcc_bar", "vcc_arrow", "gnd_chassis",
        }

    @staticmethod
    def _append_power_symbol_matches(
        design: "DesignIR",
        match_results: list,
    ) -> int:
        """Append deterministic MatchResults for power symbol instances.

        Power symbols (GND/DGND/VCC_CIRCLE/…) come from EDIF
        ``portImplementation`` blocks, are preserved across the catalog
        rebuild, but are NOT part of the ComponentCatalog — so the
        matching pipeline never assigns them a MatchResult.  Without a
        result they previously triggered INFO_LOSS warnings and dragged
        down match coverage.

        One MatchResult is generated per unique power library_id that
        actually appears in the design (the mapping CSV is keyed by
        ``source_library_id`` == instance library_id).

        Args:
            design: The DesignIR (post-catalog-rebuild).
            match_results: List being mutated in place (keeps
                ``report.match_results`` in sync).

        Returns:
            Number of power symbol results appended.
        """
        seen: set[str] = {getattr(m, "source_library_id", "") for m in match_results}
        appended: int = 0
        for page in design.pages:
            for inst in page.instances:
                lib_id: str = getattr(inst, "library_id", "") or ""
                if not lib_id or not ConversionEngine._is_power_symbol(lib_id):
                    continue
                key: str = lib_id.upper()
                if key in seen:
                    continue
                target: str = ConversionEngine._POWER_TARGET_MAP.get(key, "gnd_power")
                seen.add(key)
                match_results.append(MatchResult(
                    confidence=1.0,
                    strategy=MatchStrategy.POWER_SYMBOL,
                    source_library_id=key,
                    target_library_id=target,
                    phase1_type="power",
                    phase1_prior_conf=1.0,
                    phase2_within_conf=1.0,
                    phase2_strategy_detail="power_symbol✅",
                    cis_value="",
                    extra_data={
                        "hdl_value": key,
                        "hdl_footprint": target,
                        "hdl_jedec": target,
                        "hdl_package_type": target,
                        "hdl_category": "power",
                        "hdl_pin_count": 1,
                        "selected_primitive": target,
                        "_source_value": "",
                    },
                ))
                appended += 1
        if appended:
            logger.info(
                "R2: appended %d power symbol MatchResult(s) "
                "(total match_results=%d)",
                appended, len(match_results),
            )
        return appended

    # ── Phase XII R8: default fallback table ─────────────────────────

    @staticmethod
    def _build_fallback_table(hdl_db: ComponentDB) -> dict[str, dict[str, str]]:
        """Build type → default fallback component map from the HDL DB.

        For each component library directory found in the library (keyed
        by the directory name — e.g. ``capacitor``, ``resistor`` — so the
        report matches the type names used by PassiveMatcher), the FIRST
        candidate's first part.ptf row supplies the default value /
        footprint / jedec / package_type that PassiveMatcher L5
        (prefix-only fallback) selects when no value matches.

        Args:
            hdl_db: The scanned HDL ComponentDB.

        Returns:
            Dict mapping type/directory name → {value, footprint, jedec,
            package_type}.  Sorted by type name for stable rendering.
        """
        from collections import defaultdict

        by_type: dict[str, list[ComponentDef]] = defaultdict(list)
        for comp in hdl_db.list_all():
            type_name = ""
            src_file = getattr(comp, "source_file", "") or ""
            if src_file:
                type_name = Path(src_file).name.strip()
            if not type_name:
                type_name = (getattr(comp, "category", "") or "other").strip()
            by_type[type_name].append(comp)

        table: dict[str, dict[str, str]] = {}
        for type_name in sorted(by_type):
            comps = by_type[type_name]
            if not comps:
                continue
            first = comps[0]
            ptf_rows: list[dict] = (
                first.extra_data.get("ptf_rows", [])
                if hasattr(first, "extra_data") else []
            )
            row0: dict = ptf_rows[0] if ptf_rows else {}
            table[type_name] = {
                "value": str(row0.get("value", "") or getattr(first, "value", "") or ""),
                "footprint": str(
                    row0.get("package_type", "")
                    or row0.get("jedec_type", "")
                    or getattr(first, "footprint", "")
                    or ""
                ),
                "jedec": str(row0.get("jedec_type", "") or ""),
                "package_type": str(row0.get("package_type", "") or ""),
            }
        return table

    def _stage_validate(
        self,
        design: "DesignIR",
        match_results: list,
        report: ConversionReport,
        pc: Optional[ProgressCallback],
    ) -> bool:
        """Stage 5: Validate match results.

        Returns:
            True to continue to generation, False to abort.
        """
        self._report_progress(pc, "validate", 0.70, "Validating matches…")
        validation_errors = self._run_stage(
            "validate", self.validate, design, match_results,
            progress_callback=pc,
            stage_errors=report.stage_errors,
        )
        if validation_errors is None:
            validation_errors = []
            self._report_progress(pc, "validate", 0.85, "Validate FAILED")
        else:
            report.validation_errors = validation_errors
            report.stage_errors.setdefault("validate", []).extend(
                validation_errors
            )

            fatal_errs = [
                e for e in validation_errors
                if e.severity == Severity.FATAL
            ]
            err_errs = [
                e for e in validation_errors
                if e.severity == Severity.ERROR
            ]
            warn_errs = [
                e for e in validation_errors
                if e.severity == Severity.WARNING
            ]

            # ── Log validation results to ConversionLogger ──────────
            if validation_errors:
                error_count = sum(
                    1 for v in validation_errors
                    if hasattr(v, 'severity') and v.severity == 'ERROR'
                )
                total_warn_count = sum(
                    1 for v in validation_errors
                    if hasattr(v, 'severity') and v.severity == 'WARNING'
                )
                if error_count > 0 or total_warn_count > 0:
                    ConversionLogger.log_warning(
                        "VALIDATE",
                        f"校验发现 {error_count} 个错误, {total_warn_count} 个警告",
                    )

            for e in fatal_errs:
                report.errors.append(str(e))
            for e in err_errs:
                report.errors.append(str(e))
            for e in warn_errs:
                report.warnings.append(str(e))

            self._report_progress(
                pc, "validate", 0.85,
                f"Validated: {len(fatal_errs)} FATAL, "
                f"{len(err_errs)} ERROR, {len(warn_errs)} WARNING",
            )

            if fatal_errs:
                logger.warning(
                    "Generation skipped due to %d FATAL validation error(s)",
                    len(fatal_errs),
                )
                report._aggregate_errors()
                self._report_progress(
                    pc, "validate", 0.85,
                    "ABORTED: FATAL validation errors",
                )
                return False
        return True

    def _stage_generate(
        self,
        design: "DesignIR",
        match_results: list,
        output_dir: Path,
        report: ConversionReport,
        pc: Optional[ProgressCallback],
        effective_lib_path: Optional[Path],
    ) -> None:
        """Stage 6: Generate HDL output files + post-processing.

        Post-generation steps:
          - Quality estimation via ConversionQualityEstimator.
          - HTML report export.
        """
        self._report_progress(pc, "generate", 0.85, "Generating HDL output files…")
        self._last_hdl_lib_path = effective_lib_path
        gen_report = self._run_stage(
            "generate", self.generate, design, match_results, output_dir,
            progress_callback=pc,
            stage_errors=report.stage_errors,
        )
        if gen_report is not None:
            report.output_files = gen_report.output_files
            report.errors.extend(gen_report.errors)
            report.warnings.extend(gen_report.warnings)
            self._report_progress(
                pc, "generate", 0.98,
                f"Generated: {len(report.output_files)} file(s)",
            )
        else:
            self._report_progress(pc, "generate", 0.98, "Generate FAILED")

        # ── Quality Estimation ─────────────────────────────────────
        try:
            quality_report = self._quality_estimator.estimate(
                design, match_results,
            )
            report.quality = quality_report
            logger.info("Quality: %s", quality_report.summary())
        except Exception as exc:
            logger.warning("Quality estimation failed: %s", exc)

        # ── v0.7.2: Update readiness scores with actual pipeline data ──
        # Override Stage 1 DSN-based metrics with Catalog/matching results.
        if report.diagnostic_report is not None:
            _rd = report.diagnostic_report.readiness
            _rd.logic_score = 1.0        # Catalog = full identity
            _rd.coordinate_score = 1.0    # CrossRef CSV = 100% coords
            _total = len(match_results) if match_results else 1
            _rd.matchability_score = sum(
                1 for m in match_results if m.confidence and m.confidence >= 0.5
            ) / _total if match_results else 0.0
            _rd.symbol_score = 0.5        # HDL symbols (not original CIS)
            _rd.overall_score = (
                _rd.logic_score * 0.40 + _rd.coordinate_score * 0.25
                + _rd.matchability_score * 0.20 + _rd.symbol_score * 0.15
            )
            # Status update based on new score
            _rd.can_convert = _rd.overall_score >= 0.75
            _rd.can_convert_with_degradation = _rd.overall_score >= 0.40

        # ── Phase XII R8: default fallback component table ─────────
        # Built from the scanned HDL ComponentDB (first candidate per
        # type) so the HTML report can document what value/footprint a
        # component falls back to when its exact value is not in the lib.
        try:
            report.fallback_table = self._build_fallback_table(self._hdl_db)
        except Exception as _fb_exc:
            logger.warning("Fallback table build failed: %s", _fb_exc)

        # ── HTML Report Export ─────────────────────────────────────
        try:
            from ..diagnostics.report_gen import StructuredReportGenerator
            html_gen = StructuredReportGenerator()
            html_path = html_gen.generate_html_file(report, output_dir)
            if html_path is not None:
                report.output_files.append(str(html_path))
                logger.info("HTML report: %s", html_path)
        except Exception as exc:
            logger.warning("HTML report generation failed: %s", exc)

    # ── Phase XIV D3/D4: manual matches + power IC auto-match ────────

    def _apply_phase14_matching(
        self,
        design: "DesignIR",
        hdl_db: ComponentDB,
        match_results: list,
        report: ConversionReport,
        input_path: Path,
    ) -> None:
        """Phase XIV 匹配增强（D4 电源芯片自动匹配 → D3 人工匹配覆盖）。

        注入点：``_append_power_symbol_matches`` 之后、Validate 之前。
        两个模块正交、可独立开关（``power_ic.enabled`` /
        ``routing.manual_matches``）；失败只记 warning，不中断转换。

        Args:
            design: DesignIR。
            hdl_db: HDL ComponentDB。
            match_results: 匹配结果（原地覆盖）。
            report: ConversionReport（warnings/output_files 累加）。
            input_path: 输入文件路径（定位同目录 pstxnet.dat）。
        """
        inst_lookup: dict[str, Any] = {}
        for page in design.pages:
            for inst in page.instances:
                inst_lookup[(getattr(inst, "refdes", "") or "").upper()] = inst

        # ── D4: power IC auto-match ────────────────────────────────
        if cfg.routing.power_ic.enabled:
            try:
                from ..matcher.power_ic_scorer import (
                    PowerCandidateScorer,
                    extract_pin_names_from_pstxnet,
                )
                scorer = PowerCandidateScorer(
                    Path(cfg.routing.power_ic.config_file),
                )
                pstxnet_path = input_path.parent / "pstxnet.dat"
                by_src: dict[str, Any] = {}
                for m in match_results:
                    sid = getattr(m, "source_library_id", "") or ""
                    if sid:
                        by_src[sid.upper()] = m
                applied = 0
                for key, mr in by_src.items():
                    if getattr(mr, "strategy", None) == MatchStrategy.POWER_SYMBOL:
                        continue
                    inst = inst_lookup.get(key)
                    if inst is None:
                        continue
                    pin_conns = getattr(inst, "pin_connections", {}) or {}
                    pin_count = len(pin_conns)
                    if pin_count == 0:
                        pin_count = int(
                            (mr.extra_data or {}).get("hdl_pin_count", 0) or 0
                        )
                    if pin_count == 0 or pin_count > scorer.max_pin_count:
                        continue
                    pin_names: list[str] = []
                    if pstxnet_path.exists():
                        pin_names = extract_pin_names_from_pstxnet(
                            pstxnet_path, getattr(inst, "refdes", "") or "",
                        )
                    nets = [str(v) for v in pin_conns.values() if v]
                    best = scorer.best_auto(pin_count, pin_names, nets)
                    if best is None:
                        continue
                    target = None
                    try:
                        target = hdl_db.get_by_library_id(best["library_id"])
                    except Exception:
                        target = None
                    if target is None:
                        continue
                    mr.target_library_id = str(target.library_id)
                    mr.confidence = float(best["score"])
                    mr.strategy = MatchStrategy.POWER_IC_AUTO
                    mr.extra_data["manual_section"] = int(best["section"])
                    mr.extra_data["power_ic_candidate"] = str(best["library_id"])
                    mr.extra_data["hdl_pin_count"] = pin_count
                    inst.section = int(best["section"])
                    mr.warnings.append(
                        f"power_ic auto → {best['library_id']}/"
                        f"sym_{best['section']} ({best['reason']})"
                    )
                    applied += 1
                if applied:
                    logger.info(
                        "D4 power_ic: %d instance(s) auto-matched", applied,
                    )
            except Exception as exc:
                logger.warning("D4 power_ic matching failed: %s", exc)

        # ── D3: manual matches override（Phase XVII M8 统一 chip_config）──
        # 主入口 --chip-config（v2.0）；--manual-matches 保留为别名（v1.0
        # 兼容）；两者同时存在时 v2.0 覆盖 v1.0 同 refdes（用户 D7）。
        _chip_config = cfg.routing.chip_config
        _legacy = cfg.routing.manual_matches
        if _chip_config or _legacy:
            try:
                from ..matcher.manual_matches import (
                    ManualMatchesConfig,
                    apply_manual_matches,
                    load_merged,
                )
                manual = load_merged(
                    Path(_chip_config) if _chip_config else None,
                    Path(_legacy) if _legacy else None,
                )
                match_results, warnings = apply_manual_matches(
                    match_results, manual, hdl_db, design,
                )
                for w in warnings:
                    report.warnings.append(f"manual_matches: {w}")
                    logger.warning("manual_matches: %s", w)
            except Exception as exc:
                logger.warning("manual_matches load/apply failed: %s", exc)

        # ── export-unmatched（D3 工作流配套） ─────────────────────
        if cfg.routing.export_unmatched:
            try:
                from ..matcher.manual_matches import export_unmatched
                from ..matcher.power_ic_scorer import PowerCandidateScorer
                scorer = None
                if cfg.routing.power_ic.enabled:
                    scorer = PowerCandidateScorer(
                        Path(cfg.routing.power_ic.config_file),
                    )
                data = export_unmatched(
                    match_results, hdl_db, design.pages, scorer,
                )
                out = Path(cfg.routing.export_unmatched)
                out.parent.mkdir(parents=True, exist_ok=True)
                import yaml as _yaml
                out.write_text(
                    _yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                report.output_files.append(str(out))
                logger.info("export_unmatched → %s", out)
            except Exception as exc:
                logger.warning("export_unmatched failed: %s", exc)

        # ── 同步 report（覆盖后的 match_results） ─────────────────
        report.match_results = match_results
        report.manual_matches = [
            m for m in match_results if m.strategy == MatchStrategy.MANUAL
        ]

    # ═══════════════════════════════════════════════════════════════════
    #  Full Pipeline
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _prefer_edif_sibling(input_path: Path) -> Optional[Path]:
        """P0-D2: return the same-name ``.edf``/``.EDF`` sibling of a ``.dsn``.

        OrCAD projects ship a ``.dsn`` plus a same-name EDIF export
        (``.edf``/``.EDF``).  Since the DSN RTL variant parses to 0 real
        instances and thousands of fake nets (misparsed port names /
        raw binary — e.g. HG5015: 3717 garbage nets), the EDIF export is
        the preferred schematic source.  The DSN file itself is never
        consumed as a component/net source.

        Args:
            input_path: The path the user passed to ``convert()``.

        Returns:
            The sibling EDIF path if found, else ``None`` (DSN fallback).
        """
        if input_path.suffix.lower() != ".dsn":
            return None
        for suffix in (".EDF", ".edf"):
            candidate = input_path.with_suffix(suffix)
            if candidate.exists():
                return candidate
        return None

    def _legacy_load_input(
        self,
        input_path: Path,
        report: ConversionReport,
        pc: Optional[ProgressCallback],
    ) -> Optional[DesignIR]:
        """S2/S3 legacy fallback：原 convert() Stage 2 内联解析+增强块。

        S3 重构：拆分为子步骤方法（_resolve_parse_path / _log_parse_statistics /
        _load_cross_ref_csv / _load_pst_files / _rebuild_from_catalog），
        行为与 S2 逐字节等价（FR9）。input 插件复用同一批子步骤，保证
        plugin 模式接管路径与 legacy 全链路等价。
        """
        # ── Phase XI P0-D2: prefer EDIF over DSN as component source ──
        parse_path = self._resolve_parse_path(input_path)

        design = self._stage_parse(parse_path, report, pc)
        if design is None:
            return None

        # ── Page parse statistics ───────────────────────────────────
        self._log_parse_statistics(design)

        # ── Stage 2.5: Build ComponentCatalog from CrossRef CSV ──────
        cross_ref_map, catalog = self._load_cross_ref_csv(design, input_path)

        # ── v0.8.0: Stage 2.3 — Parse PST netlist files ────────────
        self._load_pst_files(design, input_path)

        # ── v0.5.0: Build DesignIR instances from ComponentCatalog ──
        self._rebuild_from_catalog(design, report)

        # S2：暴露 cross_ref_map/catalog 给 convert() 的 match 钩子/薄包装
        # （原为 parse 块局部变量，提取后需经 self 传递）。
        self._last_cross_ref_map = cross_ref_map
        self._last_catalog = catalog
        return design

    def _resolve_parse_path(self, input_path: Path) -> Path:
        """S3：P0-D2 解析路径决策（原 _legacy_load_input L1560-1583 纯搬移）。

        ``.dsn`` 且 DSN 元件源禁用（默认）→ 优先同名的 ``.EDF/.edf``
        兄弟文件；无兄弟文件 → 原样返回（DSN fallback，ParserRegistry 按
        扩展名选解析器）。
        """
        # ── Phase XI P0-D2: prefer EDIF over DSN as component source ──
        # When the user input is a .dsn and a same-name .EDF/.edf sibling
        # exists AND DSN components are disabled (default), parse the EDIF:
        # EDIF provides pages/components/wires; pstxnet.dat stays the
        # authoritative pin→net injection (Stage 5.5b below).  The DSN
        # RTL variant yields 0 real instances / 3717 fake nets, so it is
        # useless as a component source.
        parse_path = input_path
        if (
            input_path.suffix.lower() == ".dsn"
            and not cfg.app.use_dsn_components
        ):
            _preferred_edf = self._prefer_edif_sibling(input_path)
            if _preferred_edf is not None:
                parse_path = _preferred_edf
                logger.info(
                    "P0-D2: DSN component source disabled — parsing %s "
                    "(pstxnet.dat remains the pin→net authority)",
                    _preferred_edf.name,
                )
                ConversionLogger.log_info(
                    "SOURCE",
                    f"DSN 元件源已禁用，改用 EDIF 解析: {_preferred_edf.name}",
                )

        return parse_path

    def _log_parse_statistics(self, design: "DesignIR") -> None:
        """S3：页解析统计（原 _legacy_load_input L1589-1601 纯搬移）。"""
        # ── Page parse statistics ───────────────────────────────────
        for p in design.pages:
            inst_count = len(p.instances)
            net_count = len(p.nets)
            garbled = sum(
                1 for i in p.instances
                if not (i.refdes.isascii() and len(i.refdes) <= 60)
            )
            if garbled > 0:
                ConversionLogger.log_warning(
                    "PARSE",
                    f"Page {p.page_id}: {garbled}/{inst_count} 实例 refdes 异常",
                )


    def _load_cross_ref_csv(
        self,
        design: "DesignIR",
        input_path: Path,
    ) -> tuple[dict, Optional["ComponentCatalog"]]:
        """S3：CrossRef CSV → ComponentCatalog + 坐标注入（原 L1603-1671 纯搬移）。

        返回 ``(cross_ref_map, catalog)``；无 CSV → ``({}, None)``。
        ``design.metadata["component_catalog"]`` 与 ``self._last_cross_ref_map``
        副作用与原实现一致。
        """
        # ── Stage 2.5: Build ComponentCatalog from CrossRef CSV ──────
        # CrossRef CSV is now the **primary data source** for component
        # identity (refdes, value, coordinates, page assignment).
        # DSN is only trusted for pin_connections (network topology).
        #
        # v0.5.0: ComponentCatalog is the single source of truth.
        cross_ref_map: dict[str, CrossRefEntry] = {}
        catalog: Optional[ComponentCatalog] = None
        _csv_path: Optional[Path] = input_path.with_suffix('.CSV')
        if not _csv_path.exists():
            _csv_path = input_path.with_suffix('.csv')
        if _csv_path is not None and _csv_path.exists():
            try:
                catalog = ComponentCatalog.from_cross_ref(_csv_path)
                design.metadata["component_catalog"] = catalog

                # Also build legacy cross_ref_map for backward compatibility
                _xref_parser = CrossRefParser()
                cross_ref_map = _xref_parser.parse_file(_csv_path)
                # Phase XVIII R4: CSA 属性块注入的数据源（writer 复用）。
                self._last_cross_ref_map = cross_ref_map

                logger.info(
                    "ComponentCatalog: %d entries across %d pages",
                    len(catalog),
                    catalog.summary()["pages"],
                )
                ConversionLogger.log_info(
                    "XREF",
                    f"ComponentCatalog 构建完成: {len(catalog)} 条目, "
                    f"{catalog.summary()['pages']} 页",
                )

                # v0.7.2: Catalog entries don't carry PCB footprint info
                # (design intent).  Footprint data comes from HDL library
                # matching during Stage 4.  Individual Missing_Footprint
                # warnings are suppressed in mapping_csv_writer.
                ConversionLogger.log_info(
                    "XREF",
                    "Footprint 信息将通过 HDL 库匹配获取（Catalog 不含 footprint）",
                )

                # ── Inject CrossRef coordinates into DSN instances ───
                injected_refdes: int = 0
                injected_coord: int = 0
                for _page in design.pages:
                    for _inst in _page.instances:
                        _entry = catalog.get_by_refdes(_inst.refdes)
                        if _entry is not None:
                            if _inst.refdes != _entry.refdes:
                                _inst.refdes = _entry.refdes
                                injected_refdes += 1
                            # Always use CrossRef coordinates (more accurate)
                            if _entry.loc_x != 0 or _entry.loc_y != 0:
                                _inst.loc_x = _entry.loc_x
                                _inst.loc_y = _entry.loc_y
                                injected_coord += 1
                            if _entry.value and not _inst.value_override:
                                _inst.value_override = _entry.value

                logger.info(
                    "CrossRef injection: %d refdes, %d coords from catalog",
                    injected_refdes,
                    injected_coord,
                )
            except Exception as exc:
                logger.warning("ComponentCatalog build skipped — %s", exc)
        else:
            logger.debug("No Cross Reference CSV found alongside %s", input_path)

        return cross_ref_map, catalog

    def _load_pst_files(
        self,
        design: "DesignIR",
        input_path: Path,
        keys: Optional[list[str]] = None,
        log_summary: bool = True,
    ) -> None:
        """S3：PST 网表文件加载（原 L1673-1724 纯搬移 + 增量支持）。

        - ``keys``：None=全部（pstchip/pstxprt/pstxnet）；否则只加载指定
          key（input 插件增量调用，合并进既有 ``pst_data``）。
        - ``log_summary``：是否输出 ConversionLogger 汇总事件。插件增量
          调用传 False（由引擎 post-chain ``_log_pst_summary`` 统一输出
          一次，保证 plugin/legacy 事件流一致，FR9 字节等价）。
        """
        _wanted = set(("pstchip", "pstxprt", "pstxnet")) if keys is None else set(keys)
        pst_data: dict[str, Any] = dict(design.metadata.get("pst_data") or {})
        _pst_dir = input_path.parent
        _pst_files = [
            ("pstchip.dat", "pstchip"),
            ("pstxprt.dat", "pstxprt"),
            ("pstxnet.dat", "pstxnet"),
        ]
        for _fname, _pkey in _pst_files:
            if _pkey not in _wanted:
                continue
            _pst_path = _pst_dir / _fname
            if not _pst_path.exists():
                continue
            try:
                if _pkey == "pstchip":
                    from ..parser.pstchip_parser import PstchipParser
                    _chip_result = PstchipParser().parse(_pst_path)
                    pst_data["pstchip"] = _chip_result
                    logger.info(
                        "PST: pstchip.dat → %d primitives", len(_chip_result),
                    )
                elif _pkey == "pstxprt":
                    from ..parser.pstxnet_parser import PstxnetParser
                    _xprt_ir = PstxnetParser().parse(_pst_path)
                    pst_data["pstxprt"] = _xprt_ir
                    _ec = len(_xprt_ir.metadata.get("pstxnet_entries", []))
                    logger.info("PST: pstxprt.dat → %d entries", _ec)
                elif _pkey == "pstxnet":
                    from ..parser.pstxnet_netlist_parser import (
                        PstxnetNetlistParser,
                    )
                    _netlist_map = PstxnetNetlistParser().parse(_pst_path)
                    pst_data["pstxnet"] = _netlist_map
                    _total_pins = sum(len(v) for v in _netlist_map.values())
                    logger.info(
                        "PST: pstxnet.dat → %d refdes, %d pin connections",
                        len(_netlist_map), _total_pins,
                    )
            except Exception as _pst_exc:
                logger.warning(
                    "PST: %s parse skipped — %s", _fname, _pst_exc,
                )
        if pst_data:
            design.metadata["pst_data"] = pst_data
            if log_summary:
                ConversionLogger.log_info(
                    "PST",
                    f"网表数据已加载: {', '.join(pst_data.keys())}",
                )
        else:
            logger.debug("No PST netlist files found alongside %s", input_path)

    def _log_pst_summary(self, design: "DesignIR", input_path: Path) -> None:
        """S3：PST 汇总事件（legacy 单条，pstchip/pstxprt/pstxnet 固定序）。

        plugin 模式 post-chain 调用一次；与 legacy ``_load_pst_files`` 的
        ConversionLogger 事件逐字节一致（FR9）。
        """
        pst_data = design.metadata.get("pst_data") or {}
        if pst_data:
            _keys = [k for k in ("pstchip", "pstxprt", "pstxnet") if k in pst_data]
            ConversionLogger.log_info(
                "PST",
                f"网表数据已加载: {', '.join(_keys)}",
            )
        else:
            logger.debug("No PST netlist files found alongside %s", input_path)

    def _rebuild_from_catalog(
        self,
        design: "DesignIR",
        report: ConversionReport,
    ) -> None:
        """S3：catalog 驱动实例重建（原 _legacy_load_input L1726-1999 纯搬移）。

        读取 ``design.metadata["component_catalog"]``；无 catalog → no-op。
        含 power 符号保留/恢复、EDIF 占位实例替换、PST JEDEC 注入、
        cache 失效、report 统计与 readiness 更新。
        """
        catalog = design.metadata.get("component_catalog")
        if catalog is None:
            return
        # ── v0.5.0: Build DesignIR instances from ComponentCatalog ──
        # When DSN parsing produces 0 instances (RTL format where
        # PlacedInstance db_id=0 for all entries), create instances
        # from the CrossRef-driven ComponentCatalog.  This gives us
        # correct refdes, coordinates, values, and page assignment.
        if catalog is not None:
            # ── Phase XI P0-D2: EDIF placeholder instances (INS### with
            # schematic-element library ids) are replaced by the real
            # catalog instances.  EDIF still supplies page structure,
            # wires and nets; the catalog supplies real refdes/placement.
            # Phase XI P0-遗留#2 (2026-08-10): power symbols (GND/VCC_CIRCLE
            # etc.) come ONLY from the EDIF ``portImplementation`` blocks —
            # they are absent from the CrossRef catalog, so they must be
            # preserved across the clear and re-appended after the catalog
            # rebuild (page-local k of regular components stays unchanged
            # because power symbols sort last, mirroring the EDIF layout).
            _POWER_CELLS: frozenset[str] = frozenset({
                "gnd", "dgnd", "vcc_circle", "gnd_power", "gnd_earth",
                "gnd_signal", "vcc_bar", "vcc_arrow", "gnd_chassis",
            })
            power_insts_by_page: list[list] = []
            # Phase XI P2-1: preserve EDIF placeholder orientation before
            # the page instances are cleared — catalog rebuild loses
            # rotation/mirror otherwise.  Keyed by real refdes (bridged via
            # the pstxprt INS→refdes map) so catalog instances match back.
            edif_orient_by_page: list[dict] = []
            _pst_data0 = design.metadata.get("pst_data", {})
            _pstxprt0 = _pst_data0.get("pstxprt")
            _ins_to_refdes: dict[str, str] = {}
            if _pstxprt0 is not None:
                _ins_to_refdes = _pstxprt0.metadata.get("ins_to_refdes", {}) or {}
            if (
                design.source_format == "CIS_EDIF"
                and not cfg.app.use_dsn_components
            ):
                replaced_placeholders = sum(
                    len(p.instances) for p in design.pages
                )
                for _page in design.pages:
                    power_insts = [
                        inst for inst in _page.instances
                        if (getattr(inst, "library_id", "") or "").lower()
                        in _POWER_CELLS
                    ]
                    power_insts_by_page.append(power_insts)
                    # Preserve (refdes, rotation, mirror) for every
                    # non-power placeholder so the catalog-built instances
                    # can restore orientation (P2-1).  The EDIF placeholder
                    # refdes is INS###; the pstxprt INS→refdes map bridges
                    # it to the real refdes (e.g. INS313 → C106).
                    _orient_map: dict[str, tuple[int, int]] = {}
                    for _k, _inst in enumerate(_page.instances):
                        _rot = int(getattr(_inst, "rotation", 0) or 0)
                        _mir = int(getattr(_inst, "mirror", 0) or 0)
                        if _rot or _mir:
                            _ref = getattr(_inst, "refdes", "") or ""
                            _real = _ins_to_refdes.get(_ref, _ref)
                            _orient_map[_real] = (_rot, _mir)
                    edif_orient_by_page.append(_orient_map)
                    _page.instances = []
                logger.info(
                    "P0-D2: cleared %d EDIF placeholder instance(s); "
                    "instances will come from ComponentCatalog "
                    "(%d power symbol instance(s) preserved)",
                    replaced_placeholders,
                    sum(len(v) for v in power_insts_by_page),
                )

            catalog_instances_added: int = 0
            dsn_pages: dict[str, PageIR] = {p.page_id: p for p in design.pages}
            # Also build a lookup by page_name for fuzzy matching
            dsn_pages_by_name: dict[str, PageIR] = {
                p.page_name: p for p in design.pages if p.page_name
            }

            for entry in catalog.all_entries():
                page_name: str = entry.page_name
                target_page: Optional[PageIR] = None

                # Try exact match first (page_id == page_name)
                target_page = dsn_pages.get(page_name)
                # Try page_name match
                if target_page is None:
                    target_page = dsn_pages_by_name.get(page_name)
                # Fuzzy match: check if page_name is a substring of
                # any DSN page_id or page_name
                if target_page is None:
                    for pg_id, pg in dsn_pages.items():
                        if page_name in pg_id or pg_id in page_name:
                            target_page = pg
                            break
                if target_page is None:
                    for pg_name, pg in dsn_pages_by_name.items():
                        if page_name in pg_name or pg_name in page_name:
                            target_page = pg
                            break

                if target_page is None:
                    # v0.8.2: Check if a xref page was already created
                    # for this page_name (multiple entries share a page).
                    for _existing in design.pages:
                        if (_existing.page_id.startswith("xref.")
                                and _existing.page_name == page_name):
                            target_page = _existing
                            break

                if target_page is None:
                    # Page not found in DSN parse — create it once
                    new_page_id = f"xref.{page_name}"
                    target_page = PageIR(page_id=new_page_id, page_name=page_name)
                    design.pages.append(target_page)
                    logger.debug(
                        "Catalog: created DSN-missing page '%s'",
                        page_name,
                    )

                # Check if instance already exists (avoid duplicates
                # when DSN already produced instances for this refdes)
                if any(i.refdes == entry.refdes for i in target_page.instances):
                    continue
                inst = ComponentInstanceIR(
                    refdes=entry.refdes,
                    library_id=entry.refdes,
                    loc_x=entry.loc_x,
                    loc_y=entry.loc_y,
                    section=1,
                    value_override=entry.value,
                )
                # Phase XI P2-1: restore EDIF placeholder orientation.
                # The catalog instance is matched to its EDIF placeholder
                # by real refdes (orientation was preserved in
                # edif_orient_by_page keyed by refdes).
                if edif_orient_by_page and target_page is not None:
                    _pg_idx = None
                    for _pg_ref, _orient_map in zip(design.pages, edif_orient_by_page):
                        if (_pg_ref.page_id == target_page.page_id
                                or _pg_ref.page_name == target_page.page_name):
                            _pg_idx = _orient_map
                            break
                    if _pg_idx and entry.refdes in _pg_idx:
                        _rot, _mir = _pg_idx.pop(entry.refdes)
                        inst.rotation = _rot
                        inst.mirror = _mir
                target_page.instances.append(inst)
                catalog_instances_added += 1

            # ── v0.8.0: Inject PST data into instances ─────────────
            # Enrich ComponentInstanceIR with pstchip JEDEC_TYPE & VALUE
            # from the OrCAD PSTWRITER netlist for precise matching.
            pst_data2 = design.metadata.get("pst_data", {})
            pstchip_map2 = pst_data2.get("pstchip", {})
            pstxprt_ir2 = pst_data2.get("pstxprt")
            pstxprt_entries2 = (
                pstxprt_ir2.metadata.get("pstxnet_entries", [])
                if pstxprt_ir2 else []
            )
            if pstchip_map2 and pstxprt_entries2:
                from ..parser.pstxnet_parser import PstxnetParser
                refdes_to_chip = PstxnetParser.build_pstchip_lookup(
                    pstxprt_entries2, pstchip_map2,
                )
                pst_injected = 0
                for _pg in design.pages:
                    for _inst in _pg.instances:
                        _chip_entry = refdes_to_chip.get(_inst.refdes.upper())
                        if _chip_entry is not None:
                            _inst.extra_data["pst_jedec_type"] = (
                                _chip_entry.jedec_type
                            )
                            _inst.extra_data["pst_value"] = (
                                _chip_entry.value
                            )
                            _inst.extra_data["pst_part_name"] = (
                                _chip_entry.part_name
                            )
                            pst_injected += 1
                logger.info(
                    "PST_INJECT: %d instances enriched, %d lookup",
                    pst_injected, len(refdes_to_chip),
                )

            logger.info(
                "Catalog→DesignIR: added %d instances to %d pages "
                "(+%d dynamically created pages)",
                catalog_instances_added,
                len([p for p in design.pages if p.instances]),
                len(design.pages) - len(dsn_pages),
            )
            ConversionLogger.log_info(
                "INST",
                f"从 ComponentCatalog 创建 {catalog_instances_added} 个实例",
            )

            # ── Phase XI P0-遗留#2: restore power symbol instances ──
            # Power symbols are not part of the CrossRef catalog; re-append
            # them AFTER the catalog instances so each page's local k for
            # regular components is unchanged.  Every power symbol gets a
            # unique refdes (EDIF rename forms may leave it empty), which
            # guarantees the CoordTransform refdes→coord map never collides.
            if power_insts_by_page:
                _restored = 0
                for _pg_idx, (_pg, _power_insts) in enumerate(
                    zip(design.pages, power_insts_by_page), start=1
                ):
                    if not _power_insts:
                        continue
                    for _pk, _pi in enumerate(_power_insts, start=1):
                        if not getattr(_pi, "refdes", ""):
                            _lib_id = (
                                getattr(_pi, "library_id", "") or "power"
                            ).lower()
                            _pi.refdes = f"{_lib_id}_{_pg_idx}_{_pk}"
                        _pg.instances.append(_pi)
                    _restored += len(_power_insts)
                logger.info(
                    "P0-#2: restored %d power symbol instance(s) across "
                    "%d page(s)",
                    _restored,
                    len([v for v in power_insts_by_page if v]),
                )

            # ── Phase XII R1: invalidate cached_property values ──
            # all_instances/all_nets were cached during EDIF parsing with
            # the placeholder inventory (3023 EDIF instances).  After the
            # catalog rebuild + power restore the page instance lists have
            # changed, so the cached values are stale — drop them so the
            # next access (quality estimation, matching) recomputes the
            # real instance set (1219 = 914 catalog + 305 power symbols).
            design.invalidate_caches()

            # ── Update conversion report stats ──────────────────
            report.instances = sum(len(p.instances) for p in design.pages)
            report.nets = sum(len(p.nets) for p in design.pages)

            # ── v0.7.2: Update readiness metrics with real pipeline data ──
            # Stage 1 readiness scores were computed from DSN internal
            # inventory, but actual pipeline uses CrossRef CSV (100%
            # coordinates, 99.9% match rate).  Update readiness to
            # reflect the real data quality available.
            if report.diagnostic_report is not None:
                readiness = report.diagnostic_report.readiness
                readiness.logic_score = 1.0  # Catalog provides complete identity
                readiness.coordinate_score = 1.0  # CrossRef CSV 100% coordinates
                # Calculate matchability from actual catalog entries
                total_cat = len(catalog)
                if total_cat > 0:
                    # matchability: catalog has values for most components
                    valued_count = sum(
                        1 for e in catalog.all_entries() if e.value
                    )
                    readiness.matchability_score = min(
                        1.0, 0.5 + 0.5 * (valued_count / max(total_cat, 1))
                    )
                else:
                    readiness.matchability_score = 0.5
                # Symbol score: HDL symbols, not original CIS symbols
                readiness.symbol_score = 0.5
                # Recalculate overall
                w = ConversionReadinessEvaluator.WEIGHTS
                readiness.overall_score = (
                    readiness.logic_score * w["logic"]
                    + readiness.coordinate_score * w["coordinate"]
                    + readiness.matchability_score * w["matchability"]
                    + readiness.symbol_score * w["symbol"]
                )
                logger.info(
                    "Readiness updated (post-Catalog): overall=%.0% "
                    "logic=%.0f coord=%.0f match=%.0f sym=%.0f",
                    readiness.overall_score,
                    readiness.logic_score,
                    readiness.coordinate_score,
                    readiness.matchability_score,
                    readiness.symbol_score,
                )


    def _finalize_plugin_input(
        self,
        design: "DesignIR",
        report: ConversionReport,
        input_path: Path,
    ) -> None:
        """S3：plugin 模式 load_input post-chain 收尾（等价 legacy 尾段）。

        plugin 接管后（edif/dsn 解析 + cross_ref/pst 增量插件全部执行完），
        引擎统一执行：
        1. PST 汇总事件（legacy 单条，固定序）
        2. catalog 重建（若 catalog 存在）
        3. ``_last_cross_ref_map`` / ``_last_catalog`` 副作用暴露
           （convert() 的 match 钩子/低置信度日志依赖，S2 约定）
        """
        self._log_pst_summary(design, input_path)
        self._rebuild_from_catalog(design, report)
        self._last_catalog = design.metadata.get("component_catalog")
        self._last_cross_ref_map = getattr(self, "_last_cross_ref_map", None) or {}


    def _legacy_reports(
        self,
        design: DesignIR,
        match_results: list,
        output_dir: Path,
        report: ConversionReport,
        input_path: Path,
    ) -> None:
        """S2 legacy fallback：原 convert() 报告块（mapping csv/top3/错误日志）。

        纯代码搬移（原 L2330-2371），不改逻辑。
        """
        # ── Mapping CSV Report ─────────────────────────────────────
        try:
            from ..writer.mapping_csv_writer import MappingCSVWriter
            mapping_csv_path = output_dir / f"{report.project_name}_mapping.csv"
            MappingCSVWriter.write(
                mapping_csv_path,
                design,
                match_results,
                report,
                output_dir,
                input_path,
            )
            report.output_files.append(str(mapping_csv_path))
            logger.info("Mapping CSV: %s", mapping_csv_path)
        except Exception as exc:
            logger.warning("Mapping CSV generation failed: %s", exc)

        # ── v1.0: Top-3 Candidate Database ───────────────────────────
        try:
            from ..writer.mapping_csv_writer import write_top3_file
            top3_path = output_dir / f"{report.project_name}_top3.txt"
            # Use match_results which already carry top3_candidates
            # in extra_data (populated by pipeline.run_batch).
            write_top3_file(
                top3_path,
                [],  # sources not needed — data is in MatchResult.extra_data
                match_results,
            )
            report.output_files.append(str(top3_path))
            logger.info("Top-3 database: %s", top3_path)
        except Exception as exc:
            logger.warning("Top-3 database generation failed: %s", exc)

        # ── Write error logs ────────────────────────────────────────
        try:
            log_paths = ConversionLogger.write(
                output_dir,
                report.project_name or input_path.stem,
            )
            report.output_files.append(str(log_paths[0]))  # HTML
            report.output_files.append(str(log_paths[1]))  # TXT
            logger.info("Error logs: %s, %s", *log_paths)
        except Exception as exc:
            logger.warning("Failed to write error logs: %s", exc)

    # ═══════════════════════════════════════════════════════════════════
    #  S2 plugin 模式：set_pipeline / convert_with_cfg + 薄包装委托入口
    # ═══════════════════════════════════════════════════════════════════

    def set_pipeline(self, cfg: PipelineConfig) -> None:
        """显式激活 plugin 模式：self._pm = build_plugin_manager(cfg)。"""
        self._pipeline_cfg = cfg
        self._pm = build_plugin_manager(cfg, engine=self)

    def convert_with_cfg(
        self,
        cfg: PipelineConfig,
        input_path: Path,
        output_dir: Path,
        **kw: Any,
    ) -> ConversionReport:
        """plugin 模式便捷入口（S3+ CLI 使用）。"""
        self.set_pipeline(cfg)
        return self.convert(input_path, output_dir, **kw)

    def run_match_stage(
        self,
        design: "DesignIR",
        hdl_db: ComponentDB,
        report: ConversionReport,
        cross_ref_map: Optional[dict] = None,
        pc: Optional[ProgressCallback] = None,
    ) -> list:
        """薄包装插件委托入口：= _stage_match + _append_power_symbol_matches。

        matcher_pipeline 插件调用（与 legacy convert() 行为逐字节等价）。
        """
        results = self._stage_match(design, hdl_db, report, pc, cross_ref_map)
        self._append_power_symbol_matches(design, results)
        return results

    def run_generate_stage(
        self,
        design: "DesignIR",
        matches: list[MatchResult],
        output_dir: Path,
        report: ConversionReport,
        pc: Optional[ProgressCallback] = None,
        hdl_lib_path: Optional[Path] = None,
    ) -> ConversionReport:
        """薄包装插件委托入口：= _stage_generate（写全部文件，report 累积）。"""
        self._stage_generate(design, matches, output_dir, report, pc, hdl_lib_path)
        return report

    def run_manual_overrides(
        self,
        design: "DesignIR",
        hdl_db: ComponentDB,
        matches: list[MatchResult],
        report: ConversionReport,
        input_path: Path,
    ) -> None:
        """薄包装插件委托入口：= _apply_phase14_matching（手动匹配/电源 IC）。"""
        self._apply_phase14_matching(design, hdl_db, matches, report, input_path)

    def run_legacy_reports(
        self,
        design: "DesignIR",
        match_results: list,
        output_dir: Path,
        report: ConversionReport,
        input_path: Path,
    ) -> list:
        """薄包装插件委托入口：= _legacy_reports（mapping csv/top3/错误日志）。"""
        self._legacy_reports(design, match_results, output_dir, report, input_path)
        return list(report.output_files)

    def apply_beautify_params(self, ctx: Any) -> None:
        """S5 美化编排入口：把 pipeline ``beautify.params`` 应用到全局
        ``config.routing``。

        与 S1 CLI ``cfg_obj.routing = cfg.to_routing_config()`` 完全等价
        （FR9）：CSAWriter 在 generate 阶段读取 ``config.routing``，其内置
        美化逻辑（overlap_resolver / gnd_cluster_planner / wire_simplifier
        / wire_layout / text_layout）按配置开关在正确阶段执行 —— 顺序语义
        由 writer 内部保证，插件链顺序 = yaml 顺序（S2 逆序注册）。

        默认 profile 时 ``beautify.params`` == RoutingConfig 默认 → 应用为
        no-op，plugin 模式与 legacy 逐字节等价；max-beauty 等 profile 的
        ``routing.mode=detour`` / ``wire_simplify.enabled`` / 
        ``text_layout.enabled`` 等**非单插件 param_fields 覆盖字段**也全部
        生效（完整 params 应用，而非仅插件声明字段）。
        """
        from ..config import config as _cfg

        _cfg.routing = ctx.cfg.to_routing_config()

    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        hdl_lib_path: Optional[Path] = None,
        progress_callback: Optional[ProgressCallback] = None,
        config_file: Optional[Path] = None,
        extra_lib_paths: Optional[list[Path]] = None,
    ) -> ConversionReport:
        """Run the complete six-stage conversion pipeline.

        Pipeline stages:
            1. Diagnose — validate input files
            2. Parse    — parse .dsn/.edf → DesignIR
            3. Scan     — scan HDL library → ComponentDB
            4. Match    — match CIS components to HDL components
            5. Validate — validate match results
            6. Generate — write output files (.cpm, cds.lib, .sch)

        Phase XIV D5: ``config_file`` 指定 routing.yaml（可选）；未指定则
        使用全局 config.routing 默认值（全部新功能默认关）。D3/D4 匹配
        增强在 Stage 4 之后注入（``_apply_phase14_matching``）。

        Post-generation: quality estimation via ConversionQualityEstimator
        and HTML report export.

        Args:
            input_path: Path to the input file (.dsn or .edf).
            output_dir: Output directory for generated HDL files.
            hdl_lib_path: Path to HDL component library root.
            progress_callback: Optional callback(stage_name, progress_pct, msg).
            config_file: Optional routing.yaml path (Phase XIV D5).
            extra_lib_paths: Optional extra HDL library roots (D4 方案 B).

        Returns:
            ConversionReport with full diagnostics, match results,
            validation errors, quality scores, and output file paths.
        """
        report = ConversionReport()
        report.project_name = input_path.stem
        pc = progress_callback

        # ── Phase XIV D5: load routing.yaml（默认关，可回退） ─────
        if config_file is not None:
            try:
                cfg.load_from_file(Path(config_file))
            except Exception as exc:
                logger.warning("routing config load failed: %s", exc)

        # ── S2 plugin 模式上下文（legacy 模式 _pm=None 时仅兜底用） ──
        ctx = ConversionContext(
            cfg=self._pipeline_cfg or PipelineConfig(),
            input_files=[input_path],
            output_dir=output_dir,
        )
        ctx.report = report

        # ── Initialize conversion logger ───────────────────────────
        ConversionLogger.reset()
        ConversionLogger.log_info("CONVERT", f"Starting conversion: {input_path}")

        _bench = cfg.app.benchmark
        _t0 = _time.perf_counter() if _bench else 0.0

        # ── Stage 1: Diagnose ──────────────────────────────────────
        _t1 = _time.perf_counter() if _bench else 0.0
        try:
            if not self._stage_diagnose(input_path, report, pc):
                logger.warning("Stage 1 (Diagnose) returned False — continuing anyway")
        except Exception as exc:
            logger.warning("Stage 1 (Diagnose) failed: %s — continuing", exc)

        # ── Stage 2: Parse ─────────────────────────────────────────
        _t2 = _time.perf_counter() if _bench else 0.0
        if _bench:
            report.stage_timings["diagnose"] = _t2 - _t1

        # ── Stage 2: Parse（S2 钩子：plugin 模式 load_input 可接管） ──
        # legacy/未接管 → _legacy_load_input（原内联块，字节等价）
        # S3：plugin 接管（edif/dsn 真实现）后由 _finalize_plugin_input
        # 统一做 PST 汇总 + catalog 重建 + _last_* 副作用，保证与 legacy
        # 全链路等价（FR9）。
        handled, _res = self._host.call(
            ctx, "load_input",
            fallback=lambda: self._legacy_load_input(input_path, report, pc),
        )
        if handled and ctx.ir is not None:
            design = ctx.ir
            self._finalize_plugin_input(design, report, input_path)
        elif not handled:
            design = _res
        else:
            # handled=True 但无插件产出 ctx.ir（异常插件）→ 回退 legacy
            logger.warning(
                "load_input handled=True 但 ctx.ir 为空 — 回退 legacy 全链",
            )
            design = self._legacy_load_input(input_path, report, pc)
        if design is None:
            return report


        # ── Stage 3: Scan ──────────────────────────────────────────
        _t3 = _time.perf_counter() if _bench else 0.0
        if _bench:
            report.stage_timings["parse"] = _t3 - _t2
        hdl_db = self._stage_scan(hdl_lib_path, report, pc,
                                  extra_lib_paths=extra_lib_paths)

        # ── Stage 4: Match（S2 钩子：match_components 可接管） ────
        _t4 = _time.perf_counter() if _bench else 0.0
        if _bench:
            report.stage_timings["scan"] = _t4 - _t3
        handled, _res = self._host.call(
            ctx, "match_components", fallback=lambda: None,
        )
        if handled and ctx.matches:
            match_results = ctx.matches
        else:
            # ── Phase XII R2: power symbol MatchResults ─────────────
            # EDIF power symbols (GND/DGND/VCC_CIRCLE/…) are preserved
            # across the catalog rebuild but are NOT part of the
            # ComponentCatalog, so the matching pipeline never processes
            # them → they previously had no MatchResult (INFO_LOSS
            # warnings + coverage drag).  Generate dedicated
            # high-confidence results for every power library_id that
            # actually appears in the design so they flow through
            # reports/CSV.
            match_results = self._stage_match(design, hdl_db, report, pc,
                                              getattr(self, "_last_cross_ref_map", None))
            self._append_power_symbol_matches(design, match_results)

        # ── Phase XIV D3/D4: manual matches + power IC auto-match ──
        # 注：真正调用在 Stage 5.5b（pstxnet pin 注入）之后 ——
        # pin_connections 到那时才完整（D4 需要真实引脚数/网名）。
        # 见下方 _apply_phase14_matching 调用点。

        # ── Log match results ──────────────────────────────────────
        if match_results:
            matched = sum(
                1 for m in match_results
                if m.confidence and m.confidence >= 0.45
            )
            failed = len(match_results) - matched
            fuzzy = sum(
                1 for m in match_results
                if m.confidence and 0.25 <= m.confidence < 0.45
            )

            ConversionLogger.log_info(
                "MATCH",
                f"匹配完成: {matched} 成功, {failed} 失败, {fuzzy} 模糊",
            )

            # v0.8.2: Enrich match results with CIS/PST data for reports
            # Build lookup of refdes → instance for fast cross-reference
            inst_lookup: dict[str, Any] = {}
            for _pg in design.pages:
                for _inst in _pg.instances:
                    inst_lookup[_inst.refdes.upper()] = _inst
            for _mr in match_results:
                _inst = inst_lookup.get(_mr.source_library_id.upper())
                if _inst is not None:
                    _mr.cis_value = getattr(_inst, "value_override", "") or ""
                    extra = getattr(_inst, "extra_data", {}) or {}
                    _mr.pst_value = extra.get("pst_value", "")
                    _mr.jedec_type = extra.get("pst_jedec_type", "")
                    _mr.error_note = "; ".join(_mr.warnings[:2]) if _mr.warnings else ""

            if failed > 0:
                ConversionLogger.log_warning(
                    "MATCH",
                    f"{failed} 个器件置信度偏低",
                    detail=f"{failed}/{len(match_results)} 器件匹配失败，请检查器件库",
                )

            if fuzzy > 0:
                ConversionLogger.log_warning(
                    "MATCH",
                    f"{fuzzy} 个器件置信度一般",
                    detail="请人工确认模糊匹配结果是否可用",
                )

            # 记录每个低置信度匹配的详情 (v1.0: threshold 0.45)
            for mr in match_results:
                if not mr.confidence or mr.confidence < 0.45:
                    src = getattr(mr, 'source_library_id', '?')
                    # v0.5.1: 包含 value 信息，方便诊断
                    value_info = ""
                    if getattr(self, "_last_catalog", None) is not None:
                        cat_entry = self._last_catalog.get_by_refdes(src)
                        if cat_entry and cat_entry.value:
                            value_info = f" | value={cat_entry.value}"
                    ConversionLogger.log_warning(
                        "MATCH",
                        f"低置信度: {src}{value_info}",
                        detail=f"confidence={mr.confidence}",
                    )

        # ── Stage 5: Validate ──────────────────────────────────────
        _t5 = _time.perf_counter() if _bench else 0.0
        if _bench:
            report.stage_timings["match"] = _t5 - _t4
        # v0.5.0: Skip validation for large designs (914+ instances)
        # Validation is O(n²) and produces excessive noise when instances
        # lack pin connections (CrossRef-driven mode). Run only when
        # explicitly requested or for small designs.
        total_instances = sum(len(p.instances) for p in design.pages)
        if total_instances <= 200 or getattr(cfg.app, 'validate', False):
            if not self._stage_validate(design, match_results, report, pc):
                return report
        else:
            logger.info(
                "Stage 5 (Validate) skipped for large design (%d instances)",
                total_instances,
            )

        # ── v0.6.0: Stage 5.5 — EDIF Pin Connection Injection ──────
        # Inject pin→net mappings from EDIF into ComponentInstanceIR,
        # enabling LASTPIN SIG_NAME generation in CSA output.
        _edf_path: Optional[Path] = input_path.with_suffix('.EDF')
        if not _edf_path.exists():
            _edf_path = input_path.with_suffix('.edf')
        if _edf_path is not None and _edf_path.exists():
            try:
                from ..parser.edif_parser import EDIFParser
                pin_map = EDIFParser.extract_pin_net_map(_edf_path)
                if pin_map:
                    injected_pins: int = 0
                    injected_instances: int = 0
                    for _page in design.pages:
                        for _inst in _page.instances:
                            _pm = pin_map.get(_inst.refdes)
                            if _pm:
                                _inst.pin_connections = dict(_pm)
                                injected_pins += len(_pm)
                                injected_instances += 1
                    logger.info(
                        "EDIF pin injection: %d pins → %d instances",
                        injected_pins, injected_instances,
                    )
                    ConversionLogger.log_info(
                        "EDIF",
                        f"注入 {injected_pins} pin→net 连接到 {injected_instances} 个实例",
                    )
                else:
                    logger.debug("EDIF pin map: no connections extracted")
            except Exception as exc:
                logger.warning("EDIF pin injection skipped — %s", exc)
        else:
            logger.debug("No EDIF file found alongside %s for pin injection", input_path)

        # ── v0.9.0: Stage 5.5b — PSTXNET Pin Connection (Primary) ──
        # pstxnet.dat provides complete net connectivity with real net names
        # (823 refdes × 1818 pins, ALL non-empty).  Use it as PRIMARY source,
        # overwriting any EDIF data.  Then supplement with EDIF for remaining
        # refdes not covered by pstxnet.
        pst_data3 = design.metadata.get("pst_data", {})
        pstxnet_map3 = pst_data3.get("pstxnet", {})
        if pstxnet_map3:
            _pst_pin_count = 0
            _pst_inst_count = 0
            for _page in design.pages:
                for _inst in _page.instances:
                    _pst_pins = pstxnet_map3.get(_inst.refdes)
                    if _pst_pins:
                        # PRIMARY: always use pstxnet data (overwrite EDIF)
                        _inst.pin_connections = dict(_pst_pins)
                        _pst_pin_count += len(_pst_pins)
                        _pst_inst_count += 1
                        # Phase XI P1-4: record no-connect pins — pins
                        # whose net is "NC" (67 in HG5015: U6 mostly).
                        _nc: set[str] = {
                            _pin for _pin, _net in _pst_pins.items()
                            if str(_net).strip().upper() == "NC"
                        }
                        if _nc:
                            _inst.nc_pins = _nc
            logger.info(
                "PSTXNET pin injection (PRIMARY): %d pins → %d instances",
                _pst_pin_count, _pst_inst_count,
            )
            ConversionLogger.log_info(
                "PST",
                f"pstxnet 主注入 {_pst_pin_count} pin→net 连接到 "
                f"{_pst_inst_count} 个实例",
            )

        # ── v0.9.0: Stage 5.5c — PSTCHIP Pin Validation & Gap Fill ──
        # Use pstchip.dat pin definitions (pin_label→pin_number mapping)
        # to validate pstxnet connections and fill gaps from EDIF data.
        # pstchip provides the definitive mapping: 'A':'(1)', 'B':'(2)'.
        pst_data4 = design.metadata.get("pst_data", {})
        pstchip_map4 = pst_data4.get("pstchip", {})
        pstxprt_ir4 = pst_data4.get("pstxprt")
        pstxprt_entries4 = (
            pstxprt_ir4.metadata.get("pstxnet_entries", [])
            if pstxprt_ir4 else []
        )
        if pstchip_map4 and pstxprt_entries4:
            from ..parser.pstxnet_parser import PstxnetParser
            refdes_to_chip4 = PstxnetParser.build_pstchip_lookup(
                pstxprt_entries4, pstchip_map4,
            )
            _validated = 0
            _gap_filled = 0
            _mismatch = 0
            for _page in design.pages:
                for _inst in _page.instances:
                    _chip = refdes_to_chip4.get(_inst.refdes)
                    if _chip is None:
                        continue
                    _chip_pins: dict = getattr(_chip, 'pins', {}) or {}
                    # Build reverse map: numeric_pin → label (e.g. '1'→'A')
                    _num_to_label: dict[str, str] = {
                        v: k for k, v in _chip_pins.items()
                    }
                    # Phase XXI D（用户 Cadence 16.6 实测 P6）：pstchip
                    # primitive 提供**真实引脚名**（pin label → 引脚号）。
                    # 无论 pin_connections 有无网，都存入
                    # extra_data["pstchip_pin_names"]（{引脚号: 功能名}）——
                    # ConnectivityModelBuilder 在引脚名回退到引脚号时用它
                    # 显示真实功能名（如 AMS1117 → GND/OUTPUT/INPUT/TAP）。
                    if _chip_pins:
                        _inst.extra_data["pstchip_pin_names"] = dict(
                            _num_to_label,
                        )
                    if _inst.pin_connections:
                        # Validate: are pin numbers consistent with pstchip?
                        _validated += 1
                        for _pin_num in list(_inst.pin_connections.keys()):
                            if _pin_num in _num_to_label:
                                # Pin number matches pstchip — OK
                                pass
                            elif _pin_num in _chip_pins:
                                # Instance uses label (A/B), convert to number
                                _new_num = _chip_pins[_pin_num]
                                _net = _inst.pin_connections.pop(_pin_num)
                                _inst.pin_connections[_new_num] = _net
                                _mismatch += 1
                    else:
                        # Gap: no pin_connections — try EDIF data via pstchip mapping
                        # (EDIF pin labels like 'A','B' → pstchip numbers '1','2')
                        # Phase XXI D：EDIF 网名空且 pstxnet 未覆盖（如
                        # AMS1117→IC3）时，ConnectivityModelBuilder 用
                        # pstchip_pin_names 恢复真实引脚名（替代 mock 占位
                        # 1-8）；引脚仍无网（悬空 LASTPIN、不生成 WIRE），
                        # pin_audit 报告 [HANGING]。
                        _edif_filled = False
                        for _label, _num in _chip_pins.items():
                            # EDIF data was already injected — check if cleared
                            if _num and _num.strip():
                                pass  # EDIF empty nets were already skipped
                        # Mark as gap (pstchip confirms component has pins,
                        # but no net data available from pstxnet or EDIF)
            logger.info(
                "PSTCHIP validation: %d validated, %d label→number fixed, "
                "%d gaps (no net data)",
                _validated, _mismatch,
                sum(1 for p in design.pages for i in p.instances
                    if not i.pin_connections
                    and refdes_to_chip4.get(i.refdes) is not None),
            )

        # ── Phase XIV D3/D4: manual matches + power IC auto-match ──
        # pstxnet/pstchip 引脚注入完成后调用（实例 pin_connections 完整）。
        # S2 钩子：apply_manual_overrides 可接管；未接管 → legacy 调用。
        self._host.call(
            ctx, "apply_manual_overrides",
            fallback=lambda: self._apply_phase14_matching(
                design, hdl_db, match_results, report, input_path,
            ),
        )

        # ── S2 美化钩子（S5 真实现：插件应用 beautify.params 到全局
        # config.routing，writer 在 generate 阶段按配置执行美化逻辑；空链/
        # 全禁用 → no-op，全局 config 保持调用方预置/默认，FR9） ──
        self._host.call(ctx, "beautify", fallback=lambda: None)

        # v0.8.2: Recalculate real pages and aggregate errors before report
        # Phase XII R6: report.pages must reflect the TOTAL parsed page
        # count (all DSN/EDIF pages, including info pages such as
        # 01-Cover_Page / 02-Block_Diagram / 03-Clock_Tree / 04-Power_Tree
        # whose EDIF placeholder instances are cleared during the catalog
        # rebuild).  The previous filtered count (instances OR
        # graphic_elements) produced 20 while the HDL output had 24 CSA
        # files — a user-visible discrepancy.  The schematic/info page
        # breakdown is still available in the mapping CSV overview.
        report.pages = len(design.pages)
        report._aggregate_errors()

        # ── Stage 6: Generate ──────────────────────────────────────
        _t6 = _time.perf_counter() if _bench else 0.0
        if _bench:
            report.stage_timings["validate"] = _t6 - _t5
        effective_lib_path = (
            hdl_lib_path
            if hdl_lib_path is not None
            else (Path(cfg.hdl_lib.hdl_lib_path)
                  if cfg.hdl_lib.hdl_lib_path else None)
        )
        # ── Stage 6: Generate（S2 钩子：write_output 可接管） ──────
        handled, _res = self._host.call(
            ctx, "write_output",
            fallback=lambda: self._stage_generate(
                design, match_results, output_dir, report, pc,
                effective_lib_path,
            ),
        )

        # ── Mapping CSV / Top3 / 错误日志（S2 钩子：write_report 可接管） ──
        self._host.call(
            ctx, "write_report",
            fallback=lambda: self._legacy_reports(
                design, match_results, output_dir, report, input_path,
            ),
        )


        # ── Final aggregation ──────────────────────────────────────
        report._aggregate_errors()
        self._report_progress(
            pc, "complete", 1.0,
            "Conversion complete"
            if report.success
            else "Conversion finished with errors",
        )

        if _bench:
            _t_end = _time.perf_counter()
            report.stage_timings["generate"] = _t_end - _t6
            report.total_elapsed = _t_end - _t0
            logger.info("Benchmark:\n%s", report.benchmark_report())

        logger.info(
            "Conversion %s: %s",
            "OK" if report.success else "FAILED",
            report,
        )
        return report

    # ═══════════════════════════════════════════════════════════════════
    #  Backward-compatible alias
    # ═══════════════════════════════════════════════════════════════════

    def convert_full(
        self,
        dsn_path: Path,
        hdl_lib_path: Optional[Path],
        output_dir: Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ConversionReport:
        """Full pipeline — alias for ``convert()`` with explicit parameters.

        This method exists for API clarity when the caller wants to be
        explicit about all three paths.  It delegates to ``convert()``.

        Args:
            dsn_path: Path to the .dsn input file.
            hdl_lib_path: Path to HDL component library root.
            output_dir: Output directory for generated files.
            progress_callback: Optional progress callback.

        Returns:
            ConversionReport.
        """
        return self.convert(
            input_path=dsn_path,
            output_dir=output_dir,
            hdl_lib_path=hdl_lib_path,
            progress_callback=progress_callback,
        )

    # ═══════════════════════════════════════════════════════════════════
    #  Manual match acceptance
    # ═══════════════════════════════════════════════════════════════════

    def accept_match(
        self,
        source_library_id: str,
        target_library_id: str,
    ) -> MatchResult:
        """Accept a manual match after user confirmation.

        Args:
            source_library_id: The CIS component library ID.
            target_library_id: The user-selected HDL component library ID.

        Returns:
            MatchResult with strategy=MANUAL and confidence=1.0.
        """
        logger.info(
            "Manual match accepted: %s → %s",
            source_library_id,
            target_library_id,
        )
        return self._manual_resolver.accept(source_library_id, target_library_id)

    # ═══════════════════════════════════════════════════════════════════
    #  Helper: extract CIS ComponentDef from DesignIR
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_cis_components(
        design: DesignIR,
        cross_ref_map: Optional[dict] = None,
    ) -> list[ComponentDef]:
        """Extract unique CIS component definitions from the DesignIR.

        v0.5.0: Prefers ComponentCatalog when available in design.metadata.
        Falls back to iterating over DesignIR instances when no catalog
        is available (legacy path).

        Args:
            design: The parsed DesignIR.
            cross_ref_map: Optional refdes→CrossRefEntry map from
                Cross Reference CSV injection.

        Returns:
            List of unique ComponentDef objects used in the design.
        """
        # ── v0.5.0: Try catalog first ──────────────────────────────
        catalog = design.metadata.get("component_catalog")
        if catalog is not None:
            logger.debug("_extract_cis_components: using ComponentCatalog")
            return catalog.to_component_defs()

        # ── Legacy fallback: iterate over DSN instances ────────────
        if cross_ref_map is None:
            cross_ref_map = {}

        seen_ids: set[str] = set()
        components: list[ComponentDef] = []

        for instance in design.all_instances:
            lib_id = instance.library_id
            if not lib_id or lib_id in seen_ids:
                continue

            # Build a minimal ComponentDef from the instance
            footprint = instance.properties.get(
                "PCB Footprint",
                instance.properties.get("FOOTPRINT", ""),
            )
            value = instance.properties.get(
                "Value",
                instance.properties.get("VALUE", ""),
            )

            # CrossRef enrichment
            _xref_entry = cross_ref_map.get(instance.refdes) if cross_ref_map else None
            if _xref_entry is not None:
                if _xref_entry.value and not value:
                    value = _xref_entry.value
                if _xref_entry.value and not instance.value_override:
                    instance.value_override = _xref_entry.value

            pin_count = len(instance.pin_connections)

            # v2.0: Build extra_data with PST JEDEC for PassiveMatcher footprint fallback
            inst_jedec = instance.extra_data.get("pst_jedec_type", "") if hasattr(instance, "extra_data") else ""
            extra = {"jedec_type": inst_jedec} if inst_jedec else {}
            if not inst_jedec and len(components) < 3:
                logger.debug("v2.0 JEDEC: instance %s has no pst_jedec_type (extra_data=%s)",
                    instance.refdes, bool(hasattr(instance, "extra_data")))

            minimal = ComponentDef(
                library_id=lib_id,
                part_name=instance.refdes,
                footprint=footprint,
                value=value,
                pin_count=pin_count,
                extra_data=extra,
                pins=[
                    PinDef(number=pn, name="")
                    for pn in instance.pin_connections.keys()
                ],
            )
            components.append(minimal)
            seen_ids.add(lib_id)

        # ── V-C1: Non-destructive pstxnet injection ──────────────────
        _pstx_entries: list = design.metadata.get("pstxnet_entries", [])
        if _pstx_entries:
            _pstx_by_refdes: dict[str, object] = {}
            _pstx_by_part: dict[str, object] = {}
            for _entry in _pstx_entries:
                _rd = getattr(_entry, "refdes", "")
                _pn = getattr(_entry, "part_name", "")
                if _rd:
                    _pstx_by_refdes[_rd] = _entry
                if _pn:
                    _pstx_by_part[_pn] = _entry

            for _comp in components:
                _entry = _pstx_by_refdes.get(_comp.library_id) or _pstx_by_part.get(_comp.part_name)
                if _entry is not None:
                    _fp = getattr(_entry, "footprint", "")
                    _val = getattr(_entry, "value", "")
                    # Only inject footprint if it looks like a valid package size
                    # (contains 4-digit size code, BGA, SOT, QFN, MLF pattern)
                    if _fp and not _comp.footprint:
                        from cis2hdl.core.matcher.value_matcher import extract_pkg_size
                        _fp_size = extract_pkg_size(_fp)
                        _is_valid_fp = (
                            _fp_size and _fp_size.isdigit() and len(_fp_size) >= 4
                        ) or _fp_size.startswith("BGA") or _fp_size in ("SOT", "QFN", "MLF")
                        if _is_valid_fp:
                            _comp.footprint = _fp
                    if _val and not _comp.value:
                        _comp.value = _val

            logger.info(
                "pstxnet: processed %d entries against %d components",
                len(_pstx_entries), len(components),
            )

        return components
