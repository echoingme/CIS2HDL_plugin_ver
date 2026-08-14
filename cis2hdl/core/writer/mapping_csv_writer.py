"""综合映射 CSV 报告生成器。

生成包含转换概览、逐器件映射、异常报告、输出文件清单的单一 CSV 文件。
参考: CIStoHDL_standard/CIS_to_HDL_Mapping.csv + Page13_DeviceList.csv +
      Page13_AnomalyList.txt

v2.0: 新增双边对比列、Phase 列、Top-3 候选列、匹配统计摘要。
"""

from __future__ import annotations

import csv
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cis2hdl.core.ir.component import ComponentDef
    from cis2hdl.core.ir.design import DesignIR
    from cis2hdl.core.ir.match import MatchResult, MatchStrategy
    from cis2hdl.core.engine.conversion_engine import ConversionReport

logger = logging.getLogger(__name__)

# ── Phase XII R2: power symbol cells ─────────────────────────────────
# EDIF power symbols (GND/DGND/VCC_CIRCLE/…) are preserved across the
# catalog rebuild but are NOT part of the ComponentCatalog.  They are
# matched deterministically by ConversionEngine._append_power_symbol_matches.
# A power symbol naturally has no value and no pin connections — so the
# INFO_LOSS flags below must not be reported for them.
_POWER_CELLS: frozenset[str] = frozenset({
    "gnd", "dgnd", "vcc_circle", "gnd_power", "gnd_earth",
    "gnd_signal", "vcc_bar", "vcc_arrow", "gnd_chassis",
})

# ── CSV 段落标题常量 ────────────────────────────────────────────────────
_SECTION_OVERVIEW = "=== CIS→HDL 转换报告 ==="
_SECTION_STATS = "--- 转换统计 ---"
_SECTION_MAPPING = "--- 器件映射 ---"
_SECTION_ANOMALY = "--- 异常报告 ---"
_SECTION_FILES = "--- HDL 输出文件 ---"
_SECTION_MATCH_STATS = "--- 匹配策略统计 ---"


