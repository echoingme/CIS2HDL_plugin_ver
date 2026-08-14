"""StructuredReportGenerator — JSON / HTML report output.

Generates structured conversion reports from a ConversionReport in both
JSON and HTML formats. The HTML output uses inline CSS in warm-beige
Anthropic design language style.

v2.0: Enhanced match results table with match dimension column (✅/⚠️/❌),
      Top-3 candidate collapsible sections, NEEDS_REVIEW red highlighting,
      and strategy distribution summary chart.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StructuredReportGenerator:
    """Generates JSON and HTML structured reports from ConversionReport."""

    # ── JSON output ──────────────────────────────────────────────────

    def generate_json(self, report: Any) -> str:
        """Generate a JSON-formatted conversion report."""
        data = self._report_to_dict(report)
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    # ── HTML output ──────────────────────────────────────────────────

    def generate_html(self, report: Any) -> str:
        """Generate an HTML-formatted conversion report with Anthropic styling."""
        data = self._report_to_dict(report)
        body_parts: list[str] = []

        # ── Header ─────────────────────────────────────────────────
        project_name = data.get("project_name", "Untitled")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        success = data.get("success", False)
        status_color = "#6B8F47" if success else "#C0453A"
        status_text = "✅ 转换成功" if success else "❌ 转换失败"

        body_parts.append(f"""
        <div class="header">
            <h1>{self._escape_html(project_name)} — Conversion Report</h1>
            <p class="timestamp">{timestamp}</p>
            <p class="status" style="color:{status_color}">{status_text}</p>
        </div>
        """)

        # ── Summary stats ──────────────────────────────────────────
        quality = data.get("quality", {})
        pages = quality.get("total_pages", data.get("pages", 0))
        instances = data.get("instances", 0)
        nets = data.get("nets", 0)
        output_files = data.get("output_files", [])
        output_count = len(output_files)
        match_results = data.get("match_results", [])

        # v2c (A.2): field semantics computed here (ConversionReport unchanged)
        hdl_pages = data.get("hdl_pages", 0)
        matched_instances = data.get("matched_instances", 0)
        matched_nets = data.get("matched_nets", nets)

        error_count = 0
        warning_count = 0
        try:
            from ..writer.error_logger import ConversionLogger
            for evt in ConversionLogger._events:
                lvl = evt.get("level", "")
                if lvl in ("ERROR", "FATAL"):
                    error_count += 1
                elif lvl == "WARNING":
                    warning_count += 1
        except Exception:
            error_count = len(data.get("errors", []))
            warning_count = len(data.get("warnings", []))

        # v2c (A.2): three groups — CIS → HDL → Output; value above label
        def _card(value_html: str, label: str, extra: str = "") -> str:
            return f"""
            <div class="card"{extra}>
                <div class="card-value">{value_html}</div>
                <div class="card-label">{label}</div>
            </div>"""

        body_parts.append(f"""
        <div class="summary-cards">
            <div class="card-group">
                <div class="card-group-title">
                    <span class="card-accent" style="background:#6B8F47"></span>CIS 解析
                </div>
                {_card(pages, "Pages")}
                {_card(instances, "Instances")}
                {_card(nets, "Nets")}
            </div>
            <div class="card-group">
                <div class="card-group-title">
                    <span class="card-accent" style="background:#5A89B8"></span>HDL 输出
                </div>
                {_card(hdl_pages, "Pages")}
                {_card(matched_instances, "Matched Instances")}
                {_card(matched_nets, "Matched Nets",
                       ' title="本流水线网络为 1:1 复制"')}
            </div>
            <div class="card-group">
                <div class="card-group-title">
                    <span class="card-accent" style="background:#C9943A"></span>输出
                </div>
                {_card(output_count, "Output Files")}
                {_card(f'<span style="color:#C0453A">{error_count}</span>', "Errors")}
                {_card(f'<span style="color:#C9943A">{warning_count}</span>', "Warnings")}
            </div>
        </div>
        """)

        # ── Quality scores ─────────────────────────────────────────
        quality = data.get("quality")
        if quality:
            body_parts.append(self._render_quality_section(quality))

        # ── v2.0: Strategy distribution chart ──────────────────────
        match_results = data.get("match_results")
        if match_results:
            body_parts.append(self._render_strategy_chart(match_results))

        # ── Phase XII R8: Output file types + fallback components ──
        # Both are compact reference tables placed ABOVE Match Results.
        body_parts.append(self._render_output_types_section())
        if data.get("fallback_table"):
            # Only show fallback rows for types actually used by this
            # design's matching (keeps the table compact and relevant).
            used_types: set[str] = {
                str(m.get("phase1_type", "")).lower()
                for m in (data.get("match_results") or [])
                if m.get("phase1_type")
            }
            body_parts.append(
                self._render_fallback_section(data["fallback_table"], used_types)
            )

        # ── Match results ──────────────────────────────────────────
        if match_results:
            body_parts.append(self._render_match_section(match_results))

        # ── Errors & Warnings ──────────────────────────────────────
        all_errors = data.get("errors", [])
        all_warnings = data.get("warnings", [])
        if all_errors or all_warnings:
            body_parts.append(self._render_issues_section(all_errors, all_warnings))

        # ── Output files ───────────────────────────────────────────
        output_files = data.get("output_files", [])
        if output_files:
            body_parts.append(self._render_files_section(output_files))

        # ── Assemble full HTML ─────────────────────────────────────
        html = self._render_full_html(
            title=f"{project_name} — Conversion Report",
            body="\n".join(body_parts),
        )
        return html

    def generate_html_file(
        self,
        report: Any,
        output_path: Path,
    ) -> Optional[Path]:
        """Generate an HTML report and write it to a file."""
        try:
            if output_path.is_dir():
                project_name = getattr(report, "project_name", "conversion")
                output_path = output_path / f"{project_name}_report.html"

            html = self.generate_html(report)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            logger.info("HTML report written to %s", output_path)
            return output_path
        except OSError as exc:
            logger.error("Failed to write HTML report to %s: %s", output_path, exc)
            return None

    # ── Section renderers ────────────────────────────────────────────

    def _render_quality_section(self, quality: dict[str, Any]) -> str:
        """Render the quality assessment section."""
        overall = quality.get("overall_score", 0)
        overall_pct = round(overall * 100)
        overall_color = self._score_color(overall)

        bars_html = ""
        metric_defs = [
            ("logic_score", "Logical Integrity",
             "Completeness of component identity — refdes, value, and coordinates."),
            ("coordinate_score", "Coordinate Availability",
             "Percentage of components with known (x, y) placement coordinates."),
            ("match_score", "Match Coverage",
             "Percentage of components successfully matched to an HDL library part."),
        ]
        for key, label, desc in metric_defs:
            score = quality.get(key, 0)
            pct = int(score * 100)
            color = self._score_color(score)
            bars_html += f"""
            <div class="quality-bar">
                <span class="quality-label">{label}</span>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%;background:{color}"></div>
                </div>
                <span class="quality-pct">{pct}%</span>
            </div>
            <p class="quality-desc">{self._escape_html(desc)}</p>
            """

        matched = quality.get("matched_count", 0)
        total = quality.get("total_count", 0)

        return f"""
        <div class="section">
            <h2>Quality Assessment</h2>
            <div class="overall-score" style="color:{overall_color}">{overall_pct}%</div>
            <p class="overall-summary">转换质量: {overall_pct}%</p>
            <p class="match-summary">{matched}/{total} components matched</p>
            {bars_html}
        </div>
        """

    # ── v2.0: Strategy distribution chart ────────────────────────────

    def _render_strategy_chart(
        self, match_results: list[dict[str, Any]]
    ) -> str:
        """Render strategy distribution as horizontal bar chart."""
        strategy_counts: Counter[str] = Counter()
        phase1_counts: Counter[str] = Counter()
        needs_review_count: int = 0

        for m in match_results:
            strategy = m.get("strategy", "UNKNOWN")
            strategy_counts[strategy] += 1
            phase1_type = m.get("phase1_type", "")
            if phase1_type:
                phase1_counts[phase1_type] += 1
            if strategy == "NEEDS_REVIEW":
                needs_review_count += 1

        total = len(match_results) or 1

        bars_html = ""
        for strategy, count in strategy_counts.most_common():
            pct = count / total * 100
            color = "#6B8F47" if "PASSIVE" in strategy or "EXACT" in strategy else (
                "#C0453A" if strategy in ("NEEDS_REVIEW", "MANUAL") else "#5A89B8"
            )
            bars_html += f"""
            <div class="quality-bar">
                <span class="quality-label">{self._escape_html(strategy)}</span>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%;background:{color}"></div>
                </div>
                <span class="quality-pct">{count} ({pct:.0f}%)</span>
            </div>
            """

        review_warning = ""
        if needs_review_count > 0:
            review_warning = (
                f'<p style="color:#C0453A;margin-top:8px;">'
                f'⚠️ {needs_review_count} 个元件需要人工审核</p>'
            )

        return f"""
        <div class="section">
            <h2>Match Strategy Distribution</h2>
            {bars_html}
            {review_warning}
        </div>
        """

    # ── Phase XII R8: Output file types + fallback components ───────

    def _render_output_types_section(self) -> str:
        """Render a compact reference table of generated output file types.

        Placed ABOVE Match Results so the user can understand what each
        output artifact is without leaving the report.
        """
        # (extension / path pattern, function, structure note)
        types: list[tuple[str, str, str]] = [
            (".cpm", "Cadence 工程管理文件", "工程结构、页面列表与库引用"),
            ("cds.lib", "逻辑库定义", "注册 worklib 及 HDL 库路径"),
            (".con", "连通性约束模型", "S-expr 网络/引脚连接描述"),
            (".xcon", "跨页网络范围声明", "XML 格式，声明网络所属页面"),
            ("page.map", "页码映射", "逻辑页 ↔ 物理 pageN 映射"),
            ("pageN.csa", "DEHDL 原理图页面脚本", "WIRE / LASTPIN / FORCEADD 指令"),
            ("pageN.csv", "页面器件清单", "该页元件/网络明细"),
            ("pageN.cpc", "页面属性文件", "元件与网络属性键值"),
            (".dcf", "设计约束文件", "S-expr 约束（生成时写入）"),
            ("module_order.dat", "模块顺序", "页面对应 HDL 模块次序"),
            (".scr", "交互式脚本", "place_parts_pageN 回放脚本"),
            ("hdldirect.dat", "HDL 直连配置", "Design/Version 元信息"),
            ("hdl_lib/", "拷贝的 HDL 元件库", "chips.prt / symbol.css / part.ptf"),
            ("temp/", "临时目录", "转换过程中间文件"),
        ]

        rows_html = ""
        for ext, func, struct in types:
            rows_html += f"""
            <tr>
                <td style="font-family:'JetBrains Mono','Cascadia Code',monospace;font-size:11px;color:#5A89B8;font-weight:600;white-space:nowrap;">{self._escape_html(ext)}</td>
                <td>{self._escape_html(func)}</td>
                <td style="color:#6B6860;font-size:11px;">{self._escape_html(struct)}</td>
            </tr>"""

        return f"""
        <div class="section">
            <h2>Output File Types</h2>
            <p style="font-size:11px;color:#9D9A91;margin:-8px 0 12px;">
                本次转换输出的文件类型一览（实际生成数量见下方 Generated Files）
            </p>
            <div class="table-scroll">
            <table class="fallback-table" style="min-width:640px;">
                <thead>
                    <tr>
                        <th style="width:150px;">Extension</th>
                        <th>功能</th>
                        <th>结构说明</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            </div>
        </div>
        """

    def _render_fallback_section(
        self,
        fallback_table: dict[str, Any],
        used_types: set[str] | None = None,
    ) -> str:
        """Render the default fallback component table.

        Documents, per component type, the default value / footprint that
        PassiveMatcher L5 (prefix-only fallback, default package 0603)
        selects when a component's exact value is not present in the HDL
        library.  When ``used_types`` is non-empty, only rows whose type
        name appears in the design's phase1 types are rendered.
        """
        rows_html = ""
        for type_name in sorted(fallback_table):
            if used_types and type_name.lower() not in {t.lower() for t in used_types}:
                continue
            row = fallback_table[type_name]
            rows_html += f"""
            <tr>
                <td style="font-weight:600;white-space:nowrap;">{self._escape_html(str(type_name))}</td>
                <td>{self._escape_html(str(row.get("value", "")))}</td>
                <td>{self._escape_html(str(row.get("footprint", "")))}</td>
                <td style="font-size:11px">{self._escape_html(str(row.get("jedec", "")))}</td>
                <td style="font-size:11px">{self._escape_html(str(row.get("package_type", "")))}</td>
            </tr>"""

        return f"""
        <div class="section">
            <h2>Default Fallback Components</h2>
            <p style="font-size:11px;color:#9D9A91;margin:-8px 0 12px;">
                当元件的标称值在 HDL 库中不存在时，PassiveMatcher 第 5 级
                （前缀回退，默认封装 0603）使用该类型的第一条库记录。
            </p>
            <div class="table-scroll">
            <table class="fallback-table" style="min-width:640px;">
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>默认 Value</th>
                        <th>默认 Footprint</th>
                        <th>JEDEC_TYPE</th>
                        <th>PACKAGE_TYPE</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            </div>
        </div>
        """

    # ── v2.0: Enhanced match results table ───────────────────────────

    def _render_match_section(self, match_results: list[dict[str, Any]]) -> str:
        """Render the match results table with v2.0 enhancements.

        Includes:
        - Match dimension column (✅/⚠️/❌)
        - Top-3 candidate collapsible rows (v2c: enriched with value/
          footprint/jedec/package_type/pin_count)
        - NEEDS_REVIEW red row highlighting
        - v2c (A.1): Type column shows phase1_type (not hdl_category)
        - v2c (A.3): Top-1 main row dark, Top-1 header/Rank rows light
        - v2c (A.5): three JEDEC columns — CIS JEDEC / HDL JEDEC /
          HDL PACKAGE_TYPE
        """
        rows_html = ""
        for m in match_results:
            confidence = m.get("confidence", 0)
            source = self._escape_html(str(m.get("source_library_id", "?")))
            target = self._escape_html(str(m.get("target_library_id", "—")))
            strategy = self._escape_html(str(m.get("strategy", "?")))
            cis_val = self._escape_html(str(m.get("cis_value", "")))
            # v2.0: Show HDL matched value instead of CIS PST value
            hdl_val = self._escape_html(str(m.get("hdl_value", "")))
            hdl_pkg = self._escape_html(str(m.get("hdl_package_type", "") or m.get("hdl_footprint", "")))
            hdl_cat = self._escape_html(str(m.get("phase1_type", "") or m.get("hdl_category", "")))
            hdl_jd = self._escape_html(str(m.get("hdl_jedec", "")))
            cis_jd = self._escape_html(str(m.get("cis_jedec", "")))
            note = self._escape_html(str(m.get("error_note", "")))
            conf_pct = int(confidence * 100)
            conf_color = self._score_color(confidence)

            # v2.0: Phase info
            phase1_type = self._escape_html(str(m.get("phase1_type", "")))
            phase1_prior = m.get("phase1_prior_conf", 0)
            phase2_detail = self._escape_html(str(m.get("phase2_strategy_detail", "")))

            # v2.0: Match dims display
            match_dims_display = self._render_match_dims(phase2_detail)

            # v2.0: NEEDS_REVIEW highlighting
            row_class = ""
            row_style = ""
            if strategy == "NEEDS_REVIEW":
                row_class = ' class="needs-review"'
                row_style = ' style="background:#FFF0EF"'

            # v2c (A.3): main matched row is dark; conf uses light green.
            # NEEDS_REVIEW rows keep the light red highlight instead.
            main_class = "" if strategy == "NEEDS_REVIEW" else ' class="match-main"'

            # v2.0: Top-3 candidates with full detail
            top3: list[dict] = m.get("top3_candidates", [])
            top3_html = ""
            if top3:
                top3_rows = ""
                for rank, entry in enumerate(top3, 1):
                    t_type = self._escape_html(str(entry.get("type", "")))
                    t_cell = self._escape_html(str(entry.get("library_id", entry.get("part_name", ""))))
                    t_prim = self._escape_html(str(entry.get("primitive", "")))
                    t_value = self._escape_html(str(entry.get("value", "")))
                    t_jedec = self._escape_html(str(entry.get("jedec", "")))
                    t_pkg = self._escape_html(str(entry.get("package_type", "") or entry.get("footprint", "")))
                    t_pins = self._escape_html(str(entry.get("pin_count", "")))
                    t_part = self._escape_html(str(entry.get("part_name", "")))
                    t_conf = entry.get("final_conf", "")
                    t_dims = self._escape_html(str(entry.get("match_dims", "")))
                    t_conf_pct = f"{int(float(t_conf) * 100)}%" if t_conf else ""
                    # Phase XII R7: colorize candidate conf like the main row
                    t_conf_color = self._score_color(float(t_conf)) if t_conf else "#6B6860"
                    top3_rows += f"""
                    <tr class="top3-row" style="font-size:11px;color:#8D8983;background:rgba(108,104,96,0.04);">
                        <td colspan="2" style="text-align:right;padding-right:8px;">↳ Rank {rank} ({t_type})</td>
                        <td>{t_cell}</td>
                        <td>{t_prim}</td>
                        <td>{t_value}</td>
                        <td style="font-size:10px">{t_jedec}</td>
                        <td style="font-size:10px">{t_pkg}</td>
                        <td style="font-size:10px">{t_pins}</td>
                        <td style="color:{t_conf_color};font-weight:600">{t_conf_pct}</td>
                        <td colspan="2" style="font-size:10px">{t_dims}</td>
                        <td style="font-size:10px">{t_part}</td>
                    </tr>"""

                top3_html = f"""
                <tr class="top3-header" style="cursor:pointer;background:rgba(108,104,96,0.10);"
                    onclick="var el=this.nextElementSibling;
                    while(el && el.classList.contains('top3-row')){{
                        el.style.display=el.style.display==='none'?'table-row':'none';el=el.nextElementSibling;
                    }}">
                    <td colspan="12" style="font-size:10px;color:#9D9A91;font-weight:500;">
                        ▼ Top-{len(top3)} Candidates
                    </td>
                </tr>
                {top3_rows}"""

            rows_html += f"""
            <tr{main_class}{row_style}>
                <td style="font-weight:600">{source}</td>
                <td>{target}</td>
                <td>{cis_val}</td>
                <td style="font-size:11px">{cis_jd}</td>
                <td>{hdl_val}</td>
                <td style="font-size:11px">{hdl_jd}</td>
                <td style="font-size:11px">{hdl_pkg}</td>
                <td style="font-size:11px">{hdl_cat}</td>
                <td style="font-size:10px">{strategy}</td>
                <td class="conf-cell" style="color:{conf_color};font-weight:700">{conf_pct}%</td>
                <td style="font-size:10px;color:#9D9A91">{match_dims_display}</td>
                <td style="font-size:10px;color:#9D9A91">{note}</td>
            </tr>
            {top3_html}
            """

        return f"""
        <div class="section">
            <h2>Match Results</h2>
            <div class="table-scroll">
            <table class="match-table">
                <thead>
                    <tr>
                        <th>CIS Refdes</th>
                        <th>HDL Cell</th>
                        <th>CIS Value</th>
                        <th>CIS JEDEC</th>
                        <th>HDL Value</th>
                        <th>HDL JEDEC</th>
                        <th>HDL PACKAGE_TYPE</th>
                        <th>Type (phase1)</th>
                        <th>Strategy</th>
                        <th>Conf</th>
                        <th>Match Detail</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            </div>
        </div>
        """

    @staticmethod
    def _render_match_dims(detail: str) -> str:
        """Render match dimension string with colored emoji indicators.

        Format input: "value✅ footprint⚠️(default_0603) jedec❌ pin_count✅"
        Output: HTML with colored spans.
        """
        if not detail:
            return ""
        # Already has emoji — just escape and wrap
        escaped = (
            detail.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return f'<span style="font-size:10px">{escaped}</span>'

    def _render_issues_section(
        self,
        errors: list[Any],
        warnings: list[Any],
    ) -> str:
        """Render errors and warnings."""
        items_html = ""
        for e in errors:
            text = str(e) if not isinstance(e, dict) else e.get("message", str(e))
            items_html += f'<li class="issue error">❌ {self._escape_html(text)}</li>\n'
        for w in warnings:
            text = str(w) if not isinstance(w, dict) else w.get("message", str(w))
            items_html += f'<li class="issue warning">⚠️ {self._escape_html(text)}</li>\n'

        return f"""
        <div class="section">
            <h2>Issues</h2>
            <ul class="issue-list">
                {items_html}
            </ul>
        </div>
        """

    def _render_files_section(self, output_files: list[Any]) -> str:
        """Render the output files list."""
        items_html = ""
        for f in output_files:
            fname = str(f) if not isinstance(f, dict) else f.get("path", str(f))
            items_html += f"<li>{self._escape_html(fname)}</li>\n"

        return f"""
        <div class="section">
            <h2>Generated Files</h2>
            <ul class="file-list">
                {items_html}
            </ul>
        </div>
        """

    # ── Full HTML document ───────────────────────────────────────────

    def _render_full_html(self, title: str, body: str) -> str:
        """Wrap body content in a complete HTML document with Anthropic CSS."""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self._escape_html(title)}</title>
<style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: Poppins, Lora, -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
        font-size: 14px;
        color: #141413;
        background: #ECE9E0;
        line-height: 1.6;
    }}
    .container {{
        max-width: 1800px;
        margin: 32px auto;
        padding: 0 16px;
    }}
    .header {{
        background: #F5F3EC;
        border: 1px solid #D8D5CC;
        border-radius: 12px;
        padding: 24px 32px;
        margin-bottom: 24px;
    }}
    .header h1 {{
        font-size: 20px;
        font-weight: 700;
        color: #141413;
        margin-bottom: 8px;
    }}
    .header .timestamp {{
        font-size: 12px;
        color: #6B6860;
    }}
    .header .status {{
        font-size: 16px;
        font-weight: 600;
        margin-top: 8px;
    }}
    .summary-cards {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
    }}
    /* v2c (A.2): card groups with group title + rounded accent square */
    .card-group {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        background: #F5F3EC;
        border: 1px solid #D8D5CC;
        border-radius: 12px;
        padding: 14px;
        align-content: start;
    }}
    .card-group-title {{
        grid-column: 1 / -1;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        font-weight: 600;
        color: #6B6860;
        margin-bottom: 4px;
    }}
    .card-accent {{
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 4px;
        flex: 0 0 auto;
    }}
    .card {{
        background: #F5F3EC;
        border: 1px solid #D8D5CC;
        border-radius: 8px;
        padding: 12px 8px;
        text-align: center;
    }}
    .card-value {{
        font-size: 24px;
        font-weight: 700;
        color: #141413;
    }}
    .card-label {{
        font-size: 12px;
        color: #6B6860;
        margin-top: 4px;
    }}
    .section {{
        background: #F5F3EC;
        border: 1px solid #D8D5CC;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
    }}
    .section h2 {{
        font-size: 16px;
        font-weight: 600;
        color: #141413;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid #D8D5CC;
    }}
    .overall-score {{
        font-size: 48px;
        font-weight: 700;
        text-align: center;
        margin: 16px 0 8px;
    }}
    .overall-summary {{
        text-align: center;
        color: #6B6860;
        font-size: 13px;
    }}
    .match-summary {{
        text-align: center;
        color: #9D9A91;
        font-size: 12px;
        margin-bottom: 16px;
    }}
    .quality-bar {{
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        gap: 12px;
        min-height: 22px;
    }}
    .quality-label {{
        width: 240px;
        min-width: 240px;
        font-size: 11px;
        color: #6B6860;
        text-align: right;
        white-space: nowrap;
    }}
    .bar-track {{
        flex: 1;
        height: 8px;
        background: rgba(217, 119, 87, 0.12);
        border-radius: 4px;
        overflow: hidden;
    }}
    .bar-fill {{
        height: 100%;
        border-radius: 4px;
        transition: width 0.4s ease;
    }}
    .quality-pct {{
        width: 80px;
        font-size: 13px;
        font-weight: 600;
        color: #141413;
        text-align: left;
    }}
    .quality-desc {{
        font-size: 11px;
        color: #9D9A91;
        margin: 2px 0 12px 132px;
        line-height: 1.5;
        max-width: 520px;
    }}
    .match-table {{
        width: 100%;
        min-width: 1500px;
        border-collapse: collapse;
        font-size: 13px;
        table-layout: auto;
    }}
    .match-table th {{
        text-align: left;
        padding: 8px 12px;
        background: rgba(217, 119, 87, 0.08);
        color: #6B6860;
        font-weight: 600;
        border-bottom: 1px solid #D8D5CC;
        white-space: nowrap;
    }}
    .match-table td {{
        padding: 8px 12px;
        border-bottom: 1px solid #D8D5CC;
    }}
    /* Phase XII R8: compact fallback / output-type reference tables */
    .fallback-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }}
    .fallback-table th {{
        text-align: left;
        padding: 6px 10px;
        background: rgba(217, 119, 87, 0.08);
        color: #6B6860;
        font-weight: 600;
        border-bottom: 1px solid #D8D5CC;
        white-space: nowrap;
    }}
    .fallback-table td {{
        padding: 5px 10px;
        border-bottom: 1px solid rgba(216, 213, 204, 0.6);
        color: #141413;
    }}
    /* v2.0: NEEDS_REVIEW red highlighting */
    .needs-review td {{
        background: #FFF0EF;
    }}
    /* v2c (A.3): Top-1 main row — Phase XII R7: light gray bg + dark text.
       Slightly darker than the top-3 candidate rows (rgba(108,104,96,0.04))
       so the hierarchy is preserved while remaining readable.  The old
       medium-gray #6B6860 background was too dark; the conf color is now
       applied inline per-confidence (no !important override). */
    .match-main td {{
        background: #E5E2D8;
        color: #141413;
    }}
    /* v2.0: Top-3 collapsible rows */
    .top3-row td {{
        border-bottom: 1px solid rgba(216,213,204,0.5);
    }}
    .top3-header:hover {{
        background: rgba(217,119,87,0.08) !important;
    }}
    .table-scroll {{
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        border-radius: 8px;
        margin: 0 -2px;
        padding-bottom: 4px;
    }}
    .table-scroll::-webkit-scrollbar {{
        height: 6px;
    }}
    .table-scroll::-webkit-scrollbar-track {{
        background: rgba(141, 137, 131, 0.08);
        border-radius: 3px;
    }}
    .table-scroll::-webkit-scrollbar-thumb {{
        background: rgba(141, 137, 131, 0.25);
        border-radius: 3px;
    }}
    .table-scroll::-webkit-scrollbar-thumb:hover {{
        background: rgba(141, 137, 131, 0.40);
    }}
    .issue-list, .file-list {{
        list-style: none;
        padding: 0;
    }}
    .issue {{
        padding: 8px 12px;
        margin-bottom: 4px;
        border-radius: 6px;
        font-size: 13px;
    }}
    .issue.error {{
        background: rgba(192, 69, 58, 0.08);
        color: #C0453A;
    }}
    .issue.warning {{
        background: rgba(201, 148, 58, 0.08);
        color: #C9943A;
    }}
    .file-list li {{
        padding: 4px 0;
        font-family: "JetBrains Mono", "Cascadia Code", monospace;
        font-size: 12px;
        color: #6B6860;
    }}
    .footer {{
        text-align: center;
        color: #9D9A91;
        font-size: 11px;
        padding: 16px;
    }}
</style>
</head>
<body>
<div class="container">
{body}
<div class="footer">Generated by CIS2HDL v2.0 — OrCAD CIS to HDL Schematic Converter</div>
</div>
</body>
</html>"""

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _score_color(score: float) -> str:
        """Return a color hex for a quality score."""
        if score >= 0.90:
            return "#6B8F47"
        elif score >= 0.75:
            return "#5A89B8"
        elif score >= 0.60:
            return "#C9943A"
        elif score >= 0.40:
            return "#D97757"
        else:
            return "#C0453A"

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters in text."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _report_to_dict(self, report: Any) -> dict[str, Any]:
        """Convert a ConversionReport to a plain dict for serialization."""
        data: dict[str, Any] = {}

        for attr in (
            "project_name", "pages", "instances", "nets",
            "output_files", "errors", "warnings",
            "hdl_components_scanned",
        ):
            if hasattr(report, attr):
                data[attr] = getattr(report, attr)

        # Phase XII R8: default fallback component table (type → defaults)
        fallback_table = getattr(report, "fallback_table", None)
        if fallback_table:
            data["fallback_table"] = fallback_table

        data["success"] = getattr(report, "success", len(data.get("errors", [])) == 0)

        quality = getattr(report, "quality", None)
        if quality is not None and hasattr(quality, "to_dict"):
            qd = quality.to_dict()
            if "total_pages" not in qd:
                qd["total_pages"] = data.get("pages", 0)
            data["quality"] = qd

        stage_errors = getattr(report, "stage_errors", {})
        if stage_errors:
            data["stage_errors"] = {
                k: [{"severity": str(getattr(e, "severity", "")),
                     "message": str(e)} for e in v]
                for k, v in stage_errors.items() if isinstance(v, list)
            }

        # v2.0: Enriched match results with phase1/phase2/top3 + HDL data
        match_results = getattr(report, "match_results", None)
        if match_results:
            data["match_results"] = [
                {
                    "source_library_id": m.source_library_id,
                    "target_library_id": m.target_library_id,
                    "confidence": m.confidence,
                    "strategy": str(m.strategy),
                    "cis_value": getattr(m, "cis_value", ""),
                    "error_note": getattr(m, "error_note", ""),
                    # v2.0 fields
                    "phase1_type": getattr(m, "phase1_type", ""),
                    "phase1_prior_conf": getattr(m, "phase1_prior_conf", 0.0),
                    "phase2_strategy_detail": getattr(m, "phase2_strategy_detail", ""),
                    "phase2_within_conf": getattr(m, "phase2_within_conf", 0.0),
                    "top3_candidates": getattr(m, "top3_candidates", []),
                    # v2.0 HDL data from extra_data
                    "hdl_value": m.extra_data.get("hdl_value", ""),
                    "hdl_footprint": m.extra_data.get("hdl_footprint", ""),
                    "hdl_jedec": m.extra_data.get("hdl_jedec", ""),
                    "hdl_package_type": m.extra_data.get("hdl_package_type", ""),
                    "hdl_category": m.extra_data.get("hdl_category", "") or getattr(m, "phase1_type", ""),
                    "cis_jedec": getattr(m, "jedec_type", ""),  # CIS-side PST JEDEC
                }
                for m in match_results
            ]

        # v2c (A.2): top-level derived statistics (computed here, not on
        # ConversionReport) so both JSON and HTML consumers can rely on them.
        data["hdl_pages"] = sum(
            1 for f in data.get("output_files", [])
            if str(f).lower().endswith(".csa")
        )
        data["matched_instances"] = sum(
            1 for m in match_results or []
            if getattr(m.strategy, "value", str(m.strategy)) not in ("MANUAL", "NEEDS_REVIEW")
            and m.confidence > 0
        )
        data["matched_nets"] = data.get("nets", 0)

        validation_errors = getattr(report, "validation_errors", None)
        if validation_errors:
            data["validation_errors"] = [
                {"code": e.code, "severity": str(e.severity),
                 "message": e.message, "suggestion": e.suggestion}
                for e in validation_errors
            ]

        return data
