"""S2 T03 辅助脚本：从 conversion_engine.py 机械提取 legacy 内联块为方法。

一次性迁移工具（不进入包）；幂等性由"边界标记校验"保证。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cis2hdl" / "core" / "engine" / "conversion_engine.py"

# 1-indexed 边界（含）
PARSE_START, PARSE_END = 1604, 2043
REPORT_START, REPORT_END = 2330, 2373


def extract() -> None:
    lines = ENGINE.read_text(encoding="utf-8").split("\n")

    def check(idx1: int, needle: str, where: str) -> None:
        got = lines[idx1 - 1]
        assert needle in got, f"边界校验失败 {where}: 行{idx1} 期望含 {needle!r}，实际 {got!r}"

    check(PARSE_START, "Phase XI P0-D2", "parse-start")
    check(PARSE_END - 1, "readiness.symbol_score", "parse-end")
    check(PARSE_END + 2, "Stage 3: Scan", "parse-after")
    check(REPORT_START, "Mapping CSV Report", "report-start")
    check(REPORT_END, "Failed to write error logs", "report-end")
    check(REPORT_END + 2, "Final aggregation", "report-after")

    parse_block = lines[PARSE_START - 1:PARSE_END]          # 0-indexed [1603:2043]
    report_block = lines[REPORT_START - 1:REPORT_END]       # 0-indexed [2329:2373]

    # ── 校验 parse 块内没有 _bench/_t2/_t3（提取安全） ──
    for ln in parse_block:
        assert "_bench" not in ln and "_t2" not in ln and "_t3" not in ln, (
            f"parse 块引用了 timing 局部变量: {ln!r}"
        )

    # ── 生成 _legacy_load_input ──
    parse_body = "\n".join(parse_block)
    # 原块 `if design is None: return report` → 方法内 `return None`
    old_ret = "        if design is None:\n            return report\n"
    new_ret = "        if design is None:\n            return None\n"
    assert old_ret in parse_body, "parse 块内未找到 return report 模式"
    parse_body = parse_body.replace(old_ret, new_ret, 1)

    legacy_load = (
        "    def _legacy_load_input(\n"
        "        self,\n"
        "        input_path: Path,\n"
        "        report: ConversionReport,\n"
        "        pc: Optional[ProgressCallback],\n"
        "    ) -> Optional[DesignIR]:\n"
        "        \"\"\"S2 legacy fallback：原 convert() Stage 2 内联解析+增强块。\n\n"
        "        纯代码搬移（原 L1604-2043），不改逻辑。返回 DesignIR；失败 None。\n"
        "        \"\"\"\n"
        + parse_body
        + "\n        return design\n"
    )

    # ── 生成 _legacy_reports ──
    report_body = "\n".join(report_block)
    legacy_reports = (
        "    def _legacy_reports(\n"
        "        self,\n"
        "        design: DesignIR,\n"
        "        match_results: list,\n"
        "        output_dir: Path,\n"
        "        report: ConversionReport,\n"
        "        input_path: Path,\n"
        "    ) -> None:\n"
        "        \"\"\"S2 legacy fallback：原 convert() 报告块（mapping csv/top3/错误日志）。\n\n"
        "        纯代码搬移（原 L2330-2371），不改逻辑。\n"
        "        \"\"\"\n"
        + report_body
        + "\n"
    )

    # ── 替换 parse 块为钩子调用 ──
    hook_parse = (
        "        # ── Stage 2: Parse（S2 钩子：plugin 模式 load_input 可接管） ──\n"
        "        # legacy/未接管 → _legacy_load_input（原内联块，字节等价）\n"
        "        handled, _res = self._host.call(\n"
        "            ctx, \"load_input\",\n"
        "            fallback=lambda: self._legacy_load_input(input_path, report, pc),\n"
        "        )\n"
        "        if handled and ctx.ir is not None:\n"
        "            design = ctx.ir\n"
        "        else:\n"
        "            design = _res\n"
        "        if design is None:\n"
        "            return report\n"
    )
    lines[PARSE_START - 1:PARSE_END] = hook_parse.split("\n")

    # 行号偏移：parse 块被替换后，report 块位置变化
    delta = len(hook_parse.split("\n")) - (PARSE_END - PARSE_START + 1)
    r_start = REPORT_START + delta
    r_end = REPORT_END + delta

    def check2(idx1: int, needle: str, where: str) -> None:
        got = lines[idx1 - 1]
        assert needle in got, f"边界校验失败(shift) {where}: {got!r}"

    check2(r_start, "Mapping CSV Report", "report-start-shifted")
    check2(r_end, "Failed to write error logs", "report-end-shifted")
    check2(r_end + 2, "Final aggregation", "report-after-shifted")

    hook_report = (
        "        # ── Mapping CSV / Top3 / 错误日志（S2 钩子：write_report 可接管） ──\n"
        "        self._host.call(\n"
        "            ctx, \"write_report\",\n"
        "            fallback=lambda: self._legacy_reports(\n"
        "                design, match_results, output_dir, report, input_path,\n"
        "            ),\n"
        "        )\n"
    )
    lines[r_start - 1:r_end] = hook_report.split("\n")

    # ── 插入两个 legacy 方法（放在 _apply_phase14_matching 之后、convert 之前） ──
    # 锚点：convert 定义行
    convert_anchor = "    def convert("
    convert_idx = next(i for i, ln in enumerate(lines) if ln == convert_anchor)
    methods_text = legacy_load + "\n\n" + legacy_reports + "\n\n"
    lines[convert_idx:convert_idx] = methods_text.split("\n")

    ENGINE.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: 提取完成 ({PARSE_START}-{PARSE_END}, {REPORT_START}-{REPORT_END})")


if __name__ == "__main__":
    extract()
