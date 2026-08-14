"""CrossValidator — EDIF ↔ DSN 交叉验证器（B1.15）。

自动比对 EDIF 路径和 Binary DSN 路径的解析结果，
检测器件数/引脚数/网络数/连接关系的不一致。

参考：
    - BACKEND_DESIGN.md §3.0b
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..ir.design import DesignIR

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """单个验证问题。"""

    severity: str  # "error", "warning", "info"
    category: str  # "count", "name", "connection", "pin", "net"
    message: str
    edif_value: Any = None
    dsn_value: Any = None

    def __str__(self) -> str:
        prefix = {"error": "ERROR", "warning": "WARN", "info": "INFO"}.get(
            self.severity, "???"
        )
        return f"[{prefix}] [{self.category}] {self.message}: EDIF={self.edif_value}, DSN={self.dsn_value}"


@dataclass
class ValidationReport:
    """交叉验证报告。"""

    edif_path: str = ""
    dsn_path: str = ""
    passed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def __str__(self) -> str:
        status = "PASSED" if self.passed else f"FAILED ({self.error_count} errors)"
        return (
            f"ValidationReport[{status}] "
            f"EDIF='{self.edif_path}' DSN='{self.dsn_path}' "
            f"errors={self.error_count} warnings={self.warning_count}"
        )


class CrossValidator:
    """EDIF ↔ DSN 交叉验证器。

    Usage:
        validator = CrossValidator()
        report = validator.validate(edif_ir, dsn_ir)
        if report.passed:
            print("Both parsers agree!")
    """

    def validate(
        self,
        edif_ir: DesignIR,
        dsn_ir: DesignIR,
        edif_path: str = "",
        dsn_path: str = "",
    ) -> ValidationReport:
        """对两路解析结果执行逐项比对。

        Args:
            edif_ir: EDIF 路径解析的 DesignIR。
            dsn_ir: Binary DSN 路径解析的 DesignIR。
            edif_path: EDIF 源文件路径（用于报告）。
            dsn_path: DSN 源文件路径（用于报告）。

        Returns:
            ValidationReport 包含所有差异。
        """
        report = ValidationReport(edif_path=edif_path, dsn_path=dsn_path)

        # ── Page count ──────────────────────────────────────────────
        edif_pages = len(edif_ir.pages)
        dsn_pages = len(dsn_ir.pages)
        if edif_pages != dsn_pages:
            report.issues.append(
                ValidationIssue(
                    severity="error",
                    category="count",
                    message="Page count mismatch",
                    edif_value=edif_pages,
                    dsn_value=dsn_pages,
                )
            )

        # ── Instance count ──────────────────────────────────────────
        edif_instances = sum(len(p.instances) for p in edif_ir.pages)
        dsn_instances = sum(len(p.instances) for p in dsn_ir.pages)
        if edif_instances != dsn_instances:
            report.issues.append(
                ValidationIssue(
                    severity="error",
                    category="count",
                    message="Instance count mismatch",
                    edif_value=edif_instances,
                    dsn_value=dsn_instances,
                )
            )

        # ── Net count ───────────────────────────────────────────────
        edif_nets = sum(len(p.nets) for p in edif_ir.pages)
        dsn_nets = sum(len(p.nets) for p in dsn_ir.pages)
        if edif_nets != dsn_nets:
            report.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="count",
                    message="Net count mismatch",
                    edif_value=edif_nets,
                    dsn_value=dsn_nets,
                )
            )

        # ── Per-instance reference comparison ───────────────────────
        edif_refs: set[str] = set()
        for p in edif_ir.pages:
            for inst in p.instances:
                edif_refs.add(inst.refdes)

        dsn_refs: set[str] = set()
        for p in dsn_ir.pages:
            for inst in p.instances:
                dsn_refs.add(inst.refdes)

        # Refs in EDIF but not DSN
        missing_in_dsn = edif_refs - dsn_refs
        for ref in sorted(missing_in_dsn):
            report.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="name",
                    message=f"Instance '{ref}' in EDIF but missing from DSN",
                    edif_value=ref,
                    dsn_value=None,
                )
            )

        # Refs in DSN but not EDIF
        missing_in_edif = dsn_refs - edif_refs
        for ref in sorted(missing_in_edif):
            report.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="name",
                    message=f"Instance '{ref}' in DSN but missing from EDIF",
                    edif_value=None,
                    dsn_value=ref,
                )
            )

        # ── Per-device pin count comparison ─────────────────────────
        self._compare_per_device_pin_counts(dsn_ir, edif_ir, report)

        # ── Net connection count comparison ─────────────────────────
        self._compare_net_connection_counts(dsn_ir, edif_ir, report)

        # ── Net connection consistency comparison ────────────────────
        self._compare_net_connection_consistency(dsn_ir, edif_ir, report)

        # ── Device type grouping comparison ──────────────────────────
        self._compare_by_device_type(dsn_ir, edif_ir, report)

        # ── Final verdict ───────────────────────────────────────────
        report.passed = report.error_count == 0

        logger.info(
            "Cross validation %s: %d errors, %d warnings",
            "PASSED" if report.passed else "FAILED",
            report.error_count,
            report.warning_count,
        )

        return report

    @staticmethod
    def _compare_per_device_pin_counts(
        dsn_ir: DesignIR,
        edf_ir: DesignIR,
        report: ValidationReport,
    ) -> None:
        """Compare pin count per device (refdes) between DSN and EDF.

        Only compares devices present in BOTH sources (refdes intersection).
        Reports mismatches where the same refdes has different pin counts.
        """
        dsn_by_refdes = dsn_ir.instances_by_refdes()
        edf_by_refdes = edf_ir.instances_by_refdes()

        common_refs = set(dsn_by_refdes.keys()) & set(edf_by_refdes.keys())
        mismatches = 0

        for refdes in sorted(common_refs):
            dsn_pins = len(dsn_by_refdes[refdes].pin_connections)
            edf_pins = len(edf_by_refdes[refdes].pin_connections)
            if dsn_pins != edf_pins:
                mismatches += 1
                if mismatches <= 20:  # Cap detailed reporting
                    report.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="pin",
                            message=f"Pin count mismatch for '{refdes}'",
                            edif_value=edf_pins,
                            dsn_value=dsn_pins,
                        )
                    )

        if mismatches > 20:
            report.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="pin",
                    message=f"Pin count mismatches: {mismatches - 20} more devices (capped)",
                    edif_value=mismatches,
                    dsn_value=mismatches,
                )
            )

        if mismatches == 0 and common_refs:
            report.issues.append(
                ValidationIssue(
                    severity="info",
                    category="pin",
                    message=f"Pin counts match for all {len(common_refs)} common devices",
                )
            )

    @staticmethod
    def _compare_net_connection_counts(
        dsn_ir: DesignIR,
        edf_ir: DesignIR,
        report: ValidationReport,
    ) -> None:
        """Compare net connection counts between DSN and EDF.

        Builds net name → connection count maps for both sources,
        then compares counts for nets present in both.
        """
        def _build_net_conn_map(design: DesignIR) -> dict[str, int]:
            result: dict[str, int] = {}
            for page in design.pages:
                for net in page.nets:
                    result[net.name] = len(net.connections)
            return result

        dsn_nets = _build_net_conn_map(dsn_ir)
        edf_nets = _build_net_conn_map(edf_ir)

        common_nets = set(dsn_nets.keys()) & set(edf_nets.keys())
        mismatches = 0

        for net_name in sorted(common_nets):
            dsn_conns = dsn_nets[net_name]
            edf_conns = edf_nets[net_name]
            if dsn_conns != edf_conns:
                mismatches += 1
                if mismatches <= 10:
                    report.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="net",
                            message=f"Net connection count mismatch for '{net_name}'",
                            edif_value=edf_conns,
                            dsn_value=dsn_conns,
                        )
                    )

        if mismatches > 10:
            report.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="net",
                    message=f"Net connection count mismatches: {mismatches - 10} more nets (capped)",
                )
            )

        if mismatches == 0 and common_nets:
            report.issues.append(
                ValidationIssue(
                    severity="info",
                    category="net",
                    message=f"Net connection counts match for all {len(common_nets)} common nets",
                )
            )

    @staticmethod
    def _compare_net_connection_consistency(
        dsn_ir: DesignIR,
        edf_ir: DesignIR,
        report: ValidationReport,
    ) -> None:
        """Compare net connection topology between DSN and EDF.

        Uses Jaccard similarity on connection_signature to identify
        corresponding nets across sources. Reports nets with:
          - Jaccard == 1.0: exact match（不报告，视为一致）
          - 0.8 <= Jaccard < 1.0: near match（info，可能是子网差异）
          - 0.0 < Jaccard < 0.8: partial match（warning，需注意）
          - Jaccard == 0.0: no match（info，net 名称在两个来源中完全不同）
        """
        dsn_nets = dsn_ir.net_connection_map()
        edf_nets = edf_ir.net_connection_map()

        # 对每个 DSN net，找到 Jaccard 最高的 EDF net
        exact = 0
        near = 0
        partial = 0
        unmatched = 0

        dsn_only = set(dsn_nets.keys()) - set(edf_nets.keys())
        edf_only = set(edf_nets.keys()) - set(dsn_nets.keys())

        for dsn_name in dsn_nets:
            dsn_sig = dsn_nets[dsn_name]
            if not dsn_sig:
                unmatched += 1
                continue

            best_jaccard = 0.0
            best_net = ""
            for edf_name, edf_sig in edf_nets.items():
                if not edf_sig:
                    continue
                intersection = len(dsn_sig & edf_sig)
                union = len(dsn_sig | edf_sig)
                jaccard = intersection / union if union > 0 else 0.0
                if jaccard > best_jaccard:
                    best_jaccard = jaccard
                    best_net = edf_name

            if best_jaccard == 1.0:
                exact += 1
            elif best_jaccard >= 0.8:
                near += 1
                if near <= 5:
                    report.issues.append(
                        ValidationIssue(
                            severity="info",
                            category="net",
                            message=f"Near match: DSN '{dsn_name}' ↔ EDF '{best_net}' (Jaccard={best_jaccard:.2f})",
                        )
                    )
            elif best_jaccard > 0.0:
                partial += 1
                if partial <= 10:
                    report.issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="net",
                            message=f"Partial match: DSN '{dsn_name}' ↔ EDF '{best_net}' (Jaccard={best_jaccard:.2f})",
                        )
                    )
            else:
                unmatched += 1

        report.issues.append(
            ValidationIssue(
                severity="info",
                category="net",
                message=f"Net topology: {exact} exact, {near} near, {partial} partial, {unmatched} unmatched",
            )
        )

        if dsn_only or edf_only:
            report.issues.append(
                ValidationIssue(
                    severity="warning",
                    category="net",
                    message=f"Net name mismatch: {len(dsn_only)} DSN-only nets, {len(edf_only)} EDF-only nets",
                )
            )

    @staticmethod
    def _compare_by_device_type(
        dsn_ir: DesignIR,
        edf_ir: DesignIR,
        report: ValidationReport,
    ) -> None:
        """Compare instance counts grouped by device type.

        Groups instances by category (Resistor, Capacitor, IC, etc.)
        and compares counts between DSN and EDF for each category.
        """
        dsn_cats = dsn_ir.instances_by_type()
        edf_cats = edf_ir.instances_by_type()

        all_cats = sorted(set(dsn_cats.keys()) | set(edf_cats.keys()))

        for cat in all_cats:
            dsn_count = len(dsn_cats.get(cat, []))
            edf_count = len(edf_cats.get(cat, []))

            if dsn_count != edf_count:
                severity = "warning" if abs(dsn_count - edf_count) > 5 else "info"
                report.issues.append(
                    ValidationIssue(
                        severity=severity,
                        category="count",
                        message=f"Device type '{cat}' count mismatch",
                        edif_value=edf_count,
                        dsn_value=dsn_count,
                    )
                )
            else:
                report.issues.append(
                    ValidationIssue(
                        severity="info",
                        category="count",
                        message=f"Device type '{cat}': {dsn_count} matched",
                    )
                )
