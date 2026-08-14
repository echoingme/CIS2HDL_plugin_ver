"""Phase XVIII R1 — mock symbol.css 语法校验器（validate_symbol_css.py）。

Covers:
  * U/D justify 被拒（SPCOCN-1158 根因：全库 65689 条 C 指令只有 R/L）
  * R/L justify 通过
  * 坐标数值合法性
  * 引号/括号闭合
  * mock css 含 X "PIN_TEXT"（真实库 ch347 先例）
"""

from __future__ import annotations


def _validator():
    from cis2hdl.core.writer.validate_symbol_css import validate_symbol_css

    return validate_symbol_css


class TestCJustifyRL:
    def test_ud_justify_rejected(self):
        validate = _validator()
        bad = 'C -725 725 "T12" -725 740 0 0 32 1 U\n'
        errors = validate(bad, "bad")
        assert errors, "U justify must be rejected"
        assert any("justify must be R/L" in e for e in errors)

        bad_d = 'C 725 -725 "T12" 725 -740 0 0 32 1 D\n'
        errors = validate(bad_d, "bad_d")
        assert any("justify must be R/L" in e for e in errors)

    def test_rl_justify_accepted(self):
        validate = _validator()
        good = (
            'C -300 -250 "RST#" -325 -250 0 1 32 0 R\n'
            'C 0 -75 "1" 0 -60 0 0 32 1 R\n'
            'C 75 0 "2" 60 0 0 0 32 0 L\n'
        )
        assert validate(good, "good") == []

    def test_top_bottom_orient_90_270_justify_r(self):
        """顶/底引脚用 orient 90/270 + justify R（不再用 U/D）。"""
        validate = _validator()
        good = (
            'C -800 800 "P1" -800 815 90 0 16 1 R\n'   # top
            'C 800 -800 "P51" 800 -815 270 0 16 1 R\n'  # bottom
        )
        assert validate(good, "good") == []

    def test_real_ch347_line_accepted(self):
        """真实库 ch347 C 指令格式通过校验。"""
        validate = _validator()
        line = 'C -300 -250 "RST#" -325 -250 0 1 32 0 R\n'
        assert validate(line, "ch347") == []


class TestCoordinateValidation:
    def test_non_numeric_coord_rejected(self):
        validate = _validator()
        bad = 'C -300 -250 "RST#" XX -250 0 1 32 0 R\n'
        errors = validate(bad, "bad")
        assert any("not numeric" in e for e in errors)

    def test_float_coords_accepted(self):
        validate = _validator()
        line = 'C -300.5 -250.25 "RST#" -325.0 -250 0 1 32 0 R\n'
        assert validate(line, "float") == []

    def test_too_short_c_line_rejected(self):
        validate = _validator()
        bad = 'C -300 -250 "RST#" -325 -250 0 1 32\n'  # 缺 justify
        errors = validate(bad, "bad")
        assert any("too short" in e for e in errors)


class TestQuoteParenBalance:
    def test_unbalanced_quotes_rejected(self):
        validate = _validator()
        bad = 'C -300 -250 "RST# -325 -250 0 1 32 0 R\n'
        errors = validate(bad, "bad")
        assert any("unbalanced quotes" in e for e in errors)

    def test_unbalanced_parens_rejected(self):
        validate = _validator()
        bad = "P \"CDS_LMAN_SYM_OUTLINE\" \"-150,150,150,-150\" (0 0\n"
        errors = validate(bad, "bad")
        assert any("unbalanced parens" in e for e in errors)

    def test_control_char_rejected(self):
        validate = _validator()
        bad = 'C -300 -250 "RST#\x01" -325 -250 0 1 32 0 R\n'
        errors = validate(bad, "bad")
        assert any("control char" in e for e in errors)


class TestMockCssIntegration:
    def test_mock_css_passes_and_has_pin_text(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary
        from cis2hdl.core.writer.validate_symbol_css import validate_symbol_css

        lib = MockIconLibrary()
        sym = lib.symbol_for(
            "U6", 1, [("K18", "A0"), ("G20", "GND"), ("G21", "GND")],
        )
        css = lib._symbol_css(sym)
        assert validate_symbol_css(css, "U6") == []
        assert 'X "PIN_TEXT"' in css

    def test_bga_mock_css_passes(self):
        """BGA 四边 mock（含 top/bottom 引脚）全量通过语法校验。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary
        from cis2hdl.core.writer.validate_symbol_css import validate_symbol_css

        lib = MockIconLibrary()
        sym = lib.symbol_for(
            "U5", 1, [(str(i), f"P{i}") for i in range(1, 101)],
        )
        css = lib._symbol_css(sym)
        errors = validate_symbol_css(css, "U5")
        assert errors == []
        c_lines = [ln for ln in css.splitlines() if ln.startswith("C ")]
        assert len(c_lines) == 100
        for ln in c_lines:
            assert ln.split()[-1] in ("R", "L")


class TestXInstructionType:
    """SPCOCN-1158 第二根因：未知 X 指令类型校验（Phase XIX）。

    真实库 X 指令类型只有 PIN_TEXT/VHDL_PORT/HDL_PORT（grep 实锤），
    ``X "MOCK_TEXT"`` 是未知类型 → Cadence 解析 symbol.css 失败报
    "pin property not preceded by connection"。
    """

    def test_x_pin_text_valid(self):
        from cis2hdl.core.writer.validate_symbol_css import validate_symbol_css

        css = (
            'X "PIN_TEXT" "A0" -90 150 0 0 23 0 0 0 0 0 1 0 0\n'
        )
        assert validate_symbol_css(css, "t.css") == []

    def test_x_mock_text_rejected(self):
        from cis2hdl.core.writer.validate_symbol_css import validate_symbol_css

        css = (
            'X "MOCK_TEXT" "MOCK/模拟图标" 0 0 0 0 24 0 0 0 0 0 1 0 0\n'
        )
        errs = validate_symbol_css(css, "t.css")
        assert errs and "unknown X instruction type" in errs[0]
