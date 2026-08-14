"""Phase XXI — 用户 Cadence 16.6 实测 9 类问题修复防回归（08-14）。

Covers:
  * A  —— mock symbol.css 9 个默认 P 属性 + MOCK_TEXT 声明（SPCOCN-542/545）
  * B  —— MOCK T 字号 59→89 + CSA MOCK_TEXT 实例属性标签（PAINT PINK + DISPLAY 1.5）
  * C  —— X PIN_TEXT 锚点 px±80、C 短号贴 outline 边（x0+25/x1-25）
  * D  —— IC3(AMS1117) 引脚名 pstchip 恢复（INPUT/OUTPUT/GND/TAP 替代 1-8）
  * E  —— U6H≥3000/U6I≥2400/U6A≥2400/U12≥1200 宽度钳制
  * F  —— 文本碰撞自检（char_w=28）0 碰撞 + 避让函数
  * G  —— overlap_resolver 双重赋值修复（位移=real 非 dx）+ max_move 200
  * H  —— n≤12 行距 50、y 起点 100（T 元件 4pin 高度减小）
  * I  —— 电线穿元件体检测（wires_through_bodies）+ aesthetic_report 记录
"""

from __future__ import annotations

import re
from pathlib import Path

_FIXTURES_HDL_LIB = Path(__file__).parent.parent / "fixtures" / "hdl_lib"


def _build(design, matches=None):
    from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder

    return ConnectivityModelBuilder(design, matches=matches or []).build()


def _mock_sym(refdes, pins):
    from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

    return MockIconLibrary().symbol_for(refdes, 1, pins)


