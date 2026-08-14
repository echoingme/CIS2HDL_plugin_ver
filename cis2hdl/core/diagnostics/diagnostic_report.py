"""Diagnostic Report data models and ConversionReadinessEvaluator (D1.5 + D1.6).

All diagnostic information flows through these canonical data structures.
Frontend-GUI can render them directly as colored panels and progress bars.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import IntEnum, Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Enums ──────────────────────────────────────────────────────────────────


class Severity(IntEnum):
    """Error severity — FATAL blocks conversion, ERROR is recoverable, WARNING advisory."""

    FATAL = 0
    ERROR = 1
    WARNING = 2
    INFO = 3


class ActionVerb(str, Enum):
    """Standardized action verbs for user-facing suggestions."""

    PROVIDE = "请提供"
    REPAIR = "请修复"
    UPGRADE = "请升级"
    UPLOAD = "请上传"
    CONFIRM = "请确认"
    IGNORE = "可忽略"
    CHECK = "请检查"
    RERUN = "请重新运行"


class FileState(str, Enum):
    """Per-file parse status."""

    NOT_PROVIDED = "NOT_PROVIDED"  # User did not supply this file
    FOUND_OK = "FOUND_OK"  # Present, format valid, parsed successfully
    MISSING = "MISSING"  # Required but not found
    CORRUPTED = "CORRUPTED"  # Found but binary structure is damaged
    PARTIAL = "PARTIAL"  # Found and partially parsable (some streams broken)
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"  # Format version not supported
    BAD_FORMAT = "BAD_FORMAT"  # Wrong magic bytes / not a valid file type


# ── Data models ────────────────────────────────────────────────────────────


@dataclass
class DiagnosisError:
    """A single diagnostic entry. Maps to the 31-error-code system."""

    code: int
    severity: Severity
    category: str  # FILE / PARSE / MATCH / NET / PIN / SYMBOL / CONFIG
    message: str
    detail: str = ""
    suggestion: str = ""
    source_file: str = ""
    source_offset: int = 0
    can_ignore: bool = False

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.name,
            "category": self.category,
            "message": self.message,
            "detail": self.detail,
            "suggestion": self.suggestion,
            "source_file": self.source_file,
            "source_offset": self.source_offset,
            "can_ignore": self.can_ignore,
        }

    def __repr__(self) -> str:
        return (
            f"[{self.severity.name}] [{self.category}] E{self.code:02d}: {self.message}"
        )


@dataclass
class ActionItem:
    """A user-actionable suggestion."""

    verb: ActionVerb
    target: str  # What to act on (file path, component name, etc.)
    reason: str  # Why this action is needed
    priority: int = 0  # 0=highest, larger=lower

    def __repr__(self) -> str:
        return f"{self.verb.value} {self.target} — {self.reason}"


@dataclass
class FileStatus:
    """Single file entry in the project inventory."""

    path: Path
    file_type: str  # DSN / OLB / OPJ / EDF / DBK / PSTXNET / PSTXPRT / PSTCHIP
    state: FileState = FileState.NOT_PROVIDED
    size: int = 0
    summary: str = ""
    detail: str = ""
    data_quality: float = 0.0  # 0.0–1.0

    @property
    def is_ok(self) -> bool:
        return self.state == FileState.FOUND_OK

    @property
    def is_blocking(self) -> bool:
        return self.state in (FileState.MISSING, FileState.CORRUPTED, FileState.BAD_FORMAT)


@dataclass
class DSNInternalInventory:
    """Internal structure of the DSN CFB container."""

    dsn_path: str = ""

    # Stream presence
    has_root: bool = False
    has_views: bool = False
    has_pages: bool = False
    has_cache: bool = False
    has_library: bool = False
    has_hierarchy: bool = False

    # Page stats
    pages_parsed: int = 0
    total_pages: int = 0
    page_details: dict[str, bool] = field(default_factory=dict)  # page_name → success

    # Instance stats
    instances_parsed: int = 0
    total_instances: int = 0

    # Dependencies
    olb_references: list[str] = field(default_factory=list)
    referenced_packages: dict[str, tuple[str, int]] = field(
        default_factory=dict
    )  # package → (olb_name, instance_count)

    # Library
    strlst_entries: int = 0
    cache_entries: int = 0

    @property
    def stream_integrity_score(self) -> float:
        """0.0–1.0 score for how many expected streams were found."""
        expected = ["root", "views", "pages", "cache", "library", "hierarchy"]
        found = sum(1 for e in expected if getattr(self, f"has_{e}", False))
        return found / len(expected) if expected else 0.0

    @property
    def page_completeness(self) -> float:
        if self.total_pages == 0:
            return 1.0
        return self.pages_parsed / self.total_pages

    def summary_text(self) -> str:
        return (
            f"DSN: {self.pages_parsed}/{self.total_pages} pages, "
            f"{self.instances_parsed} instances, "
            f"{self.cache_entries} cache entries, "
            f"{self.strlst_entries} strLst entries, "
            f"{len(self.olb_references)} OLB references"
        )


@dataclass
class ProjectInventory:
    """Complete project file inventory."""

    project_root: Path = field(default_factory=Path)
    files: dict[str, FileStatus] = field(default_factory=dict)
    dsn_internal: DSNInternalInventory = field(default_factory=DSNInternalInventory)
    errors: list[DiagnosisError] = field(default_factory=list)
    missing_olbs: list[str] = field(default_factory=list)
    actions: list[ActionItem] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.files.values() if f.is_ok)

    @property
    def problem_count(self) -> int:
        return sum(1 for f in self.files.values() if not f.is_ok and f.state != FileState.NOT_PROVIDED)

    @property
    def fatal_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == Severity.FATAL)

    def has_fatal_errors(self) -> bool:
        return self.fatal_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "files": {k: _file_status_to_dict(v) for k, v in self.files.items()},
            "dsn_internal": {
                "pages_parsed": self.dsn_internal.pages_parsed,
                "total_pages": self.dsn_internal.total_pages,
                "instances_parsed": self.dsn_internal.instances_parsed,
                "total_instances": self.dsn_internal.total_instances,
                "olb_references": self.dsn_internal.olb_references,
                "stream_integrity": self.dsn_internal.stream_integrity_score,
            },
            "errors": [e.to_dict() for e in self.errors],
            "missing_olbs": self.missing_olbs,
            "actions": [a.__repr__() for a in self.actions],
        }


def _file_status_to_dict(fs: FileStatus) -> dict:
    return {
        "path": str(fs.path),
        "type": fs.file_type,
        "state": fs.state.value,
        "size": fs.size,
        "summary": fs.summary,
        "quality": fs.data_quality,
    }


@dataclass
class ReadinessReport:
    """Pre-conversion readiness assessment."""

    can_convert: bool = False
    can_convert_with_degradation: bool = False
    degradation_detail: str = ""
    logic_score: float = 0.0  # 0.0–1.0
    coordinate_score: float = 0.0
    matchability_score: float = 0.0
    symbol_score: float = 0.0
    overall_score: float = 0.0
    suggestions: list[str] = field(default_factory=list)
    recommended_path: str = ""

    def summary(self) -> str:
        if self.can_convert:
            return f"✅ Ready for conversion (quality: {self.overall_score:.0%})"
        elif self.can_convert_with_degradation:
            return f"⚠️ Degraded conversion possible — {self.degradation_detail}"
        else:
            return "❌ Cannot convert — check FATAL errors"


@dataclass
class DiagnosticReport:
    """Top-level diagnostic report."""

    inventory: ProjectInventory = field(default_factory=ProjectInventory)
    readiness: ReadinessReport = field(default_factory=ReadinessReport)
    errors: list[DiagnosisError] = field(default_factory=list)
    warnings: list[DiagnosisError] = field(default_factory=list)
    infos: list[DiagnosisError] = field(default_factory=list)

    @property
    def fatal_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == Severity.FATAL)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def all_errors_grouped(self) -> dict[str, list[DiagnosisError]]:
        """Group all errors by category for UI rendering."""
        groups: dict[str, list[DiagnosisError]] = {}
        for e in self.errors + self.warnings + self.infos:
            groups.setdefault(e.category, []).append(e)
        return groups

    def to_json(self) -> str:
        """Serialize to JSON for frontend consumption."""
        data = {
            "fatal_count": self.fatal_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": len(self.infos),
            "can_convert": self.readiness.can_convert,
            "can_degraded": self.readiness.can_convert_with_degradation,
            "overall_score": self.readiness.overall_score,
            "scores": {
                "logic": self.readiness.logic_score,
                "coordinate": self.readiness.coordinate_score,
                "matchability": self.readiness.matchability_score,
                "symbol": self.readiness.symbol_score,
            },
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [e.to_dict() for e in self.warnings],
            "infos": [e.to_dict() for e in self.infos],
            "suggestions": self.readiness.suggestions,
            "missing_olbs": self.inventory.missing_olbs,
            "file_states": {k: v.state.value for k, v in self.inventory.files.items()},
        }
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    def to_summary_text(self) -> str:
        """Human-readable single-line summary."""
        status = "READY" if self.readiness.can_convert else "NOT READY"
        return (
            f"DiagnosticReport[{status}] "
            f"errors={self.error_count} warnings={self.warning_count} "
            f"score={self.readiness.overall_score:.0%}"
        )


# ── ConversionReadinessEvaluator (D1.5) ────────────────────────────────────


class ConversionReadinessEvaluator:
    """Evaluate whether the current file set is sufficient for conversion.

    Four-dimensional weighted scoring:
        - Logic completeness    (weight 0.40) — devices, pins, nets
        - Coordinate availability (weight 0.25) — instance positions, wire paths
        - Device matchability    (weight 0.20) — pin names, attributes, footprint
        - Symbol generatability  (weight 0.15) — symbol graphics, property display
    """

    WEIGHTS = {
        "logic": 0.40,
        "coordinate": 0.25,
        "matchability": 0.20,
        "symbol": 0.15,
    }

    def evaluate(self, inventory: ProjectInventory) -> ReadinessReport:
        """Generate readiness report from project inventory.

        Args:
            inventory: Filled ProjectInventory from FileInventory + DSNInternalInventory.

        Returns:
            ReadinessReport with scores and actionable suggestions.
        """
        report = ReadinessReport()

        # ── Logic score ────────────────────────────────────────────
        dsn = inventory.dsn_internal
        if dsn.total_pages == 0:
            report.logic_score = 0.0
        else:
            page_factor = dsn.page_completeness
            inst_factor = dsn.instances_parsed / max(dsn.total_instances, 1)
            stream_factor = dsn.stream_integrity_score
            report.logic_score = (page_factor * 0.4 + inst_factor * 0.4 + stream_factor * 0.2)

        # ── Coordinate score ───────────────────────────────────────
        # Coordinates come from Binary DSN parsing (PlacedInstance.locX/Y, Wire, etc.)
        # If DSN parsed with instances, coordinates are available.
        dsn_file = inventory.files.get("*.dsn") or _find_dsn_file(inventory)
        if dsn_file and dsn_file.state == FileState.FOUND_OK:
            report.coordinate_score = report.logic_score  # Coordinates come with logic in DSN
        elif inventory.files.get("*.edf") and inventory.files["*.edf"].state == FileState.FOUND_OK:
            # EDIF-only: no coordinates
            report.coordinate_score = 0.0
            report.suggestions.append("EDIF 文件不含坐标 — 器件位置和连线路径将不可用")
        else:
            report.coordinate_score = 0.0

        # ── Matchability score ─────────────────────────────────────
        # Requires pin names, attributes, footprint — from OLB or DSN Cache
        olb_count = sum(
            1 for f in inventory.files.values()
            if f.file_type == "OLB" and f.is_ok
        )
        if olb_count > 0:
            report.matchability_score = min(1.0, 0.5 + olb_count * 0.1)
        elif dsn.cache_entries > 0:
            # DSN Cache has embedded device definitions (no pin names)
            report.matchability_score = 0.4
            report.suggestions.append(
                "缺少 OLB 文件：可从 DSN Cache 提取基础器件信息（无引脚名），提供 OLB 可大幅提升匹配准确率"
            )
        else:
            report.matchability_score = 0.1

        # ── Symbol score ───────────────────────────────────────────
        if olb_count > 0:
            report.symbol_score = 0.8
        elif dsn.cache_entries > 0:
            report.symbol_score = 0.3  # Default rectangle symbols
            report.suggestions.append(
                "缺少 OLB 文件：器件符号将使用默认矩形，提供 OLB 可保留原始符号图形"
            )
        else:
            report.symbol_score = 0.0

        # ── Overall ────────────────────────────────────────────────
        report.overall_score = (
            report.logic_score * self.WEIGHTS["logic"]
            + report.coordinate_score * self.WEIGHTS["coordinate"]
            + report.matchability_score * self.WEIGHTS["matchability"]
            + report.symbol_score * self.WEIGHTS["symbol"]
        )

        # ── Conversion decision ────────────────────────────────────
        fatal = inventory.has_fatal_errors()
        if fatal:
            report.can_convert = False
            report.can_convert_with_degradation = False
        elif report.overall_score >= 0.75:
            report.can_convert = True
            report.can_convert_with_degradation = False
        elif report.overall_score >= 0.40:
            report.can_convert = False
            report.can_convert_with_degradation = True
            report.degradation_detail = _build_degradation_detail(report)
        else:
            report.can_convert = False
            report.can_convert_with_degradation = False

        # ── Recommend path ─────────────────────────────────────────
        if report.can_convert:
            report.recommended_path = "FULL_CONVERSION"
        elif report.can_convert_with_degradation:
            report.recommended_path = "DEGRADED_CONVERSION"
        else:
            report.recommended_path = "BLOCKED"

        logger.info(
            "Readiness: %s score=%.2f logic=%.2f coord=%.2f match=%.2f sym=%.2f",
            report.recommended_path,
            report.overall_score,
            report.logic_score,
            report.coordinate_score,
            report.matchability_score,
            report.symbol_score,
        )
        return report


def _find_dsn_file(inventory: ProjectInventory) -> FileStatus | None:
    """Find the DSN FileStatus in the inventory."""
    for f in inventory.files.values():
        if f.file_type == "DSN":
            return f
    return None


def _build_degradation_detail(report: ReadinessReport) -> str:
    """Build human-readable degradation explanation."""
    parts: list[str] = []
    if report.logic_score < 0.8:
        parts.append(f"逻辑数据不完整 ({report.logic_score:.0%})")
    if report.coordinate_score < 0.5:
        parts.append("坐标不可用（器件位置/连线丢失）")
    if report.matchability_score < 0.6:
        parts.append("器件匹配受限（缺少 OLB 库）")
    if report.symbol_score < 0.5:
        parts.append("使用默认符号（缺少原始符号图形）")
    return "; ".join(parts) if parts else "轻微数据损失"
