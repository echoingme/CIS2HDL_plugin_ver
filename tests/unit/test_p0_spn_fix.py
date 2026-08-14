"""Phase XVII P0 — SPCOCN-543/542 修复 + GND 避让 + 标签随旋转回归。

Covers:
  * SIG_NAME LASTPIN 块无 PAINT MONO + DISPLAY INVISIBLE（方案 A）
  * 旋转实例 SIG_NAME 改放 WIRE（方案 C）
  * 引脚数不匹配实例跳过 LASTPIN（方案 D）
  * PLACEHOLDER 属性块无 PAINT/DISPLAY INVISIBLE（SPCOCN-542）
  * placeholder symbol.css 有 P "PLACEHOLDER" 声明
  * entity 目录（master.tag + pc.db）
  * GND 符号不落元件 outline 内
  * VALUE/$LOCATION 标签随旋转
"""

from __future__ import annotations

import re

import pytest


def _snap(v: float) -> int:
    return int(round(v / 25.0) * 25)


def _make_design():
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import DesignIR, PageIR

    p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    p1.instances = [
        ComponentInstanceIR(
            refdes="C1", library_id="C1", loc_x=4500, loc_y=12000,
            rotation=90,
            pin_connections={"1": "NET_A", "2": "NET_B"},
        ),
        ComponentInstanceIR(
            refdes="U1", library_id="U1", loc_x=6500, loc_y=9000,
            pin_connections={
                "1": "GND_POWER", "2": "GND_POWER", "3": "NET_A",
                "4": "NET_A", "5": "NET_B",
            },
        ),
    ]
    return DesignIR(project_name="HG5015-BE36_V10", pages=[p1])


def _build_conn(design=None, matches=None):
    from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder

    if design is None:
        design = _make_design()
    return ConnectivityModelBuilder(design, matches=matches or []).build()


class TestSigNamePaintRemoved:
    def test_sig_name_at_pin_matches_golden(self):
        """QA P1-1 复盘：04p4 golden page9.csa 的 SIG_NAME LASTPIN 块
        标准写法**带** ``PAINT MONO + DISPLAY INVISIBLE``（L12 GND_POWER /
        L365 CAPACITOR SIG_NAME）；无 PAINT 的是 $PN 块（L63-71）。
        SPCOCN-543 真实根因 = 坐标未命中（方案 B/C/D），与 PAINT 无关。
        """
        from cis2hdl.core.writer.csa_writer import CSAWriter

        lines = CSAWriter._sig_name_at_pin((100, 200), "NET_A")
        assert lines == [
            "FORCEPROP 2 LASTPIN (100 200) SIG_NAME NET_A",
            "J 0",
            "(110 210);",
            "DISPLAY 0.659574 (110 210);",
            "PAINT MONO (110 210);",
            "DISPLAY INVISIBLE (110 210);",
        ]
        # 与电源符号块（FORCEPROP 3）格式一致 —— 无需豁免。
        assert "PAINT MONO" in lines[-2]
        assert "DISPLAY INVISIBLE" in lines[-1]

    def test_power_symbol_block_has_paint_like_golden(self):
        """电源符号 LASTPIN SIG_NAME 带 PAINT（04p4 page9 L12 同款）。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter

        irec = type(
            "PowerIRec", (), {
                "power_nets": ["GND"], "is_power_symbol": True,
                "mirror": 0, "page_local_k": 1, "section": 1,
                "properties": {},
            },
        )()
        lines = CSAWriter()._emit_power_symbol_block(
            None, irec, "GND_POWER", -100, 200,
        )
        sig = [ln for ln in lines if "LASTPIN" in ln and "SIG_NAME" in ln]
        assert sig, "power symbol LASTPIN SIG_NAME missing"
        assert any("PAINT MONO" in ln for ln in lines)

    def test_pn_block_no_paint(self):
        """$PN 块无 PAINT（04p4 page9 L63-71 golden）。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter

        lines = CSAWriter._lastpin_pn((100, 200), "2")
        assert not any("PAINT" in ln for ln in lines)

    def test_csa_matches_golden_sig_name(self):
        """转换输出中 SIG_NAME LASTPIN 块与 04p4 golden 一致（带 PAINT）。"""
        conn = _build_conn()
        from cis2hdl.core.writer.csa_writer import CSAWriter

        content = CSAWriter()._build_csa_content_conn(conn, conn.pages[0])
        blocks = re.split(r"\n(?=FORCEPROP)", content)
        for block in blocks:
            if re.search(r"FORCEPROP [23] LASTPIN .* SIG_NAME", block):
                # golden 标准 6 行块：FORCEPROP / J 0 / (x y); / DISPLAY /
                # PAINT MONO / DISPLAY INVISIBLE。
                assert "PAINT MONO" in block, block[:120]
                assert "DISPLAY INVISIBLE" in block, block[:120]


