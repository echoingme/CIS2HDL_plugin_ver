"""Phase XIV T7/T8 — 额外 HDL 库挂载 + 跨页 IOPORT 对齐。

Covers:
  * --extra-hdl-lib 挂载 practice 目录 → ComponentDB 能扫到 dc_dc/ldo
  * power_ic.yaml 结构完整性
  * cross_page_opt 开启时 IOPORT 右侧缘 x 统一、y 等间距
"""

from __future__ import annotations

from pathlib import Path

PRACTICE_LIB = Path(__file__).resolve().parents[2] / (
    "docs_for_reference/previous_switch_programme/switch_practice/practice/hdl_lib"
)
FIXTURES_LIB = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "hdl_lib"


class TestExtraHdlLib:
    def test_scan_dcdc_in_fixtures(self):
        from cis2hdl.core.parser.hdl_scanner import HDLLibScanner

        scanner = HDLLibScanner()
        db = scanner.scan(FIXTURES_LIB)
        assert db.get_by_library_id("dc_dc") is not None
        assert db.get_by_library_id("ldo") is not None
        assert db.get_by_library_id("power_dip4") is not None

    def test_scan_practice_lib_if_present(self):
        from cis2hdl.core.parser.hdl_scanner import HDLLibScanner

        if not PRACTICE_LIB.exists():
            return
        scanner = HDLLibScanner()
        db = scanner.scan(PRACTICE_LIB)
        assert db.get_by_library_id("dc_dc") is not None

    def test_engine_scan_merges_extra(self):
        from cis2hdl.core.engine.conversion_engine import ConversionEngine
        from cis2hdl.core.config import Config

        cfg = Config()
        engine = ConversionEngine()
        report = __import__(
            "cis2hdl.core.engine.conversion_engine",
            fromlist=["ConversionReport"],
        ).ConversionReport()
        # 主库扫描 + extra 挂载 practice → dc_dc 仍在（合并）
        db = engine._stage_scan(FIXTURES_LIB, report, None,
                                extra_lib_paths=[PRACTICE_LIB])
        assert db.get_by_library_id("dc_dc") is not None


class TestPowerIcConfig:
    def test_config_structure(self):
        import yaml

        path = Path(__file__).resolve().parents[2] / "cis2hdl" / "config" / "power_ic.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["enabled"] is False  # 默认关
        assert "candidates_by_pin_count" in data
        assert 6 in {int(k) for k in data["candidates_by_pin_count"]}
        assert "scoring" in data
        assert "power_net_patterns" in data
        assert "pin_name_aliases" in data


class TestCrossPageOpt:
    def _make_conn(self, n_offpages=3):
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

    def test_ioport_right_edge_aligned(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = self._make_conn(4)
        cfg = RoutingConfig(cross_page_opt=True)
        writer = CSAWriter(routing_cfg=cfg)
        # IOPORT 位置：x 统一 -600，y 等间距 100
        positions = [writer._ioport_position_cfg(i) for i in range(4)]
        xs = {p[0] for p in positions}
        assert xs == {-600}
        ys = [p[1] for p in positions]
        assert ys == sorted(ys, reverse=True)
        assert all(
            ys[i] - ys[i + 1] == 100 for i in range(len(ys) - 1)
        ), f"not evenly spaced: {ys}"

    def test_default_ioport_position_unchanged(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = self._make_conn(4)
        cfg = RoutingConfig(cross_page_opt=False)  # 默认关
        writer = CSAWriter(routing_cfg=cfg)
        assert writer._ioport_position_cfg(0) == writer._ioport_position(0)
        assert writer._ioport_position_cfg(9) == writer._ioport_position(9)

    def test_ioport_pin_on_grid(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = self._make_conn(4)
        cfg = RoutingConfig(cross_page_opt=True)
        writer = CSAWriter(routing_cfg=cfg)
        for i in range(4):
            x, y = writer._ioport_pin_coord(i)
            assert x % 25 == 0 and y % 25 == 0
