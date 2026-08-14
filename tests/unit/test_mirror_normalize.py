"""Phase XVI T1 — 镜像归一化（system_design0811-phase16.md D.3）。

Covers:
  * MX 双引脚无源件：引脚坐标 = css 偏移镜像（EDIF 真值）+ R 行 `R 2`
    + WIRE 端点与 LASTPIN 精确重合
  * MYR90/MXR90 合成元件：坐标 = 镜像真值 + R 行近似、aesthetic_report
    [MIRROR] 记录 approx 标注
  * mirror.normalize=false → 输出与 Phase XIII 一致（回归开关）
  * 电源符号镜像：GND 引脚偏移仅镜像、不记 R 行
"""

from __future__ import annotations

import re

from cis2hdl.core.writer.aesthetic_report import AestheticReport
from cis2hdl.core.writer.coord_transform import CoordTransform
from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
from cis2hdl.core.writer.csa_writer import CSAWriter


def _mirror_design(refdes="L20", library_id="INDUCTOR",
                   rotation=0, mirror=1, extra=None,
                   pin_connections=None):
    """Synthetic single-instance design carrying rotation/mirror."""
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import DesignIR, PageIR

    p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    insts = [
        ComponentInstanceIR(
            refdes=refdes, library_id=library_id, loc_x=4500, loc_y=12000,
            rotation=rotation, mirror=mirror,
            pin_connections=pin_connections or {"1": "NET_A", "2": "NET_B"},
        ),
    ]
    if extra:
        insts.extend(extra)
    p1.instances = insts
    return DesignIR(project_name="T", pages=[p1])


def _build(design):
    return ConnectivityModelBuilder(design, matches=[]).build()


def _pin_geometry(w, conn, page_conn):
    body_coords = CoordTransform.map_page_instances(page_conn.instances)
    pin_coords, pin_name_map, net_pin_map = w._compute_pin_geometry(
        conn, page_conn, body_coords,
    )
    return body_coords, pin_coords, net_pin_map


def _wire_endpoints(routed_nets):
    endpoints = set()
    for routed in routed_nets.values():
        for wire in getattr(routed, "wires", []) or []:
            endpoints.add((wire.x1, wire.y1))
            endpoints.add((wire.x2, wire.y2))
    return endpoints