class TestA_MockCssNinePProps:
    """SPCOCN-542/545：symbol 必须声明 FORCEPROP 注入的全部默认属性。"""

    def test_nine_default_p_props_declared(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        css = lib._symbol_css(sym)
        for prop in ("CDS_LMAN_SYM_OUTLINE", "$LOCATION", "VALUE", "PART_NAME",
                     "JEDEC_TYPE", "PATH", "PACKAGE_TYPE", "DESCRIPTION",
                     "SN_NUM", "MOCK_TEXT"):
            assert f'P "{prop}"' in css, f"P {prop} 缺失（SPCOCN-542 会复发）"

    def test_p_order_matches_real_library(self):
        """顺序对齐真实库 capacitor：PART_NAME/JEDEC_TYPE/PATH/PACKAGE_TYPE/
        DESCRIPTION/SN_NUM（PATH 在 PACKAGE_TYPE 前）。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0")])
        css = lib._symbol_css(sym)
        props = [ln.split()[1].strip('"') for ln in css.splitlines()
                 if ln.startswith('P "') and ln.split()[1].strip('"') not in (
                     "CDS_LMAN_SYM_OUTLINE", "$LOCATION", "VALUE", "MOCK_TEXT")]
        expect = ["PART_NAME", "JEDEC_TYPE", "PATH", "PACKAGE_TYPE",
                  "DESCRIPTION", "SN_NUM"]
        assert props == expect, props

    def test_annotate_false_omits_mock_text(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary(annotate=False)
        sym = lib.symbol_for("U6", 1, [("K18", "A0")])
        css = lib._symbol_css(sym)
        assert "MOCK_TEXT" not in css
        assert "MOCK" not in css


class TestB_MockLabel:
    def test_t_font_89(self):
        """P5：MOCK T 指令字号 59→89（1.5×）。"""
        css = _mock_sym("U6", [("K18", "A0")]).__class__.__name__
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0")])
        css = lib._symbol_css(sym)
        t_lines = [ln for ln in css.splitlines() if ln.startswith("T 0 ")]
        assert t_lines, "no T instruction"
        font = int(t_lines[0].split()[5])
        assert font == 89, f"T font {font} != 89"

    def test_csa_mock_text_label_pink(self):
        """P5：mock FORCEADD 块注入 MOCK_TEXT 属性标签（PAINT PINK +
        DISPLAY 1.5 大字、元件上方）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        p1 = _page("U20", {"1": "A", "2": "B", "3": "C"})
        design = _design(p1)
        conn = _build(design)
        writer = CSAWriter(routing_cfg=RoutingConfig(),
                           hdl_lib_path=_FIXTURES_HDL_LIB)
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        assert "FORCEPROP 1 LAST MOCK_TEXT MOCK" in content
        assert "PAINT PINK" in content
        assert "DISPLAY 1.5" in content
        # 标签坐标 = body + rotate(0, outline顶部+60)（在图标上方）
        m = re.search(r"FORCEPROP 1 LAST MOCK_TEXT MOCK\nJ 1\n\((-?\d+) (-?\d+)\);",
                      content)
        assert m, "MOCK_TEXT block format 错误"
        # outline 顶部 = 200（3pin mock）→ 标签 y = body_y + 260
        block = content[content.find("FORCEADD U20_PH"):]
        head = block[: block.find(";") + 1]
        bm = re.search(r"\((-?\d+) (-?\d+)\);", head)
        bx, by = int(bm.group(1)), int(bm.group(2))
        assert int(m.group(1)) == bx
        assert int(m.group(2)) == by + 260


def _page(refdes, pins, extra=None):
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import PageIR

    p = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    p.instances.append(ComponentInstanceIR(
        refdes=refdes, library_id=refdes, loc_x=1000, loc_y=2000,
        rotation=0, mirror=0, pin_connections=pins,
        extra_data=dict(extra or {}),
    ))
    return p


def _design(p1):
    from cis2hdl.core.ir.design import DesignIR

    return DesignIR(project_name="T", pages=[p1])


class TestC_PinAnchor:
    def test_x_anchor_px80(self):
        """P5：X PIN_TEXT 锚点 px±80（旧 px±50 与 C 号视觉靠近）。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("J4", 1, [("1", "TXD"), ("2", "RXD"), ("3", "")])
        css = lib._symbol_css(sym)
        # left 引脚 px=-450 → X 锚点 -530（px-80）
        assert 'X "PIN_TEXT" "TXD" -530 100 0 1' in css, css
        # right 引脚 px=+450 → X 锚点 +530（px+80）
        assert 'X "PIN_TEXT" "3" 530 100 0 0' in css, css

    def test_c_number_inside_outline(self):
        """E 几何铁律：C 短号贴 outline 边（x0+25/x1-25），不落框外。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("J4", 1, [("1", "TXD"), ("2", "RXD"), ("3", "")])
        css = lib._symbol_css(sym)
        o = [float(v) for v in sym.outline.split(",")]
        x0 = int(min(o[0], o[2]))
        x1 = int(max(o[0], o[2]))
        # left 列 C 标签 x == x0+25 = -325；right 列 == x1-25 = 325
        assert ' "1" -325 100' in css, css
        assert ' "3" 325 100' in css, css


class TestD_PstchipPinRecovery:
    def test_ic3_recovers_real_pin_names(self):
        """P6：IC3(AMS1117) 网名空 → pstchip 恢复 INPUT/OUTPUT/GND/TAP
        替代占位 1-8。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        p1 = _page("IC3", {}, extra={
            "pstchip_pin_names": {"3": "INPUT", "2": "OUTPUT",
                                  "1": "GND", "4": "TAP"},
        })
        conn = _build(_design(p1))
        irec = conn.pages[0].instances[0]
        names = [(p.pin_number, p.pin_name) for p in irec.pins]
        assert names == [("1", "GND"), ("2", "OUTPUT"),
                         ("3", "INPUT"), ("4", "TAP")], names
        writer = CSAWriter(routing_cfg=RoutingConfig(),
                           hdl_lib_path=_FIXTURES_HDL_LIB)
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        assert re.search(r"FORCEADD IC3_PH\.\.1", content)
        sym = writer._mock_lib.symbol_for(
            "IC3", 1, [(p.pin_number, p.pin_name) for p in irec.pins],
        )
        assert sym.pin_names == ["GND", "OUTPUT", "INPUT", "TAP"], sym.pin_names
        assert sym.pin_count == 4

    def test_no_pstchip_keeps_8pin_fallback(self):
        """无 pstchip 数据 → 保持 8 引脚占位（不回归 Phase XX）。"""
        sym = _mock_sym("J19", [])
        assert sym.pin_count == 8

    def test_wrong_fallback_overridden_by_pstchip(self):
        """P6 增强（08-14）：错误 fallback（IC3→CH347）时 _resolve_term 解析
        出 CH347 引脚名（RST#/CTS/GPIO6），但只要 pstchip 有该引脚号真实名
        （AMS1117 → GND/OUTPUT/INPUT/TAP）且与当前名不一致，按引脚号覆盖。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        p1 = _page("IC3", {}, extra={
            "pstchip_pin_names": {"3": "INPUT", "2": "OUTPUT",
                                  "1": "GND", "4": "TAP"},
        })
        conn = _build(_design(p1))
        irec = conn.pages[0].instances[0]
        names = [(p.pin_number, p.pin_name) for p in irec.pins]
        # CH347 fallback 引脚名（1=RST#/2=CTS/GPIO6/3=TXD1/4=RXD1）被覆盖为
        # AMS1117 真实名（按引脚号）。
        assert names == [("1", "GND"), ("2", "OUTPUT"),
                         ("3", "INPUT"), ("4", "TAP")], names
        writer = CSAWriter(routing_cfg=RoutingConfig(),
                           hdl_lib_path=_FIXTURES_HDL_LIB)
        sym = writer._mock_lib.symbol_for(
            "IC3", 1, [(p.pin_number, p.pin_name) for p in irec.pins],
        )
        assert sym.pin_names == ["GND", "OUTPUT", "INPUT", "TAP"], sym.pin_names


class TestE_WidthClamps:
    def test_user_target_widths(self):
        """P7/P8/P11/P19：U6H≥3000/U6I≥2400/U6A≥2400/U12≥1200。"""
        for ref, pins, target in [
            ("U6H", [(f"P{i}", "VDD_PMU2_1P8_FNPLL") for i in range(1, 46)],
             3000),
            ("U6I", [(f"P{i}", "0V9_WIFI") for i in range(1, 51)], 2400),
            ("U6A", [(f"P{i}", "BB_QP_MRX_TG1_5G") for i in range(1, 36)],
             2400),
            ("U12", [(str(i), "") for i in range(1, 18)], 1200),
        ]:
            sym = _mock_sym(ref, pins)
            o = [float(v) for v in sym.outline.split(",")]
            width = abs(o[2] - o[0])
            assert width >= target, f"{ref} width {width} < {target}"
            # 50 栅格对齐
            assert width % 50 == 0, f"{ref} width {width} off-grid"

    def test_pin_count_band_general_clamp(self):
        """引脚数分档兜底：n>64 → 3000、24≤n≤64 → 2400、13≤n≤23 → 1200。"""
        from cis2hdl.core.writer.mock_icon_lib import _min_mock_width

        assert _min_mock_width("X99", 100) == 3000
        assert _min_mock_width("X99", 30) == 2400
        assert _min_mock_width("X99", 15) == 1200
        assert _min_mock_width("X99", 8) == 0


class TestF_TextOverlap:
    def _overlap(self, refdes, pins):
        from cis2hdl.core.writer.mock_icon_lib import mock_text_overlap_count

        sym = _mock_sym(refdes, pins)
        offs = {
            i + 1: (sym.offsets[num][0], sym.offsets[num][1], sym.sides[num])
            for i, num in enumerate(sym.pin_numbers)
        }
        labels = {i + 1: sym.labels[num] for i, num in enumerate(sym.pin_numbers)}
        numbers = {i + 1: num for i, num in enumerate(sym.pin_numbers)}
        return mock_text_overlap_count(offs, labels, numbers)

    def test_zero_overlap_all_tiers(self):
        """P12/P13：U6B/U6 等各档位 mock 文本 0 碰撞（char_w=28 口径）。"""
        cases = [
            ("U6B", [(str(i), f"VSS{i}") for i in range(1, 87)]),
            ("U5", [(str(i), f"F{i}") for i in range(1, 101)]),
            ("U6", [("1", "DDR_ADDR14"), ("2", "DDR_CLK_N"),
                    ("3", "VDD_COMMON15_1P2")]),
            ("U6H", [(f"P{i}", "VDD_PMU2_1P8_FNPLL") for i in range(1, 46)]),
        ]
        for refdes, pins in cases:
            ov = self._overlap(refdes, pins)
            assert ov == 0, f"{refdes} 文本碰撞 {ov} 组"

    def test_duplicate_long_names_no_overlap(self):
        """去重后缀（GND_2/GND_3…）使标签更长 —— 布局按实际标签长算。"""
        names = ["VDD_PMU2_1P8_FNPLL"] * 6 + ["VDD_WL_5G_1P8"] * 4
        pins = [(str(i), names[i - 1]) for i in range(1, len(names) + 1)]
        ov = self._overlap("U6X", pins)
        assert ov == 0, f"长名重复后缀仍碰撞 {ov} 组"

    def test_pin_number_name_key_collision_no_310(self):
        """U5_PH 310 根因（Phase XXI F3 追加）：BGA 引脚号（如 A7）可能与
        另一引脚的功能名（如 DDR 地址线 A7）相同 —— 旧实现 offsets 裸键
        覆盖 → 两引脚同坐标（SPCOCN-310 第二引脚被忽略）。名称键加
        ``"name:"`` 前缀隔离后：同键名（引脚号 A7 vs 功能名 A7）不再冲突。
        """
        from collections import Counter

        # U5_PH 实测形态：引脚号含 A1/A2/A3/A7/A8/A9，功能名也含这些。
        nums = ["P3", "K1", "T8", "G2", "N7", "A7", "M7", "L2", "P2", "P7",
                "R2", "N2", "R3"] + [f"X{i}" for i in range(1, 84)]
        names = ["A2", "ODT", "A8", "DQL6", "DQU4", "A7", "VSSQ8", "A3",
                 "DQU7", "A9", "VSS1", "A1", "DQU5"] + [f"F{i}" for i in range(1, 84)]
        sym = _mock_sym("U5", list(zip(nums, names)))
        coords = [sym.offsets[n][:2] for n in sym.pin_numbers]
        dup = [k for k, v in Counter(coords).items() if v > 1]
        assert not dup, f"引脚号/功能名键冲突仍致坐标重叠: {dup}"

    def test_offset_for_name_prefixed_key(self):
        """offset_for 按名称回退时命中 ``name:`` 前缀键（不误中引脚号）。"""
        sym = _mock_sym("U5", [("A7", "VDD_WL"), ("R2", "A7")])
        # 引脚号 A7 → 第一引脚坐标；功能名 A7（第二引脚）不覆盖。
        off_by_num = sym.offset_for("A7")
        off_by_name = sym.offset_for("R2", "A7")
        assert off_by_num != (0, 0) and off_by_num != off_by_name
        assert off_by_num == sym.offsets["A7"]
        assert off_by_name == sym.offsets["name:A7"]


class TestG_OverlapResolver:
    def _resolver(self):
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        return OverlapResolver(margin=50, grid=50)

    def test_real_shift_not_full_dx(self):
        """位移量 = separation - margin 冗余（real），而非完整分离向量 dx。"""
        r = self._resolver()
        passives = {"J1": (0, 0, 200, -100), "J2": (100, 0, 300, -100)}
        res = r.resolve_passives(passives, max_move=200)
        dx = res.displacements["J2"][0]
        assert dx == 150, f"位移 {dx} != 150（应为 real=dx-margin，非完整 dx）"

    def test_identical_group_spreads_deterministically(self):
        """源图坐标完全相同（J/T 组）→ 确定性偏移散开（±50*n 兜底）。"""
        r = self._resolver()
        passives = {"J3": (0, 0, 100, -50),
                    "J4": (0, 0, 100, -50),
                    "J5": (0, 0, 100, -50)}
        res = r.resolve_passives(passives, max_move=200)
        moved = res.displacements
        assert len(moved) >= 2, moved
        # 散开后任意两件间距 ≥ 50（不再重叠）
        rects = {"J3": (0, 0, 100, -50)}
        for k, (dx, dy) in moved.items():
            rects[k] = (dx, dy, dx + 100, dy - 50)
        from cis2hdl.core.writer.overlap_detector import detect_collisions
        keys = list(rects)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                cols = detect_collisions([rects[keys[i]]], [rects[keys[j]]],
                                         margin=0)
                assert not cols, f"{keys[i]} vs {keys[j]} 仍重叠"

    def test_max_passive_move_200_default(self):
        from cis2hdl.core.config import RoutingConfig

        assert RoutingConfig().placement.max_passive_move == 200


class TestH_SmallChipHeight:
    def test_four_pin_chip_height_reduced(self):
        """P21：n≤12 行距 50、y 起点 100 → T 元件 4pin 高度明显减小。"""
        from cis2hdl.core.writer.mock_icon_lib import distribute_mock_pin_offsets

        d = distribute_mock_pin_offsets(4)
        assert d[1] == (-450, 100, "left")
        assert d[2] == (-450, 50, "left")
        assert d[3] == (450, 100, "right")
        assert d[4] == (450, 50, "right")
        sym = _mock_sym("T1", [("1", ""), ("2", ""), ("3", ""), ("4", "")])
        o = [float(v) for v in sym.outline.split(",")]
        height = abs(o[1] - o[3])
        assert height <= 300, f"T1 height {height} 仍过大"
        # 引脚仍对称（左右 y 相同）
        assert d[1][1] == d[3][1] and d[2][1] == d[4][1]


class TestI_WireThroughBody:
    def test_wires_through_bodies_detection(self):
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine, WireSegment

        outlines = [(-50, -50, 50, 50)]
        cross = WireLayoutEngine.wires_through_bodies(
            [WireSegment(0, -100, 0, 100)], outlines,
        )
        assert len(cross) == 1
        # 端点恰在边界 → 不算穿体
        assert WireLayoutEngine.wires_through_bodies(
            [WireSegment(50, -100, 50, 100)], outlines,
        ) == []
        # 水平穿体
        assert len(WireLayoutEngine.wires_through_bodies(
            [WireSegment(-100, 0, 100, 0)], outlines,
        )) == 1

    def test_report_section_present(self):
        """I：aesthetic_report 输出 [WIRE_THROUGH_BODY] 节。"""
        import tempfile
        from cis2hdl.core.writer.aesthetic_report import AestheticReport

        report = AestheticReport(project_name="T")
        report.add_wire_through_body(1, "GND", (0, -100, 0, 100), (-50, -50, 50, 50))
        # 用系统临时目录（/tmp）—— 项目内目录 rmtree 触发 sandbox 批量
        # 删除拦截（safe-delete）→ 全量测试失败。
        with tempfile.TemporaryDirectory() as out:
            p = report.write(Path(out))
            text = p.read_text(encoding="utf-8")
            assert "[WIRE_THROUGH_BODY] detected=1 exempt=0 violations=1" in text
            assert "--routing detour" in text
