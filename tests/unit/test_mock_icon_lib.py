"""Phase XVII M1 — temp_lib 模拟图标生成器（mock_icon_lib.py）。

Covers:
  * 三档引脚分布（n≤12 两列 / 12<n≤64 四列 pitch≥50 / n>64 BGA 四边）
  * 功能名标签去重后缀（GND → GND_2 → GND_3）+ 空回退引脚号
  * symbol.css / chips.prt / entity 生成 + 写入 temp_lib
  * cell 名大写 + MOCK_TEXT 标注（字号 24）
"""

from __future__ import annotations

from pathlib import Path


class TestDistributeMockPinOffsets:
    def test_small_two_columns(self):
        from cis2hdl.core.writer.mock_icon_lib import distribute_mock_pin_offsets

        d = distribute_mock_pin_offsets(8)
        assert len(d) == 8
        xs = {v[0] for v in d.values()}
        # Phase XXI：字符宽 18→28、边距 355 → 无名字基线 ±450
        assert xs == {-450, 450}
        sides = {v[2] for v in d.values()}
        assert sides == {"left", "right"}
        # 左右对称 top→bottom；Phase XXI H：行距 50、y 起点 100
        assert d[1] == (-450, 100, "left")
        assert d[5] == (450, 100, "right")

    def test_medium_four_columns_pitch_ge_50(self):
        from cis2hdl.core.writer.mock_icon_lib import distribute_mock_pin_offsets

        # 13 pins → 四列，pitch 必须 ≥ 50（修 pitch<50 bug）；
        # Phase XIX：列 x 随标签区感知（短名 → ±150/±100，长名扩大）。
        d = distribute_mock_pin_offsets(13)
        xs = {v[0] for v in d.values()}
        assert len(xs) == 4 and all(x != 0 for x in xs)
        # 短名基线：外列 ±150、内列 ±100
        assert min(abs(x) for x in xs) >= 100
        ys = sorted(v[1] for v in d.values())
        gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        assert min(g for g in gaps if g > 0) >= 50

    def test_bga_two_sides(self):
        """n>64 多列两侧分布（SPCOCN-1158 修复：四边分布角部悬空）。

        仅 left/right 两侧（引脚仅 x 方向伸出，py 全在 outline y 内，
        L 连接线起点必落在 outline 边上）。
        """
        from cis2hdl.core.writer.mock_icon_lib import distribute_mock_pin_offsets

        d = distribute_mock_pin_offsets(100)
        assert len(d) == 100
        sides: dict[str, int] = {}
        for v in d.values():
            sides[v[2]] = sides.get(v[2], 0) + 1
        assert set(sides) == {"left", "right"}
        rights = [v for v in d.values() if v[2] == "right"]
        lefts = [v for v in d.values() if v[2] == "left"]
        assert all(v[0] > 0 for v in rights)
        assert all(v[0] < 0 for v in lefts)


class TestUniqueFunctionalLabels:
    def test_duplicate_suffix_and_empty_fallback(self):
        from cis2hdl.core.writer.mock_icon_lib import unique_functional_labels

        labels = unique_functional_labels(
            ["1", "2", "3", "4", "5"],
            ["A0", "GND", "GND", "GND", ""],
        )
        assert labels == {1: "A0", 2: "GND", 3: "GND_2", 4: "GND_3", 5: "5"}

    def test_all_empty_falls_back_to_pin_number(self):
        from cis2hdl.core.writer.mock_icon_lib import unique_functional_labels

        labels = unique_functional_labels(["K18", "G20"], ["", ""])
        assert labels == {1: "K18", 2: "G20"}