class MappingCSVWriter:
    """生成 CIS→HDL 综合映射 CSV 报告。

    单文件多段式报告：
        1. 转换概览（元数据 + 统计）
        2. 匹配策略统计摘要
        3. 逐器件映射表（含 v2.0 双边对比 + Phase + Top-3）
        4. 异常报告
        5. 输出文件清单
    """

    @staticmethod
    def write(
        output_path: Path,
        design_ir: "DesignIR",
        match_results: list["MatchResult"],
        conversion_report: "ConversionReport",
        output_dir: Path,
        dsn_path: Path,
    ) -> Path:
        """写入完整映射 CSV 报告。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            _write_overview(writer, design_ir, conversion_report,
                            output_dir, dsn_path, match_results)
            _write_match_stats(writer, match_results)
            _write_device_mapping(writer, design_ir, match_results)
            _write_anomaly_report(writer, design_ir, match_results)
            _write_file_inventory(writer, conversion_report)

        logger.info("Mapping CSV written: %s (%d bytes)",
                     output_path, output_path.stat().st_size)
        return output_path


# ═══════════════════════════════════════════════════════════════════════════
#  Section 1: 转换概览
# ═══════════════════════════════════════════════════════════════════════════


def _write_overview(
    writer: Any,
    design_ir: "DesignIR",
    report: "ConversionReport",
    output_dir: Path,
    dsn_path: Path,
    match_results: list["MatchResult"],
) -> None:
    """写入转换概览段落。"""
    writer.writerow([_SECTION_OVERVIEW])
    writer.writerow(["项目名称", design_ir.project_name or dsn_path.stem])
    writer.writerow(["转换时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["CIS 文件名", dsn_path.name])
    writer.writerow(["HDL 输出目录", str(output_dir)])
    writer.writerow([])

    total_inst = sum(len(p.instances) for p in design_ir.pages)
    total_nets = sum(len(p.nets) for p in design_ir.pages)

    schematic_pages = sum(1 for p in design_ir.pages if p.instances)
    info_pages = sum(
        1 for p in design_ir.pages
        if (hasattr(p, "graphic_elements") and p.graphic_elements
            and not p.instances and not p.page_id.startswith("xref."))
    )
    total_real_pages = schematic_pages + info_pages
    graphic_count = sum(
        len(p.graphic_elements) for p in design_ir.pages
        if hasattr(p, "graphic_elements") and p.graphic_elements
    )

    csa_count = 0
    for _sch_dir in output_dir.glob("**/sch_1"):
        csa_count = max(csa_count, len(list(_sch_dir.glob("page*.csa"))))

    writer.writerow([_SECTION_STATS])
    stats = [
        ("CIS 原始页面数(含子流)", len(design_ir.pages)),
        ("CIS 实际页面数", total_real_pages),
        ("  其中原理图页", schematic_pages),
        ("  其中信息页", info_pages),
        ("CIS 原始元件数", total_inst),
        ("CIS 原始网络数", total_nets),
        ("HDL 输出 CSA 文件数", csa_count),
        ("HDL 输出总文件数", len(report.output_files)),
        ("文字/形状元素", graphic_count),
    ]
    for label, value in stats:
        writer.writerow([label, str(value)])

    if match_results:
        matched = sum(
            1 for m in match_results
            if m.confidence is not None and m.confidence >= 0.45
        )
        failed = len(match_results) - matched
        fuzzy = sum(
            1 for m in match_results
            if m.confidence is not None and 0.25 <= m.confidence < 0.45
        )
        writer.writerow(["匹配成功器件", str(matched)])
        writer.writerow(["匹配失败器件", str(failed)])
        writer.writerow(["模糊匹配器件", str(fuzzy)])

    writer.writerow([])


# ═══════════════════════════════════════════════════════════════════════════
#  Section 1.5: 匹配策略统计摘要 (v2.0)
# ═══════════════════════════════════════════════════════════════════════════


def _write_match_stats(
    writer: Any,
    match_results: list["MatchResult"],
) -> None:
    """写入匹配策略分布统计摘要。

    v2.0: 按 MatchStrategy 计数，提供匹配质量概览。
    """
    writer.writerow([_SECTION_MATCH_STATS])

    strategy_counts: Counter[str] = Counter()
    for mr in match_results:
        strategy_name: str = str(getattr(mr, "strategy", "UNKNOWN"))
        strategy_counts[strategy_name] += 1

    writer.writerow(["策略", "数量", "占比"])
    total: int = len(match_results) or 1
    for strategy_name, count in strategy_counts.most_common():
        pct: str = f"{count / total * 100:.1f}%"
        writer.writerow([strategy_name, str(count), pct])

    # v2.0: Phase 1 type distribution
    phase1_types: Counter[str] = Counter()
    for mr in match_results:
        pt: str = getattr(mr, "phase1_type", "") or ""
        if pt:
            phase1_types[pt] += 1
    if phase1_types:
        writer.writerow([])
        writer.writerow(["Phase1 类型", "数量"])
        for type_name, count in phase1_types.most_common():
            writer.writerow([type_name, str(count)])

    # NEEDS_REVIEW count
    needs_review: int = sum(
        1 for mr in match_results
        if getattr(mr, "strategy", "") == "NEEDS_REVIEW"
    )
    if needs_review > 0:
        writer.writerow([])
        writer.writerow(["需人工审核", str(needs_review)])

    writer.writerow([])


# ═══════════════════════════════════════════════════════════════════════════
#  Section 2: 逐器件映射表 (v2.0 enhanced)
# ═══════════════════════════════════════════════════════════════════════════


def _write_device_mapping(
    writer: Any,
    design_ir: "DesignIR",
    match_results: list["MatchResult"],
) -> None:
    """写入逐器件映射表（v2.0 增强版）。

    包含:
        - 现有列 (保留)
        - 双边对比列: cis_footprint, cis_jedec, hdl_value, hdl_footprint,
                      hdl_category, hdl_pin_count
        - Phase 列: phase1_type, phase1_prior_conf, phase2_strategy_detail,
                     match_dims
        - Top-3 候选列: rank1~3 (type, cell, primitive, final_conf, match_dims)
    """
    writer.writerow([_SECTION_MAPPING])
    headers = [
        # === CIS 端信息 ===
        "refdes", "cis_value", "cis_footprint", "cis_library_id",
        "cis_jedec", "loc_x", "loc_y", "page_name",
        # === HDL 端信息 ===
        "hdl_part", "hdl_primitive", "hdl_value", "hdl_footprint",
        "hdl_jedec", "hdl_package_type", "hdl_category", "hdl_pin_count",
        # === 匹配信息 ===
        "match_status", "match_level", "final_conf",
        "match_strategy", "phase1_type", "phase1_prior_conf",
        "phase2_strategy_detail", "error_note",
        # === Top-3 候选 ===
        "rank1_type", "rank1_cell", "rank1_primitive", "rank1_final_conf", "rank1_match_dims",
        "rank2_type", "rank2_cell", "rank2_primitive", "rank2_final_conf", "rank2_match_dims",
        "rank3_type", "rank3_cell", "rank3_primitive", "rank3_final_conf", "rank3_match_dims",
        # Phase XVIII R4: CrossRef CSV 四属性（CSA 属性块注入数据源回显）
        "xref_jedec_type", "xref_package_type", "xref_sn_num", "xref_description",
    ]
    writer.writerow(headers)

    # 构建 library_id → MatchResult 映射
    match_map: dict[str, "MatchResult"] = {}
    for mr in match_results:
        src_lib = getattr(mr, "source_library_id", "")
        if src_lib:
            match_map[src_lib] = mr

    for page in design_ir.pages:
        page_name = page.page_name or page.page_id
        for inst in page.instances:
            lib_id = inst.library_id or ""
            mr = match_map.get(lib_id)

            # ── 确定映射状态 ──────────────────────────────────────
            if mr is not None and mr.confidence is not None:
                if mr.confidence >= 0.70:
                    status = "matched"
                    level = "exact"
                elif mr.confidence >= 0.50:
                    status = "matched"
                    level = "fuzzy"
                elif mr.confidence >= 0.45:
                    status = "matched"
                    level = "feature"
                elif mr.confidence >= 0.3:
                    status = "fuzzy"
                    level = str(getattr(mr, "strategy", ""))
                else:
                    status = "failed"
                    level = ""
            elif mr is not None:
                status = "failed"
                level = ""
            else:
                status = "failed"
                level = "no_match"
                mr = None

            # ── HDL 目标信息 ───────────────────────────────────────
            if mr is not None:
                target_lib = getattr(mr, "target_library_id", "") or "UNMATCHED"
                target_part = _extract_part_name(target_lib)
            else:
                target_lib = "UNMATCHED"
                target_part = "UNMATCHED"

            # ── CIS 属性 ────────────────────────────────────────────
            cis_value = inst.properties.get("Value", inst.properties.get("VALUE", ""))
            if not cis_value:
                cis_value = getattr(inst, "value_override", "") or ""
            if not cis_value:
                catalog = design_ir.metadata.get("component_catalog")
                if catalog:
                    cat_entry = catalog.get_by_refdes(inst.refdes)
                    if cat_entry and cat_entry.value:
                        cis_value = cat_entry.value

            cis_footprint = inst.properties.get(
                "PCB Footprint",
                inst.properties.get("FOOTPRINT",
                                     inst.properties.get("Footprint", "")),
            )

            # ── v2.0: 双边对比数据 ──────────────────────────────────
            extra = getattr(inst, "extra_data", {}) or {}
            # CIS side
            cis_jedec = extra.get("pst_jedec_type", "")

            # HDL side (from match result extra_data populated by _enrich_result)
            hdl_value = ""
            hdl_footprint = ""
            hdl_jedec = ""
            hdl_package_type = ""
            hdl_category = ""
            hdl_pin_count = ""
            if mr is not None and mr.target_library_id:
                hdl_extra = getattr(mr, "extra_data", {}) or {}
                hdl_value = hdl_extra.get("hdl_value", "")
                hdl_footprint = hdl_extra.get("hdl_footprint", "")
                hdl_jedec = hdl_extra.get("hdl_jedec", "")
                hdl_package_type = hdl_extra.get("hdl_package_type", "")
                hdl_category = hdl_extra.get("hdl_category", "")
                hdl_pin_count_str = hdl_extra.get("hdl_pin_count", "")
                hdl_pin_count = str(hdl_pin_count_str) if hdl_pin_count_str else ""

            # ── v2.0: Phase 列 ──────────────────────────────────────
            phase1_type = getattr(mr, "phase1_type", "") if mr else ""
            phase1_prior = f"{getattr(mr, 'phase1_prior_conf', 0.0):.2f}" if mr else ""
            phase2_detail = getattr(mr, "phase2_strategy_detail", "") if mr else ""

            # Use phase1_type as hdl_category when available (more meaningful than "DISCRETE")
            if phase1_type and not hdl_category:
                hdl_category = phase1_type
            match_strategy = str(getattr(mr, "strategy", "")) if mr else ""

            # ── 错误备注 ────────────────────────────────────────────
            error_note = ""
            if mr is not None and hasattr(mr, "warnings") and mr.warnings:
                error_note = "; ".join(str(w) for w in mr.warnings[:3])

            final_conf_str = ""
            if mr is not None and mr.confidence is not None:
                final_conf_str = str(round(mr.confidence, 4))

            # ── 检测关键信息缺失 ────────────────────────────────────
            # Phase XII R2: power symbols (GND/DGND/VCC_CIRCLE/…) carry
            # no value and no pin connections by design — do not flag
            # them as INFO_LOSS.
            info_loss = []
            if not cis_value or cis_value in ("", "<null>", "?"):
                info_loss.append("Missing_Value")
            catalog_available = bool(design_ir.metadata.get("component_catalog"))
            if not catalog_available:
                if not cis_footprint or cis_footprint in ("", "<null>", "?"):
                    info_loss.append("Missing_Footprint")
            if inst.loc_x == 0 and inst.loc_y == 0:
                info_loss.append("Missing_Coordinates")
            if not inst.pin_connections:
                info_loss.append("No_Pin_Connections")
            if lib_id.lower() in _POWER_CELLS:
                info_loss = []
            if info_loss:
                if error_note:
                    error_note += "; "
                error_note += "INFO_LOSS: " + ", ".join(info_loss)
                from ..writer.error_logger import ConversionLogger
                ConversionLogger.log_warning(
                    "INFO_LOSS",
                    f"{inst.refdes}: {', '.join(info_loss)}",
                    detail=f"page={page_name}, lib={lib_id}",
                )

            # ── v2.0: Top-3 候选列 ──────────────────────────────────
            top3: list[dict] = getattr(mr, "top3_candidates", []) if mr else []
            top3_cols: list[str] = []
            for rank in range(3):
                if rank < len(top3):
                    entry = top3[rank]
                    top3_cols.extend([
                        str(entry.get("type", "")),
                        str(entry.get("library_id", entry.get("part_name", ""))),
                        str(entry.get("primitive", "")),
                        str(entry.get("final_conf", "")),
                        str(entry.get("match_dims", "")),
                    ])
                else:
                    top3_cols.extend(["", "", "", "", ""])

            row = [
                # === CIS 端 ===
                inst.refdes,
                cis_value,
                cis_footprint,
                lib_id,
                cis_jedec,
                str(inst.loc_x),
                str(inst.loc_y),
                page_name,
                # === HDL 端 ===
                target_part,
                target_lib,
                hdl_value,
                hdl_footprint,
                hdl_jedec,
                hdl_package_type,
                hdl_category,
                hdl_pin_count,
                # === 匹配信息 ===
                status,
                level,
                final_conf_str,
                match_strategy,
                phase1_type,
                phase1_prior,
                phase2_detail,
                error_note,
                # === Top-3 ===
                *top3_cols,
                # Phase XVIII R4: CrossRef 四属性（组件目录数据源）
                *_xref_attrs(design_ir, inst),
            ]
            writer.writerow(row)

    writer.writerow([])


def _xref_attrs(design_ir: "DesignIR", inst) -> list[str]:
    """CrossRef CSV 四属性回显（DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM）。

    Phase XVIII R4：CSA 属性块注入的同源数据（ComponentCatalog），
    便于对比验证属性注入正确性。

    Args:
        design_ir: DesignIR（metadata 含 component_catalog）。
        inst: 实例对象（refdes 查找键）。

    Returns:
        ``[jedec_type, package_type, sn_num, description]`` 四元列表。
    """
    catalog = design_ir.metadata.get("component_catalog")
    if catalog is None:
        return ["", "", "", ""]
    entry = catalog.get_by_refdes(getattr(inst, "refdes", ""))
    if entry is None:
        return ["", "", "", ""]
    return [
        str(entry.jedec_type or ""),
        str(entry.package_type or ""),
        str(entry.sn_num or ""),
        str(entry.description or ""),
    ]


# ═══════════════════════════════════════════════════════════════════════════
#  Section 3: 异常报告
# ═══════════════════════════════════════════════════════════════════════════


def _write_anomaly_report(
    writer: Any,
    design_ir: "DesignIR",
    match_results: list["MatchResult"],
) -> None:
    """写入异常报告：列出匹配失败或模糊匹配的器件。"""
    writer.writerow([_SECTION_ANOMALY])
    writer.writerow(["refdes", "issue", "phase1_type", "strategy"])

    lib_instances: dict[str, list[str]] = {}
    for page in design_ir.pages:
        for inst in page.instances:
            lib_id = inst.library_id or ""
            lib_instances.setdefault(lib_id, []).append(inst.refdes)

    for mr in match_results:
        if mr.confidence is not None and mr.confidence >= 0.95:
            continue

        src_lib = getattr(mr, "source_library_id", "")
        refdes_list = lib_instances.get(src_lib, ["?"])

        issue = _build_anomaly_issue(mr)
        phase1 = getattr(mr, "phase1_type", "")
        strategy = str(getattr(mr, "strategy", ""))

        for refdes in refdes_list:
            writer.writerow([refdes, issue, phase1, strategy])

    writer.writerow([])


def _build_anomaly_issue(mr: "MatchResult") -> str:
    """根据 MatchResult 构建异常描述字符串。"""
    parts: list[str] = []

    if mr.confidence is None or mr.confidence <= 0.0:
        parts.append("No_SNUM")
    elif mr.confidence < 0.25:
        parts.append(f"Match_failed_confidence={mr.confidence:.2f}")
    elif mr.confidence < 0.45:
        strategy = getattr(mr, "strategy", "")
        parts.append(f"Fuzzy_match_{strategy}")
    elif mr.confidence < 0.70:
        parts.append(f"Partial_match_conf={mr.confidence:.2f}")

    if hasattr(mr, "warnings") and mr.warnings:
        for w in mr.warnings[:2]:
            short = str(w)[:60]
            parts.append(short)

    return "; ".join(parts) if parts else "Unknown_anomaly"


# ═══════════════════════════════════════════════════════════════════════════
#  Section 4: HDL 输出文件清单
# ═══════════════════════════════════════════════════════════════════════════


def _write_file_inventory(
    writer: Any,
    report: "ConversionReport",
) -> None:
    """写入 HDL 输出文件清单。"""
    writer.writerow([_SECTION_FILES])
    writer.writerow(["文件路径", "文件大小(字节)"])

    for fp in sorted(report.output_files):
        p = Path(fp)
        try:
            size = p.stat().st_size if p.exists() else 0
        except OSError:
            size = 0
        writer.writerow([fp, str(size)])

    writer.writerow([])


# ═══════════════════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════════════════


def _extract_part_name(library_id: str) -> str:
    """从 HDL library_id 中提取人类可读的器件名。"""
    if not library_id:
        return "UNMATCHED"
    parts = library_id.replace("\\", "/").split("/")
    parts = [p for p in parts if p]
    if len(parts) >= 2:
        return parts[-2]
    return parts[-1] if parts else library_id


# ═══════════════════════════════════════════════════════════════════════════
#  v1.0: Top-3 Candidate Database Export (retained)
# ═══════════════════════════════════════════════════════════════════════════


def write_top3_file(
    output_path: Path,
    sources: list["ComponentDef"],
    match_results: list["MatchResult"],
) -> Path:
    """Generate top-3 candidate database for GUI selection.

    v2.0: Now reads top3_candidates directly from MatchResult.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        project_name: str = output_path.stem.replace("_top3", "")
        f.write(f"# {project_name} — Top-3 HDL Candidates per CIS Component\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# Format: refdes | rank | type | hdl_cell | hdl_primitive | final_conf | match_dims\n")
        f.write("# Selected match marked with '*'\n")
        f.write("-" * 70 + "\n")

        for mr in match_results:
            src_lib: str = getattr(mr, "source_library_id", "")
            top3: list[dict] = getattr(mr, "top3_candidates", [])
            selected_lib: str = getattr(mr, "target_library_id", "")

            if not top3:
                # Fallback to old extra_data format
                extra = getattr(mr, "extra_data", {}) or {}
                top3 = extra.get("top3_candidates", [])

            if not top3:
                continue

            for rank, entry in enumerate(top3, 1):
                lib_id: str = entry.get("library_id", "")
                part_name: str = entry.get("part_name", "")
                primitive: str = entry.get("primitive", "")
                final_conf: str = str(entry.get("final_conf", ""))
                match_dims: str = entry.get("match_dims", "")
                type_name: str = entry.get("type", "")

                is_selected: str = "*" if lib_id == selected_lib else " "
                f.write(
                    f"{src_lib} | {rank}{is_selected}| {type_name} | "
                    f"{part_name or lib_id} | {primitive} | "
                    f"{final_conf} | {match_dims}\n"
                )

            f.write("-" * 70 + "\n")

    logger.info("Top-3 file written: %s (%d bytes)",
                 output_path, output_path.stat().st_size)
    return output_path