class TestMirrorNormalize:
    def test_mx_passive_pin_coords_mirrored(self):
        """MX 双引脚无源件：引脚坐标 = css 偏移镜像真值 (0,75)/(0,-50)。"""
        design = _mirror_design(refdes="L20", library_id="INDUCTOR",
                                rotation=0, mirror=1)
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        body_coords, pin_coords, _ = _pin_geometry(w, conn, page_conn)
        bx, by = body_coords["L20"]
        # 原 css 偏移 (0,-75)/(0,50) 经 MX（flip Y）→ (0,75)/(0,-50)
        assert pin_coords["L20.1"] == (bx, by + 75), pin_coords
        assert pin_coords["L20.2"] == (bx, by - 50), pin_coords

    def test_mx_rline_and_endpoint_coincidence(self):
        """MX → R 行 `R 2`，且 LASTPIN ∈ WIRE 端点（连接重合硬约束）。"""
        from cis2hdl.core.ir.component import ComponentInstanceIR
        design = _mirror_design(
            refdes="L20", library_id="INDUCTOR", rotation=0, mirror=1,
            extra=[
                ComponentInstanceIR(
                    refdes="R1", library_id="RESISTOR", loc_x=7000, loc_y=9000,
                    rotation=0, mirror=0,
                    pin_connections={"1": "NET_A", "2": "NET_B"},
                ),
            ],
        )
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        content = w._build_csa_content_conn(conn, page_conn)
        idx = content.find("FORCEADD INDUCTOR..1")
        assert idx != -1
        block = content[idx:idx + 120]
        assert "R 2" in block, f"MX should emit R 2:\n{block}"
        # LASTPIN 坐标 = body + 镜像偏移，且都是 WIRE 端点
        body_coords, pin_coords, net_pin_map = _pin_geometry(w, conn, page_conn)
        routed = w._route_nets(net_pin_map, [], conn, page_conn)
        endpoints = _wire_endpoints(routed)
        assert len(routed) >= 2  # NET_A/NET_B 各 ≥2 引脚 → 已布线
        for key, coord in pin_coords.items():
            assert coord in endpoints, (
                f"{key} pin {coord} not a wire endpoint"
            )

    def test_myr90_ic_truth_and_approx_rline(self):
        """MYR90 合成 IC：坐标 = EDIF 真值（镜像在前、旋转在后）+ R 行近似。

        4 引脚 2×2 对称布局下 ``closest_rotation_for_mirror`` 由数据决定
        （θ*=0），验证 R 行 == ``_dehdl_rotation(θ*)`` 且 approx=True。
        """
        from cis2hdl.core.writer.coord_transform import closest_rotation_for_mirror, rotate_point
        design = _mirror_design(
            refdes="U1", library_id="IC_4PIN", rotation=90, mirror=2,
            pin_connections={"1": "NET_A", "2": "NET_B",
                             "3": "NET_C", "4": "NET_D"},
        )
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        body_coords, pin_coords, _ = _pin_geometry(w, conn, page_conn)
        bx, by = body_coords["U1"]
        irec = page_conn.instances[0]
        # Phase XX：mock_all=true 时 IC 走 mock symbol —— _resolve_pin_offset
        # 必须传真实 placeholder（mock 几何），与 _pin_geometry 一致
        # （旧实现传 None → fallback ±150 几何 vs mock 新几何 ±200 → 不一致）。
        body_name = irec.cell_name or "IC_4PIN"
        placeholder = w._placeholder_for_irec(irec, body_name, irec.section)
        fallback = w._fallback_pin_offsets(irec.cell_name, irec.section,
                                           len(irec.pins))
        offsets_list = []
        for pin_idx, pre in enumerate(irec.pins):
            off = w._resolve_pin_offset(
                irec, body_name, irec.section, placeholder, {}, fallback,
                pre, pin_idx,
            )
            offsets_list.append(off)
            mx, my = rotate_point(off[0], off[1], 90, 2)
            # 电气硬约束：坐标 == body + EDIF 真值
            assert pin_coords[f"U1.{pre.pin_number}"] == (bx + mx, by + my), (
                f"U1.{pre.pin_number}: {pin_coords[f'U1.{pre.pin_number}']} "
                f"!= body+({mx},{my})"
            )
        # R 行 == _dehdl_rotation(closest_rotation_for_mirror(...))
        from cis2hdl.core.writer.csa_writer import _dehdl_rotation
        theta = closest_rotation_for_mirror(offsets_list, 90, 2)
        expected_rline = _dehdl_rotation(theta)
        content = w._build_csa_content_conn(conn, page_conn)
        # Phase XX：mock_all=true → U1 走 mock（U1_PH），FORCEADD 用占位 cell
        idx = content.find("FORCEADD U1_PH..1")
        assert idx >= 0, "U1 应 mock 为 U1_PH"
        block = content[idx:idx + 120]
        if expected_rline == 0:
            assert not re.search(r"\nR [123]\n", block), block[:120]
        else:
            rn = {90: "R 1", 180: "R 2", 270: "R 3"}[expected_rline]
            assert rn in block, f"expected {rn}:\n{block[:120]}"
        # 方向近似标注
        assert w._mirror_rline["U1"] == expected_rline
        assert w._mirror_is_approx(offsets_list, 90, 2, theta) is True

    def test_myr90_vertical_passive_r3(self):
        """竖直双引脚 MYR90 → θ*=90 → DEHDL R 3（精确）。"""
        design = _mirror_design(refdes="C1", library_id="CAPACITOR",
                                rotation=90, mirror=2)
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        content = w._build_csa_content_conn(conn, page_conn)
        idx = content.find("FORCEADD CAPACITOR..1")
        block = content[idx:idx + 120]
        assert "R 3" in block, f"MYR90 vertical passive should emit R 3:\n{block}"

    def test_mxr90_rline(self):
        """MXR90 → R 行 `R 1`（θ*=270 → DEHDL 90）。"""
        design = _mirror_design(refdes="C1", library_id="CAPACITOR",
                                rotation=90, mirror=1)
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        content = w._build_csa_content_conn(conn, page_conn)
        idx = content.find("FORCEADD CAPACITOR..1")
        block = content[idx:idx + 120]
        assert "R 1" in block, f"MXR90 should emit R 1:\n{block}"

    def test_mirror_rline_comes_from_pass1_state(self):
        """Pass 2 R 行从 _mirror_rline 读取（state 传递）。"""
        design = _mirror_design(refdes="L20", library_id="INDUCTOR",
                                rotation=0, mirror=1)
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        w._build_csa_content_conn(conn, page_conn)
        assert w._mirror_rline["L20"] == 180  # MX → θ*=180 → DEHDL 180

    def test_aesthetic_report_mirror_section(self):
        """aesthetic_report [MIRROR] 节：MX 无源件 exact、MYR90 IC approx。"""
        from cis2hdl.core.ir.component import ComponentInstanceIR
        design = _mirror_design(
            refdes="L20", library_id="INDUCTOR", rotation=0, mirror=1,
            extra=[
                ComponentInstanceIR(
                    refdes="U1", library_id="IC_4PIN", loc_x=7000, loc_y=9000,
                    rotation=90, mirror=2,
                    pin_connections={"1": "NET_C", "2": "NET_D",
                                     "3": "NET_E", "4": "NET_F"},
                ),
            ],
        )
        conn = _build(design)
        page_conn = conn.pages[0]
        report = AestheticReport(enabled=True)
        w = CSAWriter(aesthetic_report=report)
        w._build_csa_content_conn(conn, page_conn)
        assert len(report.mirrors) == 2
        by_refdes = {m.refdes: m for m in report.mirrors}
        assert by_refdes["L20"].orient == "MX"
        assert by_refdes["L20"].rline == 180
        assert by_refdes["L20"].approx is False
        assert by_refdes["U1"].orient == "MYR90"
        # U1 的 R 行 = _dehdl_rotation(closest_rotation_for_mirror(...))
        from cis2hdl.core.writer.coord_transform import closest_rotation_for_mirror
        from cis2hdl.core.writer.csa_writer import _dehdl_rotation
        irec = page_conn.instances[1]
        # Phase XX 补丁2：mock_all → U1 用 mock 几何（对称 4pin），与
        # _pin_geometry 一致（传真实 placeholder，勿用 fallback）。
        body_name = irec.cell_name or "IC_4PIN"
        placeholder = w._placeholder_for_irec(irec, body_name, irec.section)
        fallback = w._fallback_pin_offsets(irec.cell_name, irec.section,
                                           len(irec.pins))
        offsets_list = [
            w._resolve_pin_offset(
                irec, body_name, irec.section, placeholder, {}, fallback,
                pre, pin_idx,
            )
            for pin_idx, pre in enumerate(irec.pins)
        ]
        expected_rline = _dehdl_rotation(
            closest_rotation_for_mirror(offsets_list, 90, 2)
        )
        assert by_refdes["U1"].rline == expected_rline
        assert by_refdes["U1"].approx is True
        # write() 输出 [MIRROR] 节
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            report.project_name = "T"
            path = report.write(Path(td))
            text = path.read_text(encoding="utf-8")
            assert "[MIRROR] total=2" in text
            assert "exact=1 approx=1" in text
            assert "方向近似（镜像无法用纯旋转表达），需人工复核" in text

    def test_no_mirror_normalize_matches_phase_xiii(self):
        """mirror.normalize=false → Phase XIII 行为（镜像忽略仅旋转）。"""
        from cis2hdl.core.config import RoutingConfig
        design = _mirror_design(refdes="L20", library_id="INDUCTOR",
                                rotation=0, mirror=1)
        conn = _build(design)
        page_conn = conn.pages[0]
        cfg = RoutingConfig()
        cfg.mirror.normalize = False
        w = CSAWriter(routing_cfg=cfg)
        body_coords, pin_coords, _ = _pin_geometry(w, conn, page_conn)
        bx, by = body_coords["L20"]
        # 未镜像：偏移保持 (0,-75)/(0,50)
        assert pin_coords["L20.1"] == (bx, by - 75), pin_coords
        assert pin_coords["L20.2"] == (bx, by + 50), pin_coords
        content = w._build_csa_content_conn(conn, page_conn)
        idx = content.find("FORCEADD INDUCTOR..1")
        block = content[idx:idx + 120]
        assert "R 2" not in block, "normalize=false 不应输出镜像 R 行"
        assert w._mirror_rline == {}, "normalize=false 不应记录 _mirror_rline"

    def test_no_mirror_normalize_mirror_with_rotation(self):
        """normalize=false + MYR90 → 仅旋转（DEHDL 270 路径，Phase XIII）。"""
        from cis2hdl.core.config import RoutingConfig
        design = _mirror_design(refdes="C1", library_id="CAPACITOR",
                                rotation=90, mirror=2)
        conn = _build(design)
        page_conn = conn.pages[0]
        cfg = RoutingConfig()
        cfg.mirror.normalize = False
        w = CSAWriter(routing_cfg=cfg)
        content = w._build_csa_content_conn(conn, page_conn)
        idx = content.find("FORCEADD CAPACITOR..1")
        block = content[idx:idx + 120]
        # Phase XIII: mirror 忽略，rotation 90 → DEHDL 270 → R 3
        assert "R 3" in block, f"Phase XIII MYR90 should emit R 3:\n{block}"


