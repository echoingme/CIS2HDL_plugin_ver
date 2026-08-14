"""ErrorDiagnosisEngine — 31 error code system for CIS to HDL conversion diagnostics.

Provides the central error code dictionary, diagnosis aggregation, classification
from Python exceptions, and recovery suggestion generation.

Error code segments:
    1-10  — File-level errors (existence, format, version, dependencies)
    11-20 — Parse-level errors (syntax, structure, overflow)
    21-30 — Semantic-level errors (pins, nets, matching, power)
    31-40 — Generation-level errors (framework defined, Phase III implementation planned)
    41-50 — Reserved for future expansion
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from .diagnostic_report import (
    Severity,
    DiagnosisError,
    DiagnosticReport,
    ReadinessReport,
    ProjectInventory,
)
from ..exceptions import (
    CIS2HDLParseError,
    CIS2HDLMatchError,
    CIS2HDLConfigError,
)

logger = logging.getLogger(__name__)


# ── Error Code Templates ────────────────────────────────────────────────────


@dataclass
class ErrorCodeTemplate:
    """Template for a single error code in the 31-code system."""

    code: int
    name: str
    severity: Severity
    category: str
    message: str
    suggestion: str = ""
    can_ignore: bool = False
    phase: str = "I"  # I, II, or III


# ── Complete 31-error-code dictionary ───────────────────────────────────────


ERROR_CODES: ClassVar[dict[int, ErrorCodeTemplate]] = {
    # ════════════════════════════════════════════════════════════════════
    # File-level errors (1-10)
    # ════════════════════════════════════════════════════════════════════
    1: ErrorCodeTemplate(
        code=1,
        name="FILE_MISSING",
        severity=Severity.FATAL,
        category="FILE",
        message="必需文件缺失",
        suggestion="请提供完整的项目文件集（.dsn / .olb / .opj）",
        can_ignore=False,
        phase="I",
    ),
    2: ErrorCodeTemplate(
        code=2,
        name="BAD_FORMAT",
        severity=Severity.ERROR,
        category="FILE",
        message="文件格式无效",
        suggestion="请确认文件来源正确，文件可能已损坏",
        can_ignore=False,
        phase="I",
    ),
    3: ErrorCodeTemplate(
        code=3,
        name="FILE_CORRUPTED",
        severity=Severity.FATAL,
        category="FILE",
        message="文件已损坏",
        suggestion="请从备份恢复或重新生成此文件",
        can_ignore=False,
        phase="I",
    ),
    4: ErrorCodeTemplate(
        code=4,
        name="VERSION_OLD",
        severity=Severity.WARNING,
        category="FILE",
        message="CFB 版本较旧",
        suggestion="建议使用 OrCAD 16.6+ 重新保存项目文件",
        can_ignore=True,
        phase="I",
    ),
    5: ErrorCodeTemplate(
        code=5,
        name="VERSION_NEW",
        severity=Severity.WARNING,
        category="FILE",
        message="CFB 版本较新",
        suggestion="格式版本尚在验证中，如有解析异常请反馈",
        can_ignore=True,
        phase="I",
    ),
    6: ErrorCodeTemplate(
        code=6,
        name="OLB_REF_MISSING",
        severity=Severity.ERROR,
        category="FILE",
        message="OLB 库引用缺失",
        suggestion="请上传缺失的 OLB 文件以获取器件引脚名称和属性",
        can_ignore=True,
        phase="I",
    ),
    7: ErrorCodeTemplate(
        code=7,
        name="HDL_LIB_NOT_FOUND",
        severity=Severity.FATAL,
        category="FILE",
        message="HDL 库目录不存在或无法访问",
        suggestion="请在设置中配置正确的 HDL 库路径",
        can_ignore=False,
        phase="II",
    ),
    8: ErrorCodeTemplate(
        code=8,
        name="HDL_LIB_EMPTY",
        severity=Severity.ERROR,
        category="FILE",
        message="HDL 库目录为空（未发现任何器件）",
        suggestion="请确认 HDL 库路径正确，库目录应包含器件子目录",
        can_ignore=False,
        phase="II",
    ),
    9: ErrorCodeTemplate(
        code=9,
        name="CHIPS_PRT_MISSING",
        severity=Severity.WARNING,
        category="FILE",
        message="器件缺少 chips.prt 引脚定义文件",
        suggestion="请确认 HDL 库器件目录结构完整（需包含 chips/ 子目录）",
        can_ignore=True,
        phase="II",
    ),
    10: ErrorCodeTemplate(
        code=10,
        name="PART_PTF_MISSING",
        severity=Severity.WARNING,
        category="FILE",
        message="器件缺少 part.ptf 属性表文件",
        suggestion="请确认 HDL 库器件目录结构完整（需包含 part_table/ 子目录）",
        can_ignore=True,
        phase="II",
    ),

    # ════════════════════════════════════════════════════════════════════
    # Parse-level errors (11-20)
    # ════════════════════════════════════════════════════════════════════
    11: ErrorCodeTemplate(
        code=11,
        name="PREAMBLE_MISMATCH",
        severity=Severity.ERROR,
        category="PARSE",
        message="EDIF 前导声明不匹配",
        suggestion="请检查 EDIF 文件是否为有效的 Cadence CIS 输出",
        can_ignore=False,
        phase="I",
    ),
    12: ErrorCodeTemplate(
        code=12,
        name="STRUCTURE_OVERFLOW",
        severity=Severity.ERROR,
        category="PARSE",
        message="文件结构溢出 — 嵌套层级超限",
        suggestion="请检查文件是否过大或异常嵌套",
        can_ignore=False,
        phase="I",
    ),
    13: ErrorCodeTemplate(
        code=13,
        name="STRLST_INDEX_ERROR",
        severity=Severity.ERROR,
        category="PARSE",
        message="strLst 字符串表索引越界",
        suggestion="请尝试重新保存 DSN 文件以重建内部索引",
        can_ignore=False,
        phase="I",
    ),
    14: ErrorCodeTemplate(
        code=14,
        name="PAGE_PARSE_FAILED",
        severity=Severity.ERROR,
        category="PARSE",
        message="页面解析失败",
        suggestion="该页面可能包含不兼容的元素，请检查原始设计",
        can_ignore=True,
        phase="I",
    ),
    15: ErrorCodeTemplate(
        code=15,
        name="CHIPS_PRT_SYNTAX",
        severity=Severity.ERROR,
        category="PARSE",
        message="chips.prt 语法错误",
        suggestion="请检查 HDL 库中 chips.prt 文件格式是否正确",
        can_ignore=False,
        phase="II",
    ),

    # ════════════════════════════════════════════════════════════════════
    # Semantic-level errors (21-30)
    # ════════════════════════════════════════════════════════════════════
    21: ErrorCodeTemplate(
        code=21,
        name="PIN_NAME_MISSING",
        severity=Severity.WARNING,
        category="MATCH",
        message="引脚名称缺失 — 匹配中缺少引脚映射",
        suggestion="请提供 OLB 文件或在匹配审核面板中手动映射引脚",
        can_ignore=True,
        phase="II",
    ),
    22: ErrorCodeTemplate(
        code=22,
        name="PIN_NUMBER_MISSING",
        severity=Severity.ERROR,
        category="PIN",
        message="引脚编号不存在 — 源引脚映射到的目标引脚在 HDL 库中不存在",
        suggestion="请检查引脚映射配置，或将源引脚映射到目标器件的可用引脚",
        can_ignore=True,
        phase="II",
    ),
    23: ErrorCodeTemplate(
        code=23,
        name="PIN_COUNT_MISMATCH",
        severity=Severity.ERROR,
        category="PIN",
        message="引脚总数不匹配 — 源器件与目标器件引脚数量不一致",
        suggestion="请检查源器件与目标器件是否对应同一型号，或手动调整引脚映射",
        can_ignore=True,
        phase="II",
    ),
    24: ErrorCodeTemplate(
        code=24,
        name="NET_NAME_ILLEGAL_CHARS",
        severity=Severity.WARNING,
        category="NET",
        message="网络名包含非法字符 — 将自动规范化",
        suggestion="请确认规范化后的网络名可接受，或在源文件中修正",
        can_ignore=True,
        phase="II",
    ),
    25: ErrorCodeTemplate(
        code=25,
        name="NET_CLASSIFICATION_UNEXPECTED",
        severity=Severity.WARNING,
        category="NET",
        message="网络分类与预期不一致 — ISCF 4 类模型检查",
        suggestion="请检查原始设计中的网络分类是否正确",
        can_ignore=True,
        phase="II",
    ),
    26: ErrorCodeTemplate(
        code=26,
        name="POWER_PIN_DUPLICATE",
        severity=Severity.WARNING,
        category="PIN",
        message="重复电源引脚 — 同一电源引脚名称在器件中多次定义",
        suggestion="请检查 HDL 库中该器件的引脚定义，移除重复的电源引脚",
        can_ignore=True,
        phase="II",
    ),
    27: ErrorCodeTemplate(
        code=27,
        name="POWER_PIN_UNCONNECTED",
        severity=Severity.WARNING,
        category="PIN",
        message="电源引脚未连接或未标记 — 疑似电源引脚没有正确类型标记或连接",
        suggestion="请确认电源引脚的连接状态和类型标记",
        can_ignore=True,
        phase="II",
    ),
    28: ErrorCodeTemplate(
        code=28,
        name="MATCH_NOT_FOUND",
        severity=Severity.WARNING,
        category="MATCH",
        message="器件匹配未找到 — 所有自动匹配阶段均失败",
        suggestion="请在匹配审核面板中为该器件手动选择 HDL 对应器件",
        can_ignore=True,
        phase="II",
    ),
    29: ErrorCodeTemplate(
        code=29,
        name="MATCH_LOW_CONFIDENCE",
        severity=Severity.INFO,
        category="MATCH",
        message="器件匹配置信度较低 — 建议人工审核",
        suggestion="请在匹配审核面板中确认或修正此匹配结果",
        can_ignore=True,
        phase="II",
    ),
    30: ErrorCodeTemplate(
        code=30,
        name="BUS_EXPAND_AMBIGUOUS",
        severity=Severity.WARNING,
        category="NET",
        message="总线展开方向不明确 — 无法确定展开顺序",
        suggestion="请确认总线的展开方向（升序/降序）",
        can_ignore=True,
        phase="II",
    ),

    # ════════════════════════════════════════════════════════════════════
    # Generation-level errors (31-40) — framework defined, Phase III
    # ════════════════════════════════════════════════════════════════════
    31: ErrorCodeTemplate(
        code=31,
        name="GENERATION_FAILED",
        severity=Severity.ERROR,
        category="GEN",
        message="HDL 文件生成失败",
        suggestion="请检查输出目录权限和磁盘空间",
        can_ignore=False,
        phase="III",
    ),
    32: ErrorCodeTemplate(
        code=32,
        name="WRITER_UNAVAILABLE",
        severity=Severity.ERROR,
        category="GEN",
        message="对应的 Writer 不可用",
        suggestion="请确认目标格式的 Writer 已正确注册",
        can_ignore=False,
        phase="III",
    ),
    33: ErrorCodeTemplate(
        code=33,
        name="OUTPUT_DIR_ERROR",
        severity=Severity.ERROR,
        category="GEN",
        message="输出目录错误 — 无法创建或写入",
        suggestion="请检查输出目录权限",
        can_ignore=False,
        phase="III",
    ),
    34: ErrorCodeTemplate(
        code=34,
        name="TEMPLATE_ERROR",
        severity=Severity.ERROR,
        category="GEN",
        message="输出模板错误",
        suggestion="请检查模板文件完整性",
        can_ignore=False,
        phase="III",
    ),

    # ════════════════════════════════════════════════════════════════════
    # Reserved (41-50)
    # ════════════════════════════════════════════════════════════════════
    41: ErrorCodeTemplate(
        code=41,
        name="RESERVED_41",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 41)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    42: ErrorCodeTemplate(
        code=42,
        name="RESERVED_42",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 42)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    43: ErrorCodeTemplate(
        code=43,
        name="RESERVED_43",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 43)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    44: ErrorCodeTemplate(
        code=44,
        name="RESERVED_44",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 44)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    45: ErrorCodeTemplate(
        code=45,
        name="RESERVED_45",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 45)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    46: ErrorCodeTemplate(
        code=46,
        name="RESERVED_46",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 46)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    47: ErrorCodeTemplate(
        code=47,
        name="RESERVED_47",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 47)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    48: ErrorCodeTemplate(
        code=48,
        name="RESERVED_48",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 48)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    49: ErrorCodeTemplate(
        code=49,
        name="RESERVED_49",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 49)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),
    50: ErrorCodeTemplate(
        code=50,
        name="RESERVED_50",
        severity=Severity.INFO,
        category="GEN",
        message="(保留错误码 50)",
        suggestion="",
        can_ignore=True,
        phase="III",
    ),

    # OLB integrity errors (51-55)
    51: ErrorCodeTemplate(
        code=51,
        name="OLB_PACKAGE_MISSING",
        severity=Severity.ERROR,
        category="FILE",
        message="OLB Package 流缺失",
        suggestion="OLB 文件可能已损坏，请从备份恢复或使用 OrCAD 重新保存",
        can_ignore=False,
        phase="III",
    ),
    52: ErrorCodeTemplate(
        code=52,
        name="OLB_DEVICE_MISSING",
        severity=Severity.ERROR,
        category="PIN",
        message="OLB Device 引脚定义缺失",
        suggestion="Package 缺少 Device 流，请确认 OLB 文件完整性",
        can_ignore=True,
        phase="III",
    ),
    53: ErrorCodeTemplate(
        code=53,
        name="OLB_PIN_MAP_EMPTY",
        severity=Severity.WARNING,
        category="PIN",
        message="OLB Device 引脚映射为空",
        suggestion="该器件没有定义任何引脚，请确认是否为预期行为",
        can_ignore=True,
        phase="III",
    ),
    54: ErrorCodeTemplate(
        code=54,
        name="OLB_SYMBOL_MISSING",
        severity=Severity.WARNING,
        category="SYMBOL",
        message="OLB NormalView 符号图形缺失",
        suggestion="Package 缺少符号图形，将使用默认矩形符号",
        can_ignore=True,
        phase="III",
    ),
    55: ErrorCodeTemplate(
        code=55,
        name="OLB_SYMBOL_EMPTY",
        severity=Severity.WARNING,
        category="SYMBOL",
        message="OLB NormalView 符号图形为空",
        suggestion="该器件的符号图形不包含任何几何元素，请检查 OLB 文件",
        can_ignore=True,
        phase="III",
    ),
}


# ── ErrorDiagnosisEngine ────────────────────────────────────────────────────


class ErrorDiagnosisEngine:
    """Central error diagnosis engine with the 31-error-code system.

    Provides:
      - ERROR_CODES: Class-level dictionary of all error code templates.
      - diagnose(): Aggregate DiagnosisError list into a structured DiagnosticReport.
      - classify(): Infer error code from Python exception type.
      - aggregate(): Deduplicate and merge similar errors.
      - get_suggestion(): Retrieve the suggestion for a given error code.
      - suggest_recovery(): Generate ranked recovery suggestions from a DiagnosticReport.
    """

    ERROR_CODES: ClassVar[dict[int, ErrorCodeTemplate]] = ERROR_CODES

    @classmethod
    def get_suggestion(cls, code: int) -> str:
        """Get the suggestion text for a given error code.

        Args:
            code: Error code number (1-50).

        Returns:
            Suggestion string, or empty string if code not found.
        """
        template = cls.ERROR_CODES.get(code)
        return template.suggestion if template else ""

    @classmethod
    def classify(cls, exception: Exception) -> DiagnosisError:
        """Classify a Python exception into a DiagnosisError.

        Maps common exception types to error codes:
          - FileNotFoundError → code 1 (FILE_MISSING)
          - PermissionError → code 1
          - CIS2HDLParseError → code 12 (STRUCTURE_OVERFLOW)
          - CIS2HDLMatchError → code 28 (MATCH_NOT_FOUND)
          - CIS2HDLConfigError → code 31 (GENERATION_FAILED)
          - ValueError → code 12 (STRUCTURE_OVERFLOW)
          - IndexError → code 13 (STRLST_INDEX_ERROR)
          - KeyError → code 13
          - OSError / IOError → code 3 (FILE_CORRUPTED)
          - Other → code 31 (GENERATION_FAILED)

        Args:
            exception: The Python exception to classify.

        Returns:
            A DiagnosisError with the inferred code.
        """
        exc_type = type(exception).__name__
        exc_msg = str(exception)

        if isinstance(exception, FileNotFoundError):
            code = 1
        elif isinstance(exception, PermissionError):
            code = 1
        elif isinstance(exception, CIS2HDLParseError):
            code = 12
        elif isinstance(exception, CIS2HDLMatchError):
            code = 28
        elif isinstance(exception, CIS2HDLConfigError):
            code = 31
        elif isinstance(exception, ValueError):
            code = 12
        elif isinstance(exception, (IndexError, KeyError)):
            code = 13
        elif isinstance(exception, (OSError, IOError)):
            code = 3
        else:
            code = 31

        template = cls.ERROR_CODES.get(code)
        if template:
            return DiagnosisError(
                code=code,
                severity=template.severity,
                category=template.category,
                message=f"{template.message}: {exc_msg}",
                detail=f"Exception: {exc_type}: {exc_msg}",
                suggestion=template.suggestion,
                can_ignore=template.can_ignore,
            )
        else:
            return DiagnosisError(
                code=31,
                severity=Severity.ERROR,
                category="GEN",
                message=f"未分类异常: {exc_msg}",
                detail=f"Exception: {exc_type}: {exc_msg}",
                suggestion="请联系技术支持",
                can_ignore=False,
            )

    @classmethod
    def aggregate(cls, errors: list[DiagnosisError]) -> list[DiagnosisError]:
        """Deduplicate and merge similar errors.

        Errors with the same code and same message are merged into one,
        with combined detail strings.

        Args:
            errors: Raw list of DiagnosisError entries.

        Returns:
            Deduplicated list.
        """
        if not errors:
            return []

        # Group by (code, message) key
        groups: dict[tuple[int, str], list[DiagnosisError]] = {}
        for err in errors:
            key = (err.code, err.message)
            groups.setdefault(key, []).append(err)

        merged: list[DiagnosisError] = []
        for (code, message), group in groups.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Merge details
                details: list[str] = []
                source_files: set[str] = set()
                for err in group:
                    if err.detail:
                        details.append(err.detail)
                    if err.source_file:
                        source_files.add(err.source_file)

                first = group[0]
                detail_combined = "; ".join(details[:5])
                if len(details) > 5:
                    detail_combined += f" (and {len(details) - 5} more)"

                merged.append(
                    DiagnosisError(
                        code=code,
                        severity=first.severity,
                        category=first.category,
                        message=f"{message} (×{len(group)})",
                        detail=detail_combined,
                        suggestion=first.suggestion,
                        source_file=", ".join(sorted(source_files)[:3]),
                        can_ignore=first.can_ignore,
                    )
                )

        return merged

    @classmethod
    def diagnose(cls, errors: list[DiagnosisError]) -> DiagnosticReport:
        """Aggregate and classify a list of DiagnosisError into a DiagnosticReport.

        Groups errors by severity into errors/warnings/infos, and creates
        a minimal readiness assessment.

        Args:
            errors: Raw list of DiagnosisError entries from validators.

        Returns:
            A DiagnosticReport with categorized errors.
        """
        # First aggregate duplicates
        aggregated = cls.aggregate(errors)

        # Categorize by severity
        fatal_list: list[DiagnosisError] = []
        error_list: list[DiagnosisError] = []
        warning_list: list[DiagnosisError] = []
        info_list: list[DiagnosisError] = []

        for err in aggregated:
            if err.severity == Severity.FATAL:
                fatal_list.append(err)
                error_list.append(err)
            elif err.severity == Severity.ERROR:
                error_list.append(err)
            elif err.severity == Severity.WARNING:
                warning_list.append(err)
            elif err.severity == Severity.INFO:
                info_list.append(err)

        # Build readiness assessment
        readiness = ReadinessReport()
        if fatal_list:
            readiness.can_convert = False
            readiness.can_convert_with_degradation = False
            readiness.recommended_path = "BLOCKED"
            readiness.suggestions = [err.suggestion for err in fatal_list if err.suggestion]
        elif error_list:
            readiness.can_convert = False
            readiness.can_convert_with_degradation = True
            readiness.degradation_detail = f"{len(error_list)} 个可恢复错误"
            readiness.recommended_path = "DEGRADED_CONVERSION"
        else:
            readiness.can_convert = True
            readiness.recommended_path = "FULL_CONVERSION"
            readiness.overall_score = 0.85  # Will be refined by QualityEstimator

        report = DiagnosticReport(
            errors=error_list,
            warnings=warning_list,
            infos=info_list,
            readiness=readiness,
        )

        logger.info(
            "Diagnosis complete: %d errors, %d warnings, %d infos, path=%s",
            len(error_list), len(warning_list), len(info_list),
            readiness.recommended_path,
        )
        return report

    @classmethod
    def suggest_recovery(cls, report: DiagnosticReport) -> list[str]:
        """Generate ranked recovery suggestions from a diagnostic report.

        Analyzes the report's errors and produces actionable suggestions
        ordered by priority (FATAL first, then ERROR, then WARNING).

        Args:
            report: A DiagnosticReport from diagnose().

        Returns:
            List of suggestion strings, ordered by priority.
        """
        suggestions: list[str] = []

        # Gather all suggestions from errors, ordered by severity
        all_errors = (
            sorted(report.errors, key=lambda e: e.severity.value)
            + sorted(report.warnings, key=lambda e: e.severity.value)
            + sorted(report.infos, key=lambda e: e.severity.value)
        )

        seen: set[str] = set()
        for err in all_errors:
            if err.suggestion and err.suggestion not in seen:
                suggestions.append(err.suggestion)
                seen.add(err.suggestion)

        # Add readiness suggestions if present
        for s in report.readiness.suggestions:
            if s not in seen:
                suggestions.append(s)
                seen.add(s)

        return suggestions