class TestRotatedSigNameOnWire:
    def test_rotated_component_sig_name_on_wire(self):
        """旋转实例（C1 R90 → R 3）的 SIG_NAME 改放 WIRE，引脚只留 $PN。"""
        conn = _build_conn()
        from cis2hdl.core.writer.csa_writer import CSAWriter

        content = CSAWriter()._build_csa_content_conn(conn, conn.pages[0])
        idx = content.find("FORCEADD C1..1")
        nxt = content.find("\nFORCEADD", idx + 1)
        block = content[idx:nxt] if nxt != -1 else content[idx:]
        # R 行（DEHDL 270 → R 3）
        assert "R 3" in block
        # 引脚只留 $PN —— 无 LASTPIN 携带 SIG_NAME。
        assert not re.search(r"LASTPIN .* SIG_NAME", block), block[:300]
        assert re.search(r"LASTPIN .* \$PN \d+", block)
        # WIRE 节有独立 SIG_NAME（网络名仍在页内可见）
        assert "FORCEPROP 2 LAST SIG_NAME" in content


class TestPinCountMismatchSkip:
    def test_instance_pins_gt_symbol_pins_skip_lastpin(self, tmp_path):
        """实例引脚数 > symbol 引脚数 → 跳过 LASTPIN（方案 D）。

        构造一个 2 引脚 symbol.css 但 4 引脚实例，验证不发射 LASTPIN。
        """
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        lib = tmp_path / "hdl_lib"
        cell = lib / "RF_SW" / "sym_1"
        cell.mkdir(parents=True)
        (cell / "symbol.css").write_text(
            'P "CDS_LMAN_SYM_OUTLINE" "-150,150,150,-150" 0 0 0 0 22 0 0 0 0 0 0 0 0\n'
            'L -140 150 -150 150 -1 0\n'
            'C -150 150 "1" -175 150 0 0 32 1 R\n'
            'C 150 -150 "2" 175 -150 0 0 32 1 L\n',
            encoding="utf-8",
        )
        p1 = type("PageIR", (), {})()
        p1.page_id = "1.1"
        p1.page_name = "P1"
        p1.instances = []
        design = _make_design()
        conn = _build_conn(design)
        # 直接替换 body 名让 _get_css_pin_offsets 命中 2 引脚 symbol。
        writer = CSAWriter(routing_cfg=RoutingConfig(), hdl_lib_path=lib)
        for page in conn.pages:
            for irec in page.instances:
                if irec.refdes == "U1":
                    irec.cell_name = "RF_SW"
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        idx = content.find("FORCEADD RF_SW..1")
        block = content[idx:idx + 600] if idx != -1 else ""
        # 4 实例引脚 > 2 symbol 引脚 → 跳过 LASTPIN。
        assert "LASTPIN" not in block


