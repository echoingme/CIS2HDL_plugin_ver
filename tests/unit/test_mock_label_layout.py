"""Phase XVIII R9 — mock 图标标签布局（引脚朝外/四边方向/字号）。

Covers:
  * 引脚 tip 在矩形框**外侧**（outline 内缩，R9 核心）
  * C 指令 justify 仅 R/L（R1 回归）
  * X "PIN_TEXT" 可见引脚名
  * 字号 temp_lib.pin_font_size（默认 16）
"""

from __future__ import annotations


class TestPinOutsideBody:
    def test_small_chip_pins_outside(self):
        """n≤12：引脚 max|x| > outline 半宽（引脚在框外）。"""
        from cis2hdl.core.writer.mock_icon_lib import (
            MockIconLibrary, distribute_mock_pin_offsets,
        )

        lib = MockIconLibrary()
        sym = lib.symbol_for("J4", 1, [("1", "A"), ("2", "B"), ("3", "")])
        offs = distribute_mock_pin_offsets(3)
        xs = [o[0] for o in offs.values()]
        o = [float(v) for v in sym.outline.split(",")]
        outline_half = max(abs(o[0]), abs(o[2]))
        pin_max = max(abs(min(xs)), abs(max(xs)))
        assert pin_max > outline_half, f"pin {pin_max} <= outline {outline_half}"

    def test_bga_pins_outside(self):
        """n>64 BGA 多列两侧：引脚 x 伸出 outline、py 全在 outline y 内
        （SPCOCN-1158 修复：L 连接线起点无悬空）。"""
        from cis2hdl.core.writer.mock_icon_lib import (
            MockIconLibrary, distribute_mock_pin_offsets,
        )

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6C", 1, [(f"P{i}", f"F{i}") for i in range(1, 90)])
        # Phase XX 补丁3：xs/ys 必须与 outline 同源（sym.offsets）——
        # distribute(89) 无名字与 symbol 有名字（F1..F89）尺寸不同。
        xs = [v[0] for v in sym.offsets.values()]
        ys = [v[1] for v in sym.offsets.values()]
        o = [float(v) for v in sym.outline.split(",")]
        # x 方向引脚 tip 伸出 outline
        assert max(abs(min(xs)), abs(max(xs))) > max(abs(o[0]), abs(o[2]))
        # y 方向引脚全部落在 outline y 范围内（L 起点在 outline 上）
        assert min(ys) >= o[3] and max(ys) <= o[1], (min(ys), max(ys), o[1], o[3])

    def test_pin_line_connects_tip_to_edge(self):
        """L 线从 body 边缘连到引脚 tip（引脚朝外）。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("J4", 1, [("1", "A"), ("2", "B"), ("3", "")])
        css = lib._symbol_css(sym)
        # left 引脚: L <edge> <py> <px> <py>，px 在 outline 外
        lines = [l for l in css.splitlines() if l.startswith("L ")]
        assert lines, "no pin lines"
        for line in lines:
            parts = [int(v) for v in line.split()[1:5]]
            # 段端点至少一端在 outline 外（|x| 或 |y| > 100）
            assert any(abs(v) > 100 for v in parts), line


class TestCJustifyRL:
    def test_all_justify_rl(self):
        """C 指令 justify 仅 R/L（R1 回归，U/D 已消除）。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        for refdes, pins in [
            ("J4", [("1", "A"), ("2", "B"), ("3", "")]),
            ("U6C", [(f"P{i}", f"F{i}") for i in range(1, 90)]),
        ]:
            sym = lib.symbol_for(refdes, 1, pins)
            css = lib._symbol_css(sym)
            for line in css.splitlines():
                if line.startswith("C "):
                    last = line.split()[-1]
                    assert last in ("R", "L"), f"bad justify {last}: {line}"


class TestPinText:
    def test_x_pin_text_present(self):
        """每个 mock cell 含 X "PIN_TEXT"（真实库 ch347 先例）。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        css = lib._symbol_css(sym)
        assert 'X "PIN_TEXT"' in css

    def test_font_size_clamped_legal(self):
        """C 指令字号钳制到合法值域 ≥23（SPCOCN-1158 修复）。

        真实库 C 指令 font 合法值域 {0,1,22,23,24,29,32,34,38,40,41}
        （grep 全库实锤），16 是非法字号 → Cadence 报 "pin property not
        preceded by connection"。配置 16 时输出钳制到 23。
        """
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary(pin_font_size=16, pin_text_size=16)
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        css = lib._symbol_css(sym)
        for line in css.splitlines():
            if line.startswith("C "):
                # C x y "label" lx ly rot vis font type justify → token[8]
                font = int(line.split()[8])
            elif line.startswith('X "PIN_TEXT"'):
                # X "PIN_TEXT" "label" x y rot justify font ... → token[7]
                font = int(line.split()[7])
            else:
                continue
            assert font >= 29, f"{line.strip()}: font {font} < 29"
