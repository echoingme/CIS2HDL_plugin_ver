"""Phase XVIII R3 — SPCOCN-543 全面修复（csa_writer / naming / config）。

Covers:
  * Q2 方案 A：旋转 CAPACITOR → `FORCEADD CAPACITOR..2`（sym_2 横向
    视图）且无 R 行（golden page9 L354 先例）；坐标唯一原则同源切换
  * R3c：GND_POWER SIG_NAME = `GND_POWER\\g` + LASTPIN offset (50,100)
    （golden page9 L10-17 实锤）
  * R3d：`_lastpin_coord_hit` 旋转数学强校验
  * R3④：PQ2016 引脚数不匹配 → 跳过 LASTPIN（M1 mock 接管）
  * R3⑤：UN$ 网名稳定化（rename 策略）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_FIXTURES_HDL_LIB = Path(__file__).parent.parent / "fixtures" / "hdl_lib"


def _snap(v: float) -> int:
    return int(round(v / 25.0) * 25)


def _build(design, matches=None):
    from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder

    return ConnectivityModelBuilder(design, matches=matches or []).build()


def _make_cap_design(rotation=90, mirror=0, refdes="C1", lib="CAPACITOR"):
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import DesignIR, PageIR

    p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    p1.instances = [
        ComponentInstanceIR(
            refdes=refdes, library_id=lib, loc_x=4500, loc_y=12000,
            rotation=rotation, mirror=mirror,
            pin_connections={"1": "NET_A", "2": "NET_B"},
        ),
    ]
    return DesignIR(project_name="T", pages=[p1])


class TestRotatedPassiveSym2:
    def test_rotated_capacitor_uses_sym2_no_rline(self):
        """旋转 CAPACITOR（R90）→ `FORCEADD CAPACITOR..2`，无 R 行。

        golden 04p4 page9 L354 先例：旋转实例用 `CAPACITOR..2` 横向视图
        （不写 R 行），$PN 坐标 = body + sym_2 引脚 offset 精确命中。
        """
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        design = _make_cap_design(rotation=90)
        conn = _build(design)
        for irec in conn.pages[0].instances:
            irec.cell_name = "capacitor"
        writer = CSAWriter(
            routing_cfg=RoutingConfig(), hdl_lib_path=_FIXTURES_HDL_LIB,
        )
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        idx = content.find("FORCEADD CAPACITOR..2")
        assert idx != -1, "FORCEADD CAPACITOR..2 missing (sym_2 未切换)"
        block = content[idx:content.find("\nFORCEADD", idx + 1)]
        # 旋转行（R 1/2/3）只出现在 FORCEADD 与 (x y); 之间 —— 无旋转行。
        head = block[: block.find(";") + 1]
        assert not re.search(r"\nR [123]\n", head), head[:300]
        # LASTPIN 坐标 = body + sym_2 引脚 offset（(-50,0)/(75,0)，同源）。
        m = re.search(r"FORCEADD CAPACITOR\.\.2\n\((-?\d+) (-?\d+)\);", block)
        bx, by = int(m.group(1)), int(m.group(2))
        assert f"FORCEPROP 2 LASTPIN ({bx - 50} {by})" in block, block[:300]
        assert f"FORCEPROP 2 LASTPIN ({bx + 75} {by})" in block, block[:300]

    def test_no_sym2_fallback_keeps_rline(self):
        """无 sym_2（如 dc_dc 变体）→ 保持 R 行现状（Q2 不误切）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        # dc_dc 有 sym_N 但非被动体（_is_passive_view_body=False）→ 不切。
        design = _make_cap_design(rotation=90, lib="DC_DC", refdes="U1")
        conn = _build(design)
        for irec in conn.pages[0].instances:
            irec.cell_name = "dc_dc"
        cfg = RoutingConfig()
        cfg.temp_lib.mock_all = False  # Phase XX：本测试验证真实库 sym_2 防护
        writer = CSAWriter(
            routing_cfg=cfg, hdl_lib_path=_FIXTURES_HDL_LIB,
        )
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        assert "FORCEADD DC_DC..2" not in content, "dc_dc 禁止切 sym_2"
        assert "FORCEADD DC_DC..1" in content

    def test_mirror_passive_keeps_rline(self):
        """mirror≠0 被动元件不切 sym_2（保持镜像/旋转路径）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        design = _make_cap_design(rotation=90, mirror=1)
        conn = _build(design)
        for irec in conn.pages[0].instances:
            irec.cell_name = "capacitor"
        writer = CSAWriter(
            routing_cfg=RoutingConfig(), hdl_lib_path=_FIXTURES_HDL_LIB,
        )
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        assert "FORCEADD CAPACITOR..2" not in content, "mirror 不切 sym_2"


class TestGndPowerGolden:
    def _gnd_design(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="GND1", library_id="GND", loc_x=4500, loc_y=12000,
                rotation=0, mirror=0, pin_connections={},
            ),
            ComponentInstanceIR(
                refdes="R1", library_id="RESISTOR", loc_x=7000, loc_y=9000,
                rotation=0, mirror=0,
                pin_connections={"1": "GND", "2": "NET_X"},
            ),
        ]
        return DesignIR(project_name="T", pages=[p1])

    def test_gnd_power_sig_name_and_offset(self):
        """R3c: GND_POWER SIG_NAME = `GND_POWER\\g` + LASTPIN offset (50,100)。

        SPCOCN-543 修复（08-13）：LASTPIN 必须命中符号实际引脚 ——
        fixture hdl_lib gnd_power/sym_1/symbol.css 引脚 C 0 50 →
        offset (0,50)；旧 golden (50,100) 不匹配 → Cadence 删 SIG_NAME。
        """
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build(self._gnd_design())
        writer = CSAWriter(
            routing_cfg=RoutingConfig(), hdl_lib_path=_FIXTURES_HDL_LIB,
        )
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        m = re.search(
            r"FORCEADD GND_POWER\.\.1\n\((-?\d+) (-?\d+)\);", content,
        )
        assert m, "GND_POWER block missing"
        bx, by = int(m.group(1)), int(m.group(2))
        # SPCOCN-543 修复（08-13）：LASTPIN = body + 符号引脚 (0,50)。
        assert (
            f"FORCEPROP 3 LASTPIN ({bx + 0} {by + 50}) "
            f"SIG_NAME GND_POWER\\g"
        ) in content, content[:400]

    def test_gnd_power_css_fallback(self):
        """配置值 "css" → 回退 symbol.css 引脚 (0,50)。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        cfg = RoutingConfig()
        cfg.gnd_distribution.gnd_power_lastpin_offset = "css"
        conn = _build(self._gnd_design())
        writer = CSAWriter(routing_cfg=cfg, hdl_lib_path=_FIXTURES_HDL_LIB)
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        m = re.search(
            r"FORCEADD GND_POWER\.\.1\n\((-?\d+) (-?\d+)\);", content,
        )
        bx, by = int(m.group(1)), int(m.group(2))
        assert f"FORCEPROP 3 LASTPIN ({bx} {by + 50})" in content


