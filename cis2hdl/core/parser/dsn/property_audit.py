"""Property field completeness audit for DSN parser output.

对比参考库 `export_page13.py` 导出的 8 个 CIS 标准字段与当前项目
PlacedInstance 的属性字段，检测缺失字段并生成 DiagnosisError (code 15).

Reference:
    - CIStoHDL_standard/export_page13.py (CIS_FIELDS: 8 fields)
    - CIS2HDL_IMPROVEMENT_DOC.md §1.2.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cis2hdl.core.diagnostics.diagnostic_report import (
    DiagnosisError,
    Severity,
)

logger = logging.getLogger(__name__)

# ── CIS 标准属性字段 ────────────────────────────────────────────────────────
# 来自参考库 export_page13.py 的 8 个标准 CIS 导出字段
# 这些字段是 CIS 数据库的标准属性，通过 COM Properties 集合获取

_CIS_STANDARD_FIELDS: tuple[str, ...] = (
    "RefDes",           # 位号 (如 R1, C2, U3)
    "Value",            # 阻值 / 容值 / 型号
    "Footprint",        # PCB 封装 (PCB Footprint)
    "SNUM",             # 物料料号 (Part Number)
    "PACKAGE_TYPE",     # 封装类型
    "Manufacturer",     # 厂商
    "TYPE_NAME",        # 类型名称
    "DESCRIPTION",      # 描述
)

# DSN prefix_props 中可能使用的字段名别名映射
_CIS_FIELD_ALIASES: dict[str, list[str]] = {
    "RefDes": ["reference", "refdes", "REFERENCE", "Part Reference"],
    "Value": ["value", "VALUE", "Component Value", "Value"],
    "Footprint": ["footprint", "FOOTPRINT", "PCB Footprint", "PCB_FOOTPRINT"],
    "SNUM": ["Part Number", "PART_NUMBER", "SNUM", "snum", "MPN", "Manufacturer PN"],
    "PACKAGE_TYPE": ["PACKAGE_TYPE", "Package Type", "Package_Type", "PKG_TYPE"],
    "Manufacturer": ["Manufacturer", "MANUFACTURER", "MFR", "Vendor"],
    "TYPE_NAME": ["TYPE_NAME", "Type Name", "Type", "Component Type"],
    "DESCRIPTION": ["Description", "DESCRIPTION", "DESC", "Component Description"],
}

# 关键字段 — 缺失时会导致匹配质量问题
_CRITICAL_FIELDS: set[str] = {"RefDes", "Value", "Footprint"}

# 推荐字段 — 缺失时会降低匹配精度
_RECOMMENDED_FIELDS: set[str] = {"SNUM", "PACKAGE_TYPE"}

# 可选字段 — 缺失影响较小
_OPTIONAL_FIELDS: set[str] = {"Manufacturer", "TYPE_NAME", "DESCRIPTION"}


# ── 结果数据类 ──────────────────────────────────────────────────────────────


@dataclass
class PropertyAuditResult:
    """Single component property audit result."""

    refdes: str = ""
    pkg_name: str = ""
    found_fields: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    all_present: bool = True
    critical_missing: list[str] = field(default_factory=list)


# ── 公共 API ────────────────────────────────────────────────────────────────


def audit_property_completeness(
    prefix_props: list,
    reference: str = "",
    pkg_name: str = "",
    part_value: str = "",
    footprint: str = "",
) -> PropertyAuditResult:
    """审计 PlacedInstance 的 CIS 属性字段完整度。

    将 DSN 二进制解析出的 prefix_props (PrefixProperty 列表) 与
    CIS 标准 8 字段对比，检测缺失字段。

    Args:
        prefix_props: PlacedInstance 的 prefix_props 列表
                      (list of PrefixProperty with .name and .value).
        reference: 位号 (如 "R1", "C460").
        pkg_name: 器件封装名.
        part_value: 解析后的器件值 (从 strLst 获取).
        footprint: PCB 封装 (如果可从其他渠道获取).

    Returns:
        PropertyAuditResult with completeness analysis.
    """
    result = PropertyAuditResult(
        refdes=reference,
        pkg_name=pkg_name,
    )

    # 构建 prefix_props 查找字典（大小写不敏感）
    props_dict: dict[str, str] = {}
    for prop in prefix_props:
        name = getattr(prop, "name", "")
        value = getattr(prop, "value", "")
        if name:
            props_dict[name] = value
            # 同时存储标准化键名
            props_dict[name.lower()] = value
            props_dict[name.upper()] = value

    # 额外注入已知值
    if reference and "RefDes" not in props_dict:
        # 为 RefDes 提供 fallback
        pass  # reference is the refdes itself

    if part_value:
        for alias in _CIS_FIELD_ALIASES.get("Value", []):
            if alias not in props_dict and alias.lower() not in props_dict:
                props_dict[alias] = part_value
                break

    if footprint:
        for alias in _CIS_FIELD_ALIASES.get("Footprint", []):
            if alias not in props_dict and alias.lower() not in props_dict:
                props_dict[alias] = footprint
                break

    # 逐个标准字段检查
    for field in _CIS_STANDARD_FIELDS:
        found = _resolve_field(props_dict, field)
        if found:
            result.found_fields[field] = found
        else:
            result.missing_fields.append(field)
            if field in _CRITICAL_FIELDS:
                result.critical_missing.append(field)

    result.all_present = len(result.missing_fields) == 0

    return result


def audit_batch(
    instances: list,
) -> tuple[list[PropertyAuditResult], list[DiagnosisError]]:
    """批量审计多个 PlacedInstance 的属性完整度。

    Args:
        instances: PlacedInstance 对象列表。

    Returns:
        (audit_results, diagnosis_errors) — 审计结果列表和错误诊断列表。
    """
    results: list[PropertyAuditResult] = []
    errors: list[DiagnosisError] = []

    for inst in instances:
        props = getattr(inst, "prefix_props", [])
        refdes = getattr(inst, "reference", "")
        pkg = getattr(inst, "pkg_name", "")

        result = audit_property_completeness(
            prefix_props=props,
            reference=refdes,
            pkg_name=pkg,
        )
        results.append(result)

        # 关键字段缺失 → DiagnosisError (code 15)
        if result.critical_missing:
            err = DiagnosisError(
                code=15,
                name="PROPERTY_FIELD_INCOMPLETE",
                severity=Severity.WARNING,
                category="PARSE",
                message=(
                    f"器件 '{refdes}' 缺少关键 CIS 属性字段: "
                    f"{', '.join(result.critical_missing)}"
                ),
                suggestion=(
                    f"请确认 DSN 文件中的 CIS 属性数据库包含完整字段。"
                    f"缺失: {', '.join(result.critical_missing)}"
                ),
                can_ignore=True,
                phase="I",
            )
            errors.append(err)

    if results:
        complete_count = sum(1 for r in results if r.all_present)
        logger.info(
            "Property audit: %d/%d instances have complete CIS properties",
            complete_count,
            len(results),
        )

    return results, errors


# ── 内部辅助 ────────────────────────────────────────────────────────────────


def _resolve_field(props_dict: dict[str, str], field_name: str) -> str:
    """在属性字典中查找 CIS 字段，支持别名。

    按优先级：精确名 → 别名列表 → 大小写变体。

    Args:
        props_dict: 属性名到值的映射（已预标准化）。
        field_name: CIS 标准字段名。

    Returns:
        找到的属性值，或空字符串。
    """
    # 精确匹配
    if field_name in props_dict:
        return props_dict[field_name]

    # 别名匹配
    for alias in _CIS_FIELD_ALIASES.get(field_name, []):
        if alias in props_dict:
            return props_dict[alias]
        alias_lower = alias.lower()
        if alias_lower in props_dict:
            return props_dict[alias_lower]
        alias_upper = alias.upper()
        if alias_upper in props_dict and alias_upper != alias:
            return props_dict[alias_upper]

    return ""