class TestMirrorPowerSymbol:
    def _gnd_design(self, mirror=1):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="GND1", library_id="GND", loc_x=4500, loc_y=12000,
                rotation=0, mirror=mirror,
                pin_connections={},
            ),
        ]
        return DesignIR(project_name="T", pages=[p1])

    def test_power_symbol_mirror_only_no_rline(self):
        """GND 电源符号 mirror≠0：引脚偏移仅镜像（不旋转）、无 R 行、
        不记 _mirror_rline。"""
        from cis2hdl.core.config import RoutingConfig
        design = self._gnd_design(mirror=1)
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        body_coords, pin_coords, _ = _pin_geometry(w, conn, page_conn)
        bx, by = body_coords["GND1"]
        # SPCOCN-543 修复（08-13）：plumbing 电源符号**忽略 mirror**
        # （Cadence 不镜像 plumbing、图形对称）→ 偏移恒 (0,50)。
        assert pin_coords["GND1.1"] == (bx, by + 50), pin_coords
        assert w._mirror_rline == {}, "电源符号不记 _mirror_rline"
        content = w._build_csa_content_conn(conn, page_conn)
        idx = content.find("FORCEADD GND_POWER..1")
        block = content[idx:idx + 200]
        assert not re.search(r"\nR [123]\n", block), (
            f"电源符号不应输出 R 行:\n{block[:200]}"
        )

    def test_power_symbol_block_lastpin_mirrored_offset(self):
        """主理人修复回归点：电源符号 FORCEADD 块 LASTPIN == body+镜像偏移。

        Phase XVI A.5 末：Pass 1 的 WIRE 端点源已镜像；若 _emit_power_symbol_block
        仍硬编码 y±50，则 LASTPIN 落在未镜像位置（GND MX 会输出 body+(0,+50) 而非
        body+(0,-50)）。注意仅断言"LASTPIN ∈ WIRE 端点"不足以捕获此回归——未镜像
        位置恰是 trunk 端点，故必须断言精确镜像坐标。
        """
        from cis2hdl.core.ir.component import ComponentInstanceIR
        design = self._gnd_design(mirror=1)
        # 加入同网元件引脚 → GND 网 2 引脚可布线（产生 WIRE 端点为真值源）
        design.pages[0].instances.append(ComponentInstanceIR(
            refdes="R1", library_id="RESISTOR", loc_x=7000, loc_y=9000,
            rotation=0, mirror=0,
            pin_connections={"1": "GND", "2": "NET_X"},
        ))
        conn = _build(design)
        page_conn = conn.pages[0]
        w = CSAWriter()
        content = w._build_csa_content_conn(conn, page_conn)
        idx = content.find("FORCEADD GND_POWER..1")
        assert idx != -1, "GND_POWER block missing"
        block = content[idx:idx + 200]
        m = re.search(
            r"FORCEPROP 3 LASTPIN \((-?\d+) (-?\d+)\) SIG_NAME", block,
        )
        assert m, f"GND_POWER LASTPIN SIG_NAME missing:\n{block[:200]}"
        body_coords, _, _ = _pin_geometry(w, conn, page_conn)
        bx, by = body_coords["GND1"]
        # SPCOCN-543 修复（08-13）：plumbing 电源符号忽略 mirror →
        # LASTPIN 恒为 body+(0,50)（命中符号实际引脚 C 0 50）。
        assert (int(m.group(1)), int(m.group(2))) == (bx, by + 50), (
            f"LASTPIN 未命中符号引脚（应为 body+(0,50)）:\n{block[:200]}"
        )
        # 且该 LASTPIN 必须是页内某 WIRE 端点（DEHDL 连接重合硬约束）
        endpoints = set()
        for wl in re.findall(
            r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content,
        ):
            endpoints.add((int(wl[0]), int(wl[1])))
            endpoints.add((int(wl[2]), int(wl[3])))
        assert (int(m.group(1)), int(m.group(2))) in endpoints, (
            f"LASTPIN 不是 WIRE 端点:\n{block[:200]}"
        )