class TestMockIconLibrary:
    def test_symbol_generation(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for(
            "U6", 1,
            [("K18", "A0"), ("G20", "GND"), ("G21", "GND"), ("G22", "GND")],
        )
        assert sym is not None
        assert sym.cell_name == "U6_PH"
        assert sym.pin_count == 4
        # 功能名去重：GND/GND_2/GND_3
        labels = set(sym.labels.values())
        assert "GND" in labels and "GND_2" in labels and "GND_3" in labels

    def test_css_has_mock_text_and_pins(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        css = lib._symbol_css(sym)
        assert "MOCK" in css  # T 指令文本（Phase XIX 短标识）
        # Phase XIX：默认 T 指令可见文本（真实库 INPORT 先例，两行结构：
        # T 行 + 文本行）——P 属性不渲染、X "MOCK_TEXT" 是未知 X 指令类型
        # （1158 根因）。Phase XXI B：字号 59→89（用户 P5"放大 1.5x"）。
        assert 'T 0 ' in css and ' 89 ' in css
        assert '\nMOCK\n' in css
        # Phase XXI A：9 个默认 P 属性 + MOCK_TEXT 声明（SPCOCN-542/545）。
        for _prop in ("PART_NAME", "JEDEC_TYPE", "PATH", "PACKAGE_TYPE",
                      "DESCRIPTION", "SN_NUM", "MOCK_TEXT"):
            assert f'P "{_prop}"' in css, _prop
        # Phase XVIII R1: 每个引脚有可见名 X "PIN_TEXT"。
        assert 'X "PIN_TEXT" "A0"' in css
        # Phase XXI C/E：A0/GND → 外列 ±450、C 短号贴 outline 边（x0+25）。
        assert ' "1" -325 100' in css or ' "1" 325 100' in css
        assert "CDS_LMAN_SYM_OUTLINE" in css

    def test_css_justify_only_rl(self):
        """R1: C 指令 justify 只允许 R/L（顶/底用 orient 90/270 表达方向）。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        # BGA 四边（含 top/bottom）—— 旧行为会生成 justify U/D。
        sym = lib.symbol_for(
            "U5", 1, [(str(i), f"P{i}") for i in range(1, 101)],
        )
        css = lib._symbol_css(sym)
        c_lines = [ln for ln in css.splitlines() if ln.startswith("C ")]
        assert c_lines, "no C lines"
        for ln in c_lines:
            assert ln.split()[-1] in ("R", "L"), ln
        assert 'X "PIN_TEXT"' in css

    def test_annotate_disabled_omits_mock_text(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary(annotate=False)
        sym = lib.symbol_for("U6", 1, [("K18", "A0")])
        css = lib._symbol_css(sym)
        assert "MOCK_TEXT" not in css

    def test_write_to_temp_lib(self, tmp_path):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        lib.symbol_for("J4", 1, [("1", "TXD"), ("2", "RXD"), ("3", "")])
        files = lib.write_to_temp_lib(tmp_path)
        assert files
        # cell 目录大写（与 FORCEADD 一致）
        assert (tmp_path / "U6_PH" / "sym_1" / "symbol.css").exists()
        assert (tmp_path / "U6_PH" / "chips" / "chips.prt").exists()
        # entity 目录（真实库结构）
        assert (tmp_path / "U6_PH" / "entity" / "master.tag").exists()
        assert (tmp_path / "U6_PH" / "entity" / "pc.db").exists()
        assert (tmp_path / "J4_PH" / "sym_1" / "symbol.css").exists()
        # Phase XVIII R2: master.tag 分目录内容 = golden。
        assert (tmp_path / "U6_PH" / "sym_1" / "master.tag").read_text().strip() == "symbol.css"
        assert (tmp_path / "U6_PH" / "chips" / "master.tag").read_text().strip() == "chips.prt"
        assert (tmp_path / "U6_PH" / "entity" / "master.tag").read_text().strip() == "verilog.v"
        # Phase XVIII R2: cell 根目录无 master.tag。
        assert not (tmp_path / "U6_PH" / "master.tag").exists()

    def test_chips_prt_has_pin_numbers(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        prt = lib._chips_prt(sym)
        assert "PIN_NUMBER='(K18)'" in prt
        assert "PIN_NUMBER='(G20)'" in prt

    def test_disabled_returns_none(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        assert MockIconLibrary(enabled=False).symbol_for(
            "U6", 1, [("K18", "A0")],
        ) is None

    def test_offset_for_by_number_and_name(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        assert sym.offset_for("K18") != (0, 0)
        assert sym.offset_for("G20") != (0, 0)
        # 未知引脚 → (0,0)
        assert sym.offset_for("Z99") == (0, 0)


class TestMockAll:
    """Phase XX（用户 08-13 决策）：所有多引脚芯片/connector 默认模拟图标。

    无论是否匹配到 hdl_lib 真实符号（如 J4 之前匹配真实库），mock_all=true
    时一律输出模拟图标；false 恢复"仅匹配失败才 mock"。
    """

    def test_mock_all_default_true(self):
        from cis2hdl.core.config import RoutingConfig
        cfg = RoutingConfig()
        assert cfg.temp_lib.mock_all is True

    def test_mock_all_makes_matched_j_use_mock(self):
        """J4 之前匹配真实库 → mock_all=true 后必须用 J4_PH mock。"""
        import re
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder

        # 用合成设计：一个 J 开头多引脚实例
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances.append(ComponentInstanceIR(
            refdes="J4", library_id="CONNECTOR", loc_x=1000, loc_y=2000,
            rotation=0, mirror=0,
            pin_connections={"1": "A", "2": "B", "3": "C"},
        ))
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        # 显式匹配（模拟 J4 匹配到真实库——旧行为会用真实库）
        cfg = RoutingConfig()
        writer = CSAWriter(routing_cfg=cfg, hdl_lib_path=__import__(
            "pathlib").Path("tests/fixtures/hdl_lib"))
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        assert re.search(r"FORCEADD J4_PH\.\.1", content), (
            "mock_all=true 时 J4 必须用模拟图标 J4_PH")
        # mock_all=false → 恢复旧行为（不 mock，用原 cell 名）
        cfg2 = RoutingConfig()
        cfg2.temp_lib.mock_all = False
        writer2 = CSAWriter(routing_cfg=cfg2, hdl_lib_path=__import__(
            "pathlib").Path("tests/fixtures/hdl_lib"))
        content2 = writer2._build_csa_content_conn(conn, conn.pages[0])
        assert "J4_PH" not in content2, "mock_all=false 时 J4 不应 mock"


class TestNoOverlappingPins:
    """SPCOCN-310 防回归（Phase XX 补丁，08-13 用户实测）。

    U6H/U6I/U6E/U6A 报 "More than one pin found at the same location"
    → 第二引脚被忽略 → 该引脚 SPN 属性 543 连锁被删。根因：``_lab2``
    在长名时与外列 ``_label_w`` 相同 → 内外列坐标完全重复。
    """

    def test_long_names_no_duplicate_coords(self):
        from collections import Counter
        from cis2hdl.core.writer.mock_icon_lib import distribute_mock_pin_offsets

        names = (["VDD_PMU2_1P8_FNPLL"] * 6
                 + ["VDD_WL_5G_1P8", "VDD_WL_5G_1P2",
                    "VDD_WL_2G_1P8", "VDD_WL_2G_1P2"]
                 + [f"SIG{i}" for i in range(14)])
        for n in (24, 45, 90, 150):
            offs = distribute_mock_pin_offsets(n, names[:n] if n < 24 else names)
            c = Counter((v[0], v[1]) for v in offs.values())
            dups = [k for k, cnt in c.items() if cnt > 1]
            assert not dups, f"n={n} 重叠坐标: {dups[:5]}"

    def test_inner_column_narrower_than_outer(self):
        """内列 x 必须 < 外列 x（310 根因的几何前提）。"""
        from cis2hdl.core.writer.mock_icon_lib import distribute_mock_pin_offsets

        offs = distribute_mock_pin_offsets(24, ["VDD_PMU2_1P8_FNPLL"] * 24)
        xs = sorted(set(v[0] for v in offs.values()))
        assert len(xs) == 4 and len(set(xs)) == 4, f"唯一 x 不足 4: {xs}"


class TestMockAllMissingPins:
    """pins 空/缺失场景也必须 mock（Phase XX 补丁）。

    用户实测 IC3（AMS1117→CH347）与 J19（RJ45_2X2_LED）仍用真实库错误
    图标——根因：这些实例匹配数据缺失（irec.pins 空）→ 旧代码
    ``len(pins) <= 1`` 在 mock_all 分支前拦截。修复：pins≤1 检查仅对
    legacy（mock_all=false）生效。
    """

    def test_pins_empty_chip_still_mock(self):
        import re
        from pathlib import Path
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        # 无 pin_connections → pins 空；cell 名 CH347（错误匹配真实库）
        p1.instances.append(ComponentInstanceIR(
            refdes="IC3", library_id="AMS1117", loc_x=1000, loc_y=2000,
            rotation=0, mirror=0,
            cell_name="CH347",
        ))
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        cfg = RoutingConfig()
        w = CSAWriter(routing_cfg=cfg, hdl_lib_path=Path("tests/fixtures/hdl_lib"))
        irec = conn.pages[0].instances[0]
        assert not list(getattr(irec, "pins", []) or []), "前置：pins 应为空"
        assert w._needs_placeholder(irec, "CH347", 1), "pins 空也须 mock（mock_all）"
        content = w._build_csa_content_conn(conn, conn.pages[0])
        assert re.search(r"FORCEADD IC3_PH\.\.1", content), (
            "CH347 错误匹配必须被 mock 接管")

    def test_rj45_connector_mock(self):
        from cis2hdl.core.writer.csa_writer import CSAWriter
        assert CSAWriter._is_connector_body("RJ45_2X2_LED")
        assert CSAWriter._is_connector_body("RJ45")
        assert CSAWriter._is_connector_body("CONNECTOR_2X5")
        assert CSAWriter._is_connector_body("USB3")
        assert CSAWriter._is_connector_body("DSUB9")
        assert CSAWriter._is_connector_body("J19")

    def test_schematic_elements_kept(self):
        """IOPORT/OFFPAGE/MARK 等图纸元素不能被 mock。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter
        for name in ("IOPORT", "OFFPAGE", "MARK", "TP", "BISHEET"):
            assert CSAWriter._is_schematic_element(name), name
        assert not CSAWriter._is_schematic_element("CH347")


class TestNoTextOverlap:
    """引脚名文本零碰撞（Phase XX 补丁 3，08-13 用户复测）。

    ①C 指令与 X PIN_TEXT 显示同一长名且同侧 → 156 组碰撞（U6B 实测）；
    ②X 指令 justify 字段错位（恒 0 左对齐）→ left 列长名侵入框内。
    修复：C=短引脚号（框内）、X=长功能名（框外，left/top justify=1
    右对齐向左延伸 / right/bottom justify=0）；列间距 ≥ 文本宽。
    """

    def test_c_short_number_and_x_long_name(self):
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary()
        sym = lib.symbol_for("U6B", 1, [("1", "DDR_ADDR14"), ("2", "DDR_CLK_N")])
        css = lib._symbol_css(sym)
        # C 指令文本 = 短引脚号（2pin → max_len=10 → 外列 ±650，Phase XXI
        # 字符宽 28）；C 短号贴 outline 边 x0+25（E 几何铁律，不落框外）。
        assert ' "1" -525 100' in css or ' "1" 525 100' in css
        assert 'X "PIN_TEXT" "DDR_ADDR14"' in css
        # X 文本必须朝引脚外侧（left justify=1 右对齐 / right justify=0），
        # 锚点 px±80（Phase XXI C：旧 px±50 与 C 号视觉靠近 → px±80）。
        assert 'X "PIN_TEXT" "DDR_ADDR14" -730 100 0 1' in css

    def test_no_text_overlap_all_tiers(self):
        """多档位引脚分布：同 y 文本互不覆盖。

        Phase XXI F（用户 P12/P13 复测 U6B/U6 引脚名仍重叠）：字符宽
        18→**28**（与布局公式同口径 —— 字号 29 真实渲染宽 ~24-28，旧值
        低估）。C 短号贴 outline 边（x0+25）、X 长名 px±80 框外延伸后，
        铁律 ``列距 ≥ max_len*28 + 255`` 保证 0 碰撞。
        """
        from collections import Counter
        from cis2hdl.core.writer.mock_icon_lib import distribute_mock_pin_offsets

        char_w = 28
        for n, names in [
            (8, ["VDD_PMU2_1P8"] * 8),
            (24, ["DDR_ADDR14", "VDD_COMMON15_1P2"] * 12),
            (84, ["VSS" + str(i) for i in range(84)]),
            (150, ["ABB_WL_ADDA_QN_2G_C0"] * 150),
        ]:
            offs = distribute_mock_pin_offsets(n, names)
            # 同**侧**（left x<0 / right x>0）同 y 的相邻列间距必须
            # ≥ 文本宽 + 100（X 长名在框外不互叠）。跨中心的左右内列
            # 之间是 body（C 短号区），不参与比较。
            max_len = max(map(len, names))
            for side in ("left", "right"):
                by_y: dict[int, list[int]] = {}
                for v in offs.values():
                    if (side == "left") != (v[0] < 0):
                        continue
                    by_y.setdefault(v[1], []).append(v[0])
                for y, xs in by_y.items():
                    xs = sorted(xs)
                    for a, b in zip(xs, xs[1:]):
                        assert b - a >= max_len * char_w + 100, (
                            f"n={n} side={side} y={y} 列间距 {b-a} "
                            f"< 文本宽+100")
