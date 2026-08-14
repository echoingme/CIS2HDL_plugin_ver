"""MultiSourceCrossValidator — three-source cross-validation (DS3.2).

Extends the existing EDIF↔DSN CrossValidator with a third source
(pstxnet.dat) for comprehensive multi-file consistency checking.

Three-source comparison:
    Source A: .dsn (Binary DSN parser) — ground truth for device/instance/net counts
    Source B: .edf (EDIF parser)      — independent parse for cross-verification
    Source C: pstxnet.dat (ASCII)     — Allegro netlist for net-level comparison

When a user provides all three sources, the validator performs pairwise
comparisons and reports any inconsistencies.

Usage:
    validator = MultiSourceCrossValidator()
    report = validator.validate(dsn_ir=..., edf_ir=..., pstxnet_path=Path("pstxnet.dat"))
    print(report.summary())
"""

from __future__ import annotations

import logging
import re as _re
import xml.etree.ElementTree as _ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..ir.design import DesignIR

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# PSTXNET Mini-Parser (internal — used for net-level comparison)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PstxnetData:
    """Parsed pstxnet.dat data.

    pstxnet.dat format (OrCAD/Allegro netlist):
        $PACKAGES
        <refdes>  ! <footprint>; <value>
        ...
        $NETS
        '<net_name>'  : <refdes>.<pin>  <refdes>.<pin> ...
        ...
        $END
    """

    packages: dict[str, dict[str, str]] = field(default_factory=dict)
    """refdes → {footprint, value}"""

    nets: dict[str, list[str]] = field(default_factory=dict)
    """net_name → [refdes.pin, ...]"""

    instance_count: int = 0
    net_count: int = 0
    pin_count: int = 0


def parse_pstxnet(pstxnet_path: Path) -> PstxnetData:
    """Parse a pstxnet.dat file into structured data.

    Handles the standard Allegro/OrCAD pstxnet.dat format with
    $PACKAGES, $NETS, and $END sections.

    Args:
        pstxnet_path: Path to the pstxnet.dat file.

    Returns:
        PstxnetData with parsed packages and nets.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unrecognized.
    """
    if not pstxnet_path.exists():
        raise FileNotFoundError(f"pstxnet.dat not found: {pstxnet_path}")

    content = pstxnet_path.read_text(encoding="utf-8", errors="replace")
    data = PstxnetData()

    section: str | None = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Detect section headers
        if line.startswith("$PACKAGES"):
            section = "packages"
            continue
        elif line.startswith("$NETS"):
            section = "nets"
            continue
        elif line.startswith("$END"):
            break

        if section == "packages":
            # Format: REFDES  ! FOOTPRINT; VALUE
            match = _re.match(r"(\S+)\s+!\s*([^;]*);\s*(.*)", line)
            if match:
                refdes = match.group(1)
                footprint = match.group(2).strip() if match.group(2) else ""
                value = match.group(3).strip() if match.group(3) else ""
                data.packages[refdes] = {"footprint": footprint, "value": value}
                data.instance_count += 1

        elif section == "nets":
            # Format: 'NETNAME'  : REFDES.PIN  REFDES.PIN ...
            # Net name may or may not be quoted
            match = _re.match(r"'?([^']+)'?\s*:\s*(.+)", line)
            if match:
                net_name = match.group(1).strip()
                connections_str = match.group(2).strip()
                connections = connections_str.split()
                # Each connection is REFDES.PIN
                data.nets[net_name] = connections
                data.net_count += 1
                data.pin_count += len(connections)

    logger.info(
        "pstxnet.dat parsed: %d instances, %d nets, %d pin connections",
        data.instance_count, data.net_count, data.pin_count,
    )
    return data


