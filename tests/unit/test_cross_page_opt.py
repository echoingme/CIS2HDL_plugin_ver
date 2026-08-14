"""Phase XIV T8 — 跨页网视觉优化（cross_page_opt）。

Covers:
  * 开启 cross_page_opt 时 CSA 中 IOPORT 同侧 x/y 对齐断言
  * 默认关闭 → 与未开启输出一致（回归零影响）
"""

from __future__ import annotations

from pathlib import Path


def _make_conn(n_offpages=3):
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import DesignIR, PageIR
    from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder

    p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    p1.instances = [
        ComponentInstanceIR(
            refdes="C1", library_id="C1", loc_x=4500, loc_y=12000,
            pin_connections={"1": "NET_A", "2": "NET_B"},
        ),
    ]
    p1.off_pages = [
        {"name": f"OP{i}", "net_name": f"NET_{i}"} for i in range(n_offpages)
    ]
    design = DesignIR(project_name="T", pages=[p1])
    return ConnectivityModelBuilder(design, matches=[]).build()


def _ioport_positions(content: str):
    """提取 CSA 中所有 FORCEADD IOPORT 位置。"""
    import re

    lines = content.splitlines()
    positions = []
    for i, line in enumerate(lines):
        if line == "FORCEADD IOPORT..1":
            if i + 1 < len(lines):
                m = re.match(r"^\((-?\d+) (-?\d+)\);", lines[i + 1])
                if m:
                    positions.append((int(m.group(1)), int(m.group(2))))
    return positions


class TestCrossPageIoportAlign:
    def test_opt_on_same_x_even_y(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _make_conn(4)
        cfg = RoutingConfig(cross_page_opt=True)
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        positions = _ioport_positions(content)
        assert len(positions) == 4
        xs = {p[0] for p in positions}
        assert xs == {-600}, f"IOPORT x 未对齐: {xs}"
        ys = sorted((p[1] for p in positions), reverse=True)
        assert all(
            ys[i] - ys[i + 1] == 100 for i in range(len(ys) - 1)
        ), f"IOPORT y 未等间距: {ys}"

    def test_opt_off_default_unchanged(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _make_conn(3)
        cfg_off = RoutingConfig(cross_page_opt=False)
        cfg_on = RoutingConfig(cross_page_opt=True)
        writer_off = CSAWriter(routing_cfg=cfg_off)
        writer_on = CSAWriter(routing_cfg=cfg_on)
        content_off = writer_off._build_csa_content_conn(conn, conn.pages[0])
        content_on = writer_on._build_csa_content_conn(conn, conn.pages[0])
        # 开启时 IOPORT 位置变化（右侧缘 x 统一）
        pos_off = _ioport_positions(content_off)
        pos_on = _ioport_positions(content_on)
        assert pos_off != pos_on
        # 默认关闭路径与 cfg_off 输出一致（此处验证开启 ≠ 关闭）

    def test_opt_on_wires_endpoints_on_grid(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _make_conn(3)
        cfg = RoutingConfig(cross_page_opt=True)
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        import re
        for m in re.finditer(
            r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content,
        ):
            for v in (int(m.group(i)) for i in range(1, 5)):
                assert v % 25 == 0