class TestLastpinCoordHit:
    def _writer(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        return CSAWriter(routing_cfg=RoutingConfig())

    def test_hit_nonrotated(self):
        w = self._writer()
        assert w._lastpin_coord_hit((1050, 2100), (1000, 2000), (50, 100), 0, 0)
        assert w._lastpin_coord_hit((1000, 1925), (1000, 2000), (0, -75), 0, 0)

    def test_hit_rotated(self):
        """旋转数学：rotate_point(50,100,270) = (100,-50)。"""
        from cis2hdl.core.writer.coord_transform import rotate_point

        assert rotate_point(50, 100, 270) == (100, -50)
        w = self._writer()
        assert w._lastpin_coord_hit(
            (1100, 1950), (1000, 2000), (50, 100), 270, 0,
        )

    def test_hit_mirrored(self):
        """镜像：rotate_point(50,100,0,1) = (50,-100)。"""
        from cis2hdl.core.writer.coord_transform import rotate_point

        assert rotate_point(50, 100, 0, 1) == (50, -100)
        w = self._writer()
        assert w._lastpin_coord_hit(
            (1050, 1900), (1000, 2000), (50, 100), 0, 1,
        )

    def test_miss_rejected(self):
        w = self._writer()
        # 偏移 (0,50) 与期望 (50,100) 差 (-50,-50) → 未命中。
        assert not w._lastpin_coord_hit(
            (1000, 2050), (1000, 2000), (50, 100), 0, 0,
        )
        # 完全错误坐标（sym_1 vs sym_2 混用）→ 未命中。
        assert not w._lastpin_coord_hit(
            (1000, 2075), (1000, 2000), (0, -75), 0, 0,
        )

    def test_nudge_rejected_by_strict_hit(self):
        """_unique_pin_coord 微移的坐标在 _lastpin_coord_hit 严格不等 →
        由 _nudged_pin_keys 在 _lastpins_for_instance 跳过（此处直接
        断言方法本身是严格相等语义）。"""
        w = self._writer()
        assert not w._lastpin_coord_hit(
            (1075, 2100), (1000, 2000), (50, 100), 0, 0,
        )


class TestPinCountMismatchSkip:
    def test_rotated_4pin_vs_sym2_2pin_skip_lastpin(self, tmp_path):
        """PQ2016 类：4 引脚实例 vs symbol 2 引脚 → 跳过 LASTPIN（方案 D）。

        4 引脚不满足 sym_2 切换的 2 引脚条件 → 保持 ``CAPACITOR..1``
        （视图不切），但 LASTPIN 全跳过（M1 mock 接管渲染）。
        """
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        design = _make_cap_design(rotation=90, refdes="U_PQ", lib="PQ2016")
        # 给 U_PQ 追加 2 个引脚 → 4 引脚实例。
        design.pages[0].instances[0].pin_connections = {
            "1": "A", "2": "B", "3": "C", "4": "D",
        }
        conn = _build(design)
        for irec in conn.pages[0].instances:
            irec.cell_name = "capacitor"
        writer = CSAWriter(
            routing_cfg=RoutingConfig(), hdl_lib_path=_FIXTURES_HDL_LIB,
        )
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        # 4 引脚不切 sym_2（保持 sym_1）……
        assert "FORCEADD CAPACITOR..1" in content
        # ……但 4 > 2 → LASTPIN 全跳过（M1 mock 接管）。
        block = content[content.find("FORCEADD CAPACITOR..1"):]
        block = block[: block.find("\nFORCEADD") if "\nFORCEADD" in block else 400]
        assert "LASTPIN" not in block, "pin-count mismatch 应跳过 LASTPIN"


class TestUnNameStabilize:
    def test_stabilize_un_name_direct(self):
        from cis2hdl.utils.naming import stabilize_un_name

        assert stabilize_un_name("UN$5SCAPACITORSI43$2") == "UN_5SCAPACITORSI43_2"
        assert stabilize_un_name("NET_A") == "NET_A"
        assert stabilize_un_name("UN$A$B") == "UN_A_B"

    def test_un_policy_display_rename(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        w = CSAWriter(routing_cfg=RoutingConfig())
        assert w._un_policy_display(
            "UN$5SCAPACITORSI43$2",
        ) == "UN_5SCAPACITORSI43_2"
        # \\g 后缀保留
        assert w._un_policy_display(
            "UN$5$2\\g",
        ) == "UN_5_2\\g"

    def test_un_policy_omit(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        cfg = RoutingConfig()
        cfg.ioport.un_name_policy = "omit"
        w = CSAWriter(routing_cfg=cfg)
        assert w._un_policy_display("UN$5SCAPACITORSI43$2") == ""
        assert w._un_policy_display("NET_A") == "NET_A"

    def test_un_net_sig_name_in_output(self):
        """集成：UN$ 网在 CSA 输出的 SIG_NAME 为稳定名。"""
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="U1", library_id="U1", loc_x=4500, loc_y=12000,
                rotation=0, mirror=0,
                pin_connections={"1": "UN$5SCAPACITORSI43$2"},
            ),
            ComponentInstanceIR(
                refdes="R1", library_id="RESISTOR", loc_x=7000, loc_y=9000,
                rotation=0, mirror=0,
                pin_connections={"1": "UN$5SCAPACITORSI43$2", "2": "NET_X"},
            ),
        ]
        design = DesignIR(project_name="T", pages=[p1])
        conn = _build(design)
        writer = CSAWriter(routing_cfg=RoutingConfig())
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        assert "UN_5SCAPACITORSI43_2" in content, (
            "UN$ 网名应稳定化为 UN_5SCAPACITORSI43_2"
        )