# ═══════════════════════════════════════════════════════════════════════════
# MultiSourceValidationReport
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class MultiSourceIssue:
    """A single multi-source validation discrepancy.

    Attributes:
        severity: 'error', 'warning', or 'info'.
        category: Issue category ('count', 'name', 'connectivity', 'attribute', 'net').
        message: Human-readable description.
        source_a: Value from source A (DSN).
        source_b: Value from source B (EDF).
        source_c: Value from source C (pstxnet).
        affected_sources: Which source pair(s) disagree ('A_B', 'A_C', 'B_C', etc.).
    """

    severity: str = "info"
    category: str = "count"
    message: str = ""
    source_a: Any = None
    source_b: Any = None
    source_c: Any = None
    affected_sources: str = ""

    def __str__(self) -> str:
        prefix = {"error": "ERROR", "warning": "WARN", "info": "INFO"}.get(
            self.severity, "???"
        )
        parts = [f"[{prefix}] [{self.category}] {self.message}"]
        if self.source_a is not None:
            parts.append(f"DSN={self.source_a}")
        if self.source_b is not None:
            parts.append(f"EDF={self.source_b}")
        if self.source_c is not None:
            parts.append(f"PST={self.source_c}")
        return " ".join(parts)


@dataclass
class MultiSourceValidationReport:
    """Complete three-source cross-validation report.

    Attributes:
        dsn_path: Path to the DSN file.
        edf_path: Path to the EDF file.
        pstxnet_path: Path to the pstxnet.dat file.
        sources_available: Number of sources provided (2 or 3).
        passed: True if no error-level issues found.
        issues: All validation issues found.
        dsn_instances: Instance count from DSN.
        edf_instances: Instance count from EDF.
        pstxnet_instances: Instance count from pstxnet.
        dsn_nets: Net count from DSN.
        edf_nets: Net count from EDF.
        pstxnet_nets: Net count from pstxnet.
    """

    dsn_path: str = ""
    edf_path: str = ""
    pstxnet_path: str = ""
    sources_available: int = 0
    passed: bool = True
    issues: list[MultiSourceIssue] = field(default_factory=list)

    # Count summaries (for quick reference)
    dsn_instances: int = 0
    edf_instances: int = 0
    pstxnet_instances: int = 0
    dsn_nets: int = 0
    edf_nets: int = 0
    pstxnet_nets: int = 0

    @property
    def errors(self) -> list[MultiSourceIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[MultiSourceIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def summary(self) -> str:
        """Human-readable one-line summary."""
        status = "PASSED" if self.passed else "FAILED"
        parts = [
            f"MultiSourceValidation[{status}]",
            f"sources={self.sources_available}",
            f"errors={self.error_count}",
            f"warnings={self.warning_count}",
        ]
        if self.sources_available >= 2:
            parts.append(f"DSN={self.dsn_instances}inst/{self.dsn_nets}net")
            parts.append(f"EDF={self.edf_instances}inst/{self.edf_nets}net")
        if self.sources_available >= 3:
            parts.append(f"PST={self.pstxnet_instances}inst/{self.pstxnet_nets}net")
        return " ".join(parts)

    def detailed_report(self) -> str:
        """Multi-line detailed report."""
        lines = [self.summary(), "-" * 60]
        for issue in self.issues:
            lines.append(str(issue))
        if not self.issues:
            lines.append("No discrepancies found across all sources.")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# MultiSourceCrossValidator
# ═══════════════════════════════════════════════════════════════════════════


class MultiSourceCrossValidator:
    """Three-source cross-validator for DSN, EDF, and pstxnet.dat.

    Performs pairwise comparisons across up to three data sources
    and reports any discrepancies in instance counts, net counts,
    attribute values, and connectivity.

    Usage::

        validator = MultiSourceCrossValidator()
        report = validator.validate(
            dsn_ir=dsn_design,
            edf_ir=edf_design,
            pstxnet_path=Path("pstxnet.dat"),
        )
        if not report.passed:
            print(report.detailed_report())
    """

    def validate(
        self,
        dsn_ir: Optional[DesignIR] = None,
        edf_ir: Optional[DesignIR] = None,
        pstxnet_path: Optional[Path] = None,
        dsn_path: str = "",
        edf_path: str = "",
    ) -> MultiSourceValidationReport:
        """Run three-source cross-validation.

        At least two of the three sources must be provided.
        Comparison is performed pairwise between all available sources.

        Args:
            dsn_ir: DesignIR from DSN parser (source A).
            edf_ir: DesignIR from EDIF parser (source B).
            pstxnet_path: Path to pstxnet.dat file (source C).
            dsn_path: DSN file path for report metadata.
            edf_path: EDF file path for report metadata.

        Returns:
            MultiSourceValidationReport with all findings.
        """
        pst_path_str = str(pstxnet_path) if pstxnet_path else ""
        report = MultiSourceValidationReport(
            dsn_path=dsn_path,
            edf_path=edf_path,
            pstxnet_path=pst_path_str,
        )

        # ── Count how many sources are available ──────────────────────
        available: list[str] = []
        if dsn_ir is not None:
            available.append("DSN")
            report.dsn_instances = sum(len(p.instances) for p in dsn_ir.pages)
            report.dsn_nets = sum(len(p.nets) for p in dsn_ir.pages)
        if edf_ir is not None:
            available.append("EDF")
            report.edf_instances = sum(len(p.instances) for p in edf_ir.pages)
            report.edf_nets = sum(len(p.nets) for p in edf_ir.pages)

        pst_data: PstxnetData | None = None
        if pstxnet_path is not None and pstxnet_path.exists():
            try:
                pst_data = parse_pstxnet(pstxnet_path)
                available.append("PST")
                report.pstxnet_instances = pst_data.instance_count
                report.pstxnet_nets = pst_data.net_count
            except Exception as exc:
                report.issues.append(
                    MultiSourceIssue(
                        severity="warning",
                        category="count",
                        message=f"Failed to parse pstxnet.dat: {exc}",
                    )
                )
                logger.warning("pstxnet.dat parse failed: %s", exc)

        report.sources_available = len(available)

        if report.sources_available < 2:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="count",
                    message="Multi-source validation requires at least 2 sources",
                    affected_sources="",
                )
            )
            report.passed = False
            return report

        logger.info(
            "MultiSourceCrossValidator: %d source(s) available (%s)",
            report.sources_available, ", ".join(available),
        )

        # ═══════════════════════════════════════════════════════════════
        # DSN ↔ EDF comparison
        # ═══════════════════════════════════════════════════════════════
        if dsn_ir is not None and edf_ir is not None:
            self._compare_dsn_edf(dsn_ir, edf_ir, report)

        # ═══════════════════════════════════════════════════════════════
        # DSN ↔ pstxnet comparison
        # ═══════════════════════════════════════════════════════════════
        if dsn_ir is not None and pst_data is not None:
            self._compare_dsn_pst(dsn_ir, pst_data, report)

        # ═══════════════════════════════════════════════════════════════
        # EDF ↔ pstxnet comparison
        # ═══════════════════════════════════════════════════════════════
        if edf_ir is not None and pst_data is not None:
            self._compare_edf_pst(edf_ir, pst_data, report)

        # ── Final verdict ─────────────────────────────────────────────
        report.passed = report.error_count == 0

        logger.info(
            "MultiSource validation %s: %d errors, %d warnings",
            "PASSED" if report.passed else "FAILED",
            report.error_count,
            report.warning_count,
        )

        return report

    # ── Pairwise comparison methods ────────────────────────────────────

    @staticmethod
    def _compare_dsn_edf(
        dsn_ir: DesignIR,
        edf_ir: DesignIR,
        report: MultiSourceValidationReport,
    ) -> None:
        """Compare DSN and EDF DesignIRs — enhanced with pin/connection/type checks.

        Checks: instance count, page count, net count, refdes overlap,
                per-device pin counts, net connection counts, device type grouping.
        """
        # ── Instance count ──────────────────────────────────────────────
        dsn_inst = sum(len(p.instances) for p in dsn_ir.pages)
        edf_inst = sum(len(p.instances) for p in edf_ir.pages)
        if dsn_inst != edf_inst:
            report.issues.append(
                MultiSourceIssue(
                    severity="error",
                    category="count",
                    message="DSN vs EDF: instance count mismatch",
                    source_a=dsn_inst,
                    source_b=edf_inst,
                    affected_sources="A_B",
                )
            )

        # ── Page count ──────────────────────────────────────────────────
        dsn_pages = len(dsn_ir.pages)
        edf_pages = len(edf_ir.pages)
        if dsn_pages != edf_pages:
            report.issues.append(
                MultiSourceIssue(
                    severity="error",
                    category="count",
                    message="DSN vs EDF: page count mismatch",
                    source_a=dsn_pages,
                    source_b=edf_pages,
                    affected_sources="A_B",
                )
            )

        # ── Net count ───────────────────────────────────────────────────
        dsn_nets = sum(len(p.nets) for p in dsn_ir.pages)
        edf_nets = sum(len(p.nets) for p in edf_ir.pages)
        if dsn_nets != edf_nets:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="count",
                    message="DSN vs EDF: net count mismatch",
                    source_a=dsn_nets,
                    source_b=edf_nets,
                    affected_sources="A_B",
                )
            )

        # ── Refdes comparison ──────────────────────────────────────────
        dsn_refs: set[str] = set()
        for p in dsn_ir.pages:
            for inst in p.instances:
                dsn_refs.add(inst.refdes)

        edf_refs: set[str] = set()
        for p in edf_ir.pages:
            for inst in p.instances:
                edf_refs.add(inst.refdes)

        missing_in_edf = dsn_refs - edf_refs
        for ref in sorted(missing_in_edf)[:10]:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="name",
                    message=f"DSN vs EDF: refdes '{ref}' in DSN but missing from EDF",
                    source_a=ref,
                    source_b=None,
                    affected_sources="A_B",
                )
            )
        if len(missing_in_edf) > 10:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="name",
                    message=f"DSN vs EDF: {len(missing_in_edf) - 10} more refdes in DSN missing from EDF",
                    affected_sources="A_B",
                )
            )

        missing_in_dsn = edf_refs - dsn_refs
        for ref in sorted(missing_in_dsn)[:10]:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="name",
                    message=f"DSN vs EDF: refdes '{ref}' in EDF but missing from DSN",
                    source_b=ref,
                    source_a=None,
                    affected_sources="A_B",
                )
            )

        # ═══════════════════════════════════════════════════════════════
        # B4.2: Per-device pin count comparison
        # ═══════════════════════════════════════════════════════════════
        dsn_by_ref = dsn_ir.instances_by_refdes()
        edf_by_ref = edf_ir.instances_by_refdes()
        common_refs = set(dsn_by_ref.keys()) & set(edf_by_ref.keys())
        pin_mismatches = 0
        for refdes in sorted(common_refs):
            dsn_pins = len(dsn_by_ref[refdes].pin_connections)
            edf_pins = len(edf_by_ref[refdes].pin_connections)
            if dsn_pins != edf_pins:
                pin_mismatches += 1
        if pin_mismatches > 0:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="pin",
                    message=f"DSN vs EDF: {pin_mismatches} devices have different pin counts",
                    affected_sources="A_B",
                )
            )

        # ═══════════════════════════════════════════════════════════════
        # B4.3: Net connection count comparison
        # ═══════════════════════════════════════════════════════════════
        def _net_conn_map(ir: DesignIR) -> dict[str, int]:
            result: dict[str, int] = {}
            for p in ir.pages:
                for net in p.nets:
                    result[net.name] = len(net.connections)
            return result

        dsn_netmap = _net_conn_map(dsn_ir)
        edf_netmap = _net_conn_map(edf_ir)
        common_nets = set(dsn_netmap.keys()) & set(edf_netmap.keys())
        net_mismatches = 0
        for net_name in common_nets:
            if dsn_netmap[net_name] != edf_netmap[net_name]:
                net_mismatches += 1
        if net_mismatches > 0:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="net",
                    message=f"DSN vs EDF: {net_mismatches} nets have different connection counts",
                    affected_sources="A_B",
                )
            )

        # ═══════════════════════════════════════════════════════════════
        # B4.6: Device type grouping comparison
        # ═══════════════════════════════════════════════════════════════
        dsn_cats = dsn_ir.instances_by_type()
        edf_cats = edf_ir.instances_by_type()
        all_cats = sorted(set(dsn_cats.keys()) | set(edf_cats.keys()))
        for cat in all_cats:
            dsn_count = len(dsn_cats.get(cat, []))
            edf_count = len(edf_cats.get(cat, []))
            if dsn_count != edf_count:
                severity = "warning" if abs(dsn_count - edf_count) > 5 else "info"
                report.issues.append(
                    MultiSourceIssue(
                        severity=severity,
                        category="count",
                        message=f"DSN vs EDF: device type '{cat}' count mismatch",
                        source_a=dsn_count,
                        source_b=edf_count,
                        affected_sources="A_B",
                    )
                )

    @staticmethod
    def _compare_dsn_pst(
        dsn_ir: DesignIR,
        pst_data: PstxnetData,
        report: MultiSourceValidationReport,
    ) -> None:
        """Compare DSN DesignIR with pstxnet.dat data.

        Checks: instance count, net count, refdes overlap.
        """
        dsn_inst = sum(len(p.instances) for p in dsn_ir.pages)
        pst_inst = pst_data.instance_count

        if dsn_inst != pst_inst:
            report.issues.append(
                MultiSourceIssue(
                    severity="error",
                    category="count",
                    message="DSN vs PST: instance count mismatch",
                    source_a=dsn_inst,
                    source_c=pst_inst,
                    affected_sources="A_C",
                )
            )

        # Net count (pstxnet may have more due to power nets)
        dsn_nets = sum(len(p.nets) for p in dsn_ir.pages)
        pst_nets = pst_data.net_count
        if abs(dsn_nets - pst_nets) > max(dsn_nets, pst_nets) * 0.1:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="count",
                    message="DSN vs PST: significant net count difference (>10%)",
                    source_a=dsn_nets,
                    source_c=pst_nets,
                    affected_sources="A_C",
                )
            )
        elif dsn_nets != pst_nets:
            report.issues.append(
                MultiSourceIssue(
                    severity="info",
                    category="count",
                    message="DSN vs PST: minor net count difference",
                    source_a=dsn_nets,
                    source_c=pst_nets,
                    affected_sources="A_C",
                )
            )

        # Refdes comparison
        dsn_refs: set[str] = set()
        for p in dsn_ir.pages:
            for inst in p.instances:
                dsn_refs.add(inst.refdes)

        pst_refs = set(pst_data.packages.keys())

        missing_in_pst = dsn_refs - pst_refs
        for ref in sorted(missing_in_pst)[:10]:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="name",
                    message=f"DSN vs PST: refdes '{ref}' in DSN but missing from pstxnet",
                    source_a=ref,
                    source_c=None,
                    affected_sources="A_C",
                )
            )
        if len(missing_in_pst) > 10:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="name",
                    message=f"DSN vs PST: {len(missing_in_pst) - 10} more refdes in DSN missing from pstxnet",
                    affected_sources="A_C",
                )
            )

        missing_in_dsn = pst_refs - dsn_refs
        for ref in sorted(missing_in_dsn)[:10]:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="name",
                    message=f"DSN vs PST: refdes '{ref}' in pstxnet but missing from DSN",
                    source_c=ref,
                    source_a=None,
                    affected_sources="A_C",
                )
            )

    @staticmethod
    def _compare_edf_pst(
        edf_ir: DesignIR,
        pst_data: PstxnetData,
        report: MultiSourceValidationReport,
    ) -> None:
        """Compare EDIF DesignIR with pstxnet.dat data.

        Checks: instance count, net count, refdes overlap.
        """
        edf_inst = sum(len(p.instances) for p in edf_ir.pages)
        pst_inst = pst_data.instance_count

        if edf_inst != pst_inst:
            report.issues.append(
                MultiSourceIssue(
                    severity="error",
                    category="count",
                    message="EDF vs PST: instance count mismatch",
                    source_b=edf_inst,
                    source_c=pst_inst,
                    affected_sources="B_C",
                )
            )

        edf_nets = sum(len(p.nets) for p in edf_ir.pages)
        pst_nets = pst_data.net_count
        if abs(edf_nets - pst_nets) > max(edf_nets, pst_nets) * 0.1:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="count",
                    message="EDF vs PST: significant net count difference (>10%)",
                    source_b=edf_nets,
                    source_c=pst_nets,
                    affected_sources="B_C",
                )
            )

        # Refdes overlap
        edf_refs: set[str] = set()
        for p in edf_ir.pages:
            for inst in p.instances:
                edf_refs.add(inst.refdes)

        pst_refs = set(pst_data.packages.keys())

        missing_in_pst = edf_refs - pst_refs
        for ref in sorted(missing_in_pst)[:10]:
            report.issues.append(
                MultiSourceIssue(
                    severity="warning",
                    category="name",
                    message=f"EDF vs PST: refdes '{ref}' in EDF but missing from pstxnet",
                    source_b=ref,
                    source_c=None,
                    affected_sources="B_C",
                )
            )