class TestPlaceholderProperty:
    def test_css_declares_placeholder(self):
        from cis2hdl.core.writer.placeholder_lib import PlaceholderLibrary

        lib = PlaceholderLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "A1")])
        css = lib._symbol_css(sym)
        assert 'P "PLACEHOLDER"' in css

    def test_placeholder_block_no_paint(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        cfg = RoutingConfig()
        cfg.temp_lib.enabled = False  # 回退 placeholder
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        idx = content.find("PLACEHOLDER 1")
        assert idx != -1
        block = content[idx:idx + 120]
        assert "PAINT" not in block
        assert "INVISIBLE" not in block
        assert "R 1" in block

    def test_entity_dir_written(self, tmp_path):
        from cis2hdl.core.writer.placeholder_lib import PlaceholderLibrary

        lib = PlaceholderLibrary()
        lib.symbol_for("U6", 1, [("K18", "A0")])
        lib.write_to_hdl_lib(tmp_path)
        entity = tmp_path / "u6_ph" / "entity"
        assert (entity / "master.tag").exists()
        assert (entity / "pc.db").exists()


class TestGndAvoidsOutline:
    def test_gnd_symbol_not_on_chip(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        cfg = RoutingConfig()
        cfg.gnd_distribution.enabled = True
        cfg.temp_lib.enabled = False
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        # 找到 GND_POWER body 与 U1 body，断言不重叠。
        m_u1 = re.search(r"FORCEADD U1_PH\.\.1\n\((-?\d+) (-?\d+)\);", content)
        assert m_u1
        ux, uy = int(m_u1.group(1)), int(m_u1.group(2))
        u_outline = (-150, -150, 150, 150)
        gnd_bodies = re.findall(
            r"FORCEADD GND_POWER\.\.1\n\((-?\d+) (-?\d+)\);", content,
        )
        assert gnd_bodies
        for gx, gy in ((int(x), int(y)) for x, y in gnd_bodies):
            # GND body rect (-50,-50,50,0) 与 U1 outline 不交。
            gx0, gy0, gx1, gy1 = gx - 50, gy - 50, gx + 50, gy
            ox0, oy0, ox1, oy1 = (
                ux + u_outline[0], uy + u_outline[1],
                ux + u_outline[2], uy + u_outline[3],
            )
            overlap = not (
                gx0 >= ox1 or gx1 <= ox0 or gy0 >= oy1 or gy1 <= oy0
            )
            assert not overlap, (
                f"GND body ({gx0},{gy0},{gx1},{gy1}) overlaps U1 "
                f"({ox0},{oy0},{ox1},{oy1})"
            )


class TestLabelsRotate:
    def test_value_location_follow_rotation(self):
        """旋转实例的 VALUE/$LOCATION 标签坐标 = rotate_point 结果。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter, _dehdl_rotation
        from cis2hdl.core.writer.coord_transform import rotate_point

        conn = _build_conn()
        content = CSAWriter()._build_csa_content_conn(conn, conn.pages[0])
        # C1 R90 → DEHDL 270：VALUE 基准 (-5,-50) → rotate 270 → (-50, 5)？
        rot_dehdl = _dehdl_rotation(90)
        vbase = rotate_point(-5, -50, rot_dehdl)
        idx = content.find("FORCEADD C1..1")
        nxt = content.find("\nFORCEADD", idx + 1)
        block = content[idx:nxt] if nxt != -1 else content[idx:]
        m = re.search(r"FORCEPROP 1 LAST VALUE \S+\nR 1\nJ 1\n\((-?\d+) (-?\d+)\);", block)
        assert m, f"VALUE block not found: {block[:400]}"
        m_body = re.search(r"R 3\n\((-?\d+) (-?\d+)\);", block)
        assert m_body
        bx, by = int(m_body.group(1)), int(m_body.group(2))
        vx, vy = int(m.group(1)), int(m.group(2))
        assert (vx - bx, vy - by) == vbase, (
            f"VALUE offset ({vx - bx},{vy - by}) != rotate_point {vbase}"
        )


class TestMockCdsLib:
    """QA P1-2 回归：mock 模拟图标 CDS_LIB 指向 temp_lib（Cadence 可达）。"""

    def test_mock_instance_cds_lib_is_temp_lib(self):
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()  # U1 无具体符号 → mock 图标（temp_lib.enabled 默认 true）
        content = CSAWriter()._build_csa_content_conn(conn, conn.pages[0])
        idx = content.find("FORCEADD U1_PH..1")
        nxt = content.find("\nFORCEADD", idx + 1)
        block = content[idx:nxt] if nxt != -1 else content[idx:]
        assert "CDS_LIB temp_lib" in block, block[:400]

    def test_placeholder_instance_cds_lib_is_hdl_lib(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        cfg = RoutingConfig()
        cfg.temp_lib.enabled = False  # 回退 placeholder → hdl_lib
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        idx = content.find("FORCEADD U1_PH..1")
        nxt = content.find("\nFORCEADD", idx + 1)
        block = content[idx:nxt] if nxt != -1 else content[idx:]
        assert "CDS_LIB hdl_lib" in block, block[:400]

    def test_cdslib_defines_temp_lib(self, tmp_path):
        from cis2hdl.core.writer.output_manager import OutputManager

        mgr = OutputManager(project_name="T", output_root=tmp_path)
        mgr.setup_directory_structure()
        cdslib = mgr.write_cdslib()
        text = cdslib.read_text(encoding="utf-8")
        assert "DEFINE temp_lib temp_lib" in text


class TestLoadFromFileTopSections:
    """QA P2-1 回归：routing.yaml 顶层子节（ioport 等）可经 load_from_file
    生效 —— use_net_name 无 CLI 旗标也能用 yaml 启用。"""

    @pytest.fixture(autouse=True)
    def _restore_global_config(self):
        """保存/恢复全局 config 单例 —— 防止 load_from_file 污染后续测试。"""
        from cis2hdl.core.config import config as _cfg

        saved = _cfg.routing
        yield
        _cfg.routing = saved

    def test_top_level_ioport_use_net_name(self, tmp_path):
        from cis2hdl.core.config import Config

        p = tmp_path / "routing.yaml"
        p.write_text(
            'version: "1.0"\n'
            "ioport:\n"
            "  use_net_name: true\n",
            encoding="utf-8",
        )
        cfg = Config.get()
        cfg.reset()
        cfg.load_from_file(p)
        assert cfg.routing.ioport.use_net_name is True

    def test_top_level_temp_lib_and_wire_simplify(self, tmp_path):
        from cis2hdl.core.config import Config

        p = tmp_path / "routing.yaml"
        p.write_text(
            'version: "1.0"\n'
            "temp_lib:\n"
            "  enabled: false\n"
            "wire_simplify:\n"
            "  enabled: true\n"
            "  dot_merge: 75\n",
            encoding="utf-8",
        )
        cfg = Config.get()
        cfg.reset()
        cfg.load_from_file(p)
        assert cfg.routing.temp_lib.enabled is False
        assert cfg.routing.wire_simplify.enabled is True
        assert cfg.routing.wire_simplify.dot_merge == 75

    def test_nested_routing_section_still_works(self, tmp_path):
        from cis2hdl.core.config import Config

        p = tmp_path / "routing.yaml"
        p.write_text(
            'version: "1.0"\n'
            "routing:\n"
            "  mode: detour\n"
            "  ioport:\n"
            "    use_net_name: true\n",
            encoding="utf-8",
        )
        cfg = Config.get()
        cfg.reset()
        cfg.load_from_file(p)
        assert cfg.routing.mode == "detour"
        assert cfg.routing.ioport.use_net_name is True
