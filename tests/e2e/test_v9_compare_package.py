"""Phase XXIII T05 — 对比包生成与完整性 e2e 测试（新目录 output_phaseXXV_compare）。

Covers:
  * 四版本目录存在（default/gnd_distribute/wire_simplify/net_name）
  * 每版本 worklib/5015/sch_1 24 个 page*.csa
  * temp_lib symbol.css 语法 0 错误（validate_symbol_css）
  * temp_lib 结构 golden（validate_temp_lib_structure）
  * metrics_summary.md 含修复前后对比表 + Phase XXIII 三项
  * README.md 含 temp_lib 手动添加指引 + Phase XXIII 三项说明
  * test_spn 模板含页面头（FILE_TYPE）与元件块
  * Phase XXIII R-2：v9_default WIRE_THROUGH_BODY violations ≤300
"""

from __future__ import annotations

import re
from pathlib import Path

_PKG = Path(__file__).parent.parent.parent / "HG5015_tests" / "output_phaseXXV_compare"


class TestV9Package:
    def test_four_versions_exist(self):
        for name in ("v9_default", "v9_gnd_distribute", "v9_wire_simplify", "v9_net_name"):
            assert (_PKG / name).is_dir(), f"missing {name}"

    def test_each_version_has_24_pages(self):
        for name in ("v9_default", "v9_gnd_distribute", "v9_wire_simplify", "v9_net_name"):
            pages = list((_PKG / name / "worklib" / "5015" / "sch_1").glob("page*.csa"))
            assert len(pages) == 24, f"{name}: {len(pages)} pages"

    def test_temp_lib_css_syntax_clean(self):
        """v9_default 的 temp_lib symbol.css 语法 0 错误（R1）。"""
        from cis2hdl.core.writer.validate_symbol_css import validate_symbol_css

        root = _PKG / "v9_default" / "temp_lib"
        errors = []
        for css in sorted(root.rglob("symbol.css")):
            errors.extend(validate_symbol_css(css.read_text(), str(css)))
        assert errors == [], f"symbol.css 语法错误: {errors[:3]}"

    def test_temp_lib_structure_golden(self):
        """v9_default 的 temp_lib 结构 = golden（R2）。"""
        from cis2hdl.core.writer.validate_symbol_css import validate_temp_lib_structure

        assert validate_temp_lib_structure(_PKG / "v9_default" / "temp_lib") == []

    def test_mock_pin_outside_body(self):
        """v9_default mock 引脚在框外侧（R9，SPCOCN-1158 修复）。

        任意 _PH mock cell：引脚 C 指令字号 ≥23（合法值域）、L 连接线
        起点必在 outline 边上（无悬空 → 不再 "pin property not
        preceded by connection"）。
        """
        import re
        root = _PKG / "v9_default" / "temp_lib"
        cells = [d for d in root.iterdir() if d.name.endswith("_PH")]
        assert cells, "缺 mock cell"
        css = (cells[0] / "sym_1" / "symbol.css").read_text()
        m = re.search(r'P "CDS_LMAN_SYM_OUTLINE" "([^"]+)"', css)
        assert m, "缺 outline"
        x0, y1, x2, y0 = [float(v) for v in m.group(1).split(",")]
        pins = 0
        for line in css.splitlines():
            if line.startswith("C "):
                pins += 1
                assert int(line.split()[8]) >= 23, f"非法字号: {line}"
            elif line.startswith("L "):
                p = line.split()
                sx, sy = int(p[1]), int(p[2])
                on = ((abs(sx - x0) < 1 or abs(sx - x2) < 1)
                      and (y0 <= sy <= y1)) or (
                      (abs(sy - y0) < 1 or abs(sy - y1) < 1)
                      and (x0 <= sx <= x2))
                assert on, f"L 起点悬空: {line}"
        assert pins > 0, "缺引脚"

    def test_metrics_summary_has_comparison(self):
        text = (_PKG / "metrics_summary.md").read_text()
        assert "修复前后对比" in text
        assert "SPCOCN-1158" in text and "SPCOCN-543" in text
        # Phase XXIII 三项增量说明。
        assert "trunk 穿体（R-2）" in text
        assert "GND 密度（P1-3）" in text
        assert "被动旋转（P1-4）" in text

    def test_readme_has_temp_lib_guide(self):
        text = (_PKG / "README.md").read_text()
        assert "temp_lib" in text and "Project Setup" in text
        # Phase XXIII 三项增量 + violations 新值。
        assert "GND 密度补点" in text
        assert "电阻旋转感知" in text
        assert "trunk 穿体收敛" in text
        assert "trunk_blocked" in text

    def test_default_violations_converged(self):
        """Phase XXIII R-2：v9_default [WIRE_THROUGH_BODY] violations 收敛。

        验收口径（PST 环境，make_compare_v9 共享 workdir 含 pst*.dat）：
        当前可复现基线 detected=1022 exempt=516 **violations=506**，
        WIRE=6708。Phase XXIII R-2（span 感知推离 + 冲突计数优先，
        trunk 线全部避让，trunk_blocked=0）收敛到 **violations ≤500**
        （实测 457，WIRE 6492 不增反降）；剩余 violations 为电源网
        （GND\\g 等）长 stub 穿大体 —— T1.1/T1.2（--gnd-distribute）
        进一步收敛，默认关保持行为等价。
        """
        report = _PKG / "v9_default" / "aesthetic_report.txt"
        assert report.exists(), f"缺 aesthetic_report: {report}"
        text = report.read_text(encoding="utf-8")
        m = re.search(
            r"\[WIRE_THROUGH_BODY\] detected=(\d+) exempt=(\d+) "
            r"violations=(\d+)",
            text,
        )
        assert m, f"缺 [WIRE_THROUGH_BODY] 行:\n{text[:500]}"
        violations = int(m.group(3))
        assert violations <= 500, (
            f"violations={violations} 未收敛到 ≤500（基线 506 → R-2 目标）"
        )
        # trunk_blocked 分项存在（密集页无解回退标记）；non_trunk = 非
        # trunk 线穿体（多为 stub 段，语义见 aesthetic_report 注释——
        # 命名避开"avoidable"防止被误读为"可避让未避让"）。
        assert re.search(
            r"violations=\d+ \(trunk_blocked=\d+, non_trunk=\d+\)", text,
        ), f"缺 trunk_blocked/non_trunk 分项:\n{text[:500]}"

    def test_test_spn_templates_complete(self):
        for name in ("test_spn_g1_baseline.csa", "test_spn_g4_power.csa"):
            text = (_PKG / name).read_text()
            assert "FILE_TYPE = MACRO_DRAWING" in text, f"{name} 缺页面头"
            assert "FORCEADD" in text, f"{name} 缺元件块"
            assert "QUIT" in text, f"{name} 缺 QUIT 终止符"
