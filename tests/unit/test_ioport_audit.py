"""Phase XVI T2 — IOPORT 一致性核对（system_design0811-phase16.md D.3）。

Covers:
  * audit_page 接线核对：仅 IOPORT 单引脚网豁免 / 已布线通过 / 未达端点 → unwired
  * 网名一致性：WPS vs wps 同 canonical → name_conflicts 且不自动合并
  * 孤立 connector：IOPORT 网名全工程无引脚 → orphan；skip_orphan 不生成
  * manual_names 覆盖：IOPORT 名 → 页网解析层覆盖后接线通过
  * 报告文件格式三节 + 统计；开关关闭 write 返回 None
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder, PageConnectivity
from cis2hdl.core.writer.csa_writer import CSAWriter
from cis2hdl.core.writer.coord_transform import CoordTransform
from cis2hdl.core.writer.ioport_audit import (
    IOPortAuditor,
    NameConflict,
    OrphanIoport,
    UnwiredIoport,
    canonical_name,
)


def _wire(x1, y1, x2, y2):
    return SimpleNamespace(x1=x1, y1=y1, x2=x2, y2=y2)


def _routed(name, wires):
    return {name: SimpleNamespace(wires=wires)}


def _page(nets_display, net_by_bare, off_pages):
    pc = PageConnectivity(page_num=1, page_name="05-Power_Supply1",
                          off_pages=off_pages)
    pc.nets = [SimpleNamespace(display_name=d) for d in nets_display]
    pc.net_by_bare = {
        bare: SimpleNamespace(display_name=d) for bare, d in net_by_bare.items()
    }
    return pc


class TestAuditPageWiring:
    def test_exempt_name_only_and_pass_and_unwired(self):
        """网 A 仅 IOPORT → 豁免；网 B 已布线 → 通过；网 C 未达端点 → unwired。"""
        page_conn = _page(
            nets_display=["NET_B", "NET_C"],
            net_by_bare={"net_a": "NET_A", "net_b": "NET_B", "net_c": "NET_C"},
            off_pages=[
                {"name": "OP_A", "net_name": "NET_A"},
                {"name": "OP_B", "net_name": "NET_B"},
                {"name": "OP_C", "net_name": "NET_C"},
            ],
        )
        net_pin_map = {
            "NET_A": [{"refdes": "IOPORT_0", "pin": "A", "coord": (100, 100)}],
            "NET_B": [
                {"refdes": "R1", "pin": "1", "coord": (200, 200)},
                {"refdes": "IOPORT_1", "pin": "A", "coord": (300, 200)},
            ],
            "NET_C": [
                {"refdes": "R2", "pin": "1", "coord": (400, 400)},
                {"refdes": "IOPORT_2", "pin": "A", "coord": (500, 500)},
            ],
        }
        routed_nets = _routed("NET_B", [_wire(200, 200, 300, 200)])
        auditor = IOPortAuditor()
        auditor.audit_page(page_conn, net_pin_map, routed_nets)
        assert auditor._exempt_name_only == 1
        assert len(auditor._unwired) == 1
        assert auditor._unwired[0].net == "NET_C"
        assert auditor._unwired[0].coord == (500, 500)
        assert auditor._unwired[0].pins_on_page == 1
        assert auditor._ioport_total == 3

    def test_all_wired_no_unwired(self):
        page_conn = _page(
            nets_display=["NET_B"],
            net_by_bare={"net_b": "NET_B"},
            off_pages=[{"name": "OP_B", "net_name": "NET_B"}],
        )
        net_pin_map = {
            "NET_B": [
                {"refdes": "R1", "pin": "1", "coord": (200, 200)},
                {"refdes": "IOPORT_0", "pin": "A", "coord": (300, 200)},
            ],
        }
        routed_nets = _routed("NET_B", [_wire(200, 200, 300, 200)])
        auditor = IOPortAuditor()
        auditor.audit_page(page_conn, net_pin_map, routed_nets)
        assert auditor._unwired == []
        assert auditor._exempt_name_only == 0


class TestNameConflict:
    def test_wps_vs_wps_page_pins(self):
        """IOPORT 'WPS' 与页内引脚显示名 'wps' 同 canonical → conflict。"""
        page_conn = _page(
            nets_display=["wps"],
            net_by_bare={"wps": "wps"},
            off_pages=[{"name": "OP_WPS", "net_name": "WPS"}],
        )
        net_pin_map = {
            "wps": [
                {"refdes": "R1", "pin": "1", "coord": (200, 200)},
                {"refdes": "IOPORT_0", "pin": "A", "coord": (300, 200)},
            ],
        }
        routed_nets = _routed("wps", [_wire(200, 200, 300, 200)])
        auditor = IOPortAuditor()
        auditor.audit_page(page_conn, net_pin_map, routed_nets)
        auditor.finalize(SimpleNamespace(cell_name="T", nets=[]))
        assert len(auditor._name_conflicts) == 1
        nc = auditor._name_conflicts[0]
        assert nc.ioport_name == "WPS"
        assert "wps" in nc.pin_net_names
        assert nc.canonical == "wps"
        # 不自动合并：net_pin_map 仍按各自 key
        assert "wps" in net_pin_map and "WPS" not in net_pin_map

    def test_global_grouping_distinct_raw(self):
        """两页 IOPORT 'WPS' / 'wps' → canonical 组内 distinct raw > 1。"""
        p1 = _page(["NET_A"], {"net_a": "NET_A"},
                   [{"name": "OP1", "net_name": "WPS"}])
        p2 = _page(["NET_A"], {"net_a": "NET_A"},
                   [{"name": "OP2", "net_name": "wps"}])
        auditor = IOPortAuditor()
        auditor.audit_page(p1, {}, {})
        auditor.audit_page(p2, {}, {})
        auditor.finalize(SimpleNamespace(cell_name="T", nets=[]))
        assert len(auditor._name_conflicts) == 1
        assert auditor._name_conflicts[0].canonical == "wps"
        assert set(auditor._name_conflicts[0].pin_net_names) == {"WPS", "wps"}

    def test_no_conflict_when_names_identical(self):
        page_conn = _page(
            nets_display=["NET_A"],
            net_by_bare={"net_a": "NET_A"},
            off_pages=[{"name": "OP_A", "net_name": "NET_A"}],
        )
        auditor = IOPortAuditor()
        auditor.audit_page(page_conn, {"NET_A": [
            {"refdes": "R1", "pin": "1", "coord": (200, 200)},
            {"refdes": "IOPORT_0", "pin": "A", "coord": (300, 200)},
        ]}, _routed("NET_A", [_wire(200, 200, 300, 200)]))
        auditor.finalize(SimpleNamespace(cell_name="T", nets=[]))
        assert auditor._name_conflicts == []


class TestOrphan:
    def test_orphan_no_component_pin(self):
        """IOPORT 网名全工程无元件引脚 → orphan=1。"""
        page_conn = _page(
            nets_display=["NET_A"],
            net_by_bare={"net_a": "NET_A"},
            off_pages=[{"name": "OP_X", "net_name": "NO_SUCH_NET"}],
        )
        auditor = IOPortAuditor()
        auditor.audit_page(page_conn, {}, {})
        auditor.finalize(SimpleNamespace(
            cell_name="T", nets=[SimpleNamespace(display_name="NET_A")],
        ))
        assert len(auditor._orphans) == 1
        assert auditor._orphans[0].net == "NO_SUCH_NET"
        assert auditor._orphans[0].reason == "no-component-pin"

    def test_auto_net_orphan_reason(self):
        page_conn = _page(
            nets_display=[],
            net_by_bare={},
            off_pages=[{"name": "OP_UN", "net_name": "UN$2$CAPACITOR$I7$1"}],
        )
        auditor = IOPortAuditor()
        auditor.audit_page(page_conn, {}, {})
        auditor.finalize(SimpleNamespace(cell_name="T", nets=[]))
        assert len(auditor._orphans) == 1
        assert auditor._orphans[0].reason == "auto-net"

    def test_orphan_ioport_names_static(self):
        """orphan_ioport_names 静态工具（skip_orphan 预计算）。"""
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="C1", library_id="CAPACITOR", loc_x=4500, loc_y=12000,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        p1.off_pages = [
            {"name": "OP_A", "net_name": "NET_A"},
            {"name": "OP_X", "net_name": "ORPHAN_NET"},
        ]
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        orphan = IOPortAuditor.orphan_ioport_names(conn)
        assert orphan == {"ORPHAN_NET"}


class TestSkipOrphanWriter:
    def _design(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="C1", library_id="CAPACITOR", loc_x=4500, loc_y=12000,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        p1.off_pages = [
            {"name": "OP_A", "net_name": "NET_A"},
            {"name": "OP_X", "net_name": "ORPHAN_NET"},
        ]
        return DesignIR(project_name="T", pages=[p1])

    def test_default_emits_all(self):
        from cis2hdl.core.config import RoutingConfig
        conn = ConnectivityModelBuilder(self._design(), matches=[]).build()
        content = CSAWriter(routing_cfg=RoutingConfig())._build_csa_content_conn(
            conn, conn.pages[0],
        )
        assert content.count("FORCEADD IOPORT..1") == 2

    def test_skip_orphan_skips_generation(self):
        from cis2hdl.core.config import RoutingConfig
        conn = ConnectivityModelBuilder(self._design(), matches=[]).build()
        cfg = RoutingConfig()
        cfg.ioport.skip_orphan = True
        w = CSAWriter(routing_cfg=cfg)
        w._orphan_ioport_names = IOPortAuditor.orphan_ioport_names(conn)
        content = w._build_csa_content_conn(conn, conn.pages[0])
        assert content.count("FORCEADD IOPORT..1") == 1
        # Pass 1 入网也跳过孤立 → ORPHAN_NET 不在 net_pin_map
        body = CoordTransform.map_page_instances(conn.pages[0].instances)
        _, _, npm = w._compute_pin_geometry(conn, conn.pages[0], body)
        assert not any(
            str(p.get("refdes", "")).startswith("IOPORT_")
            for key, pins in npm.items() if "ORPHAN" in key
            for p in pins
        )


class TestManualNames:
    def test_resolve_display_override(self):
        page_conn = _page([], {"wps_lv": "WPS_LV"}, [])
        auditor = IOPortAuditor(manual_names={"WPS": "WPS_LV"})
        assert auditor._resolve_display(page_conn, "WPS") == "WPS_LV"
        # 无覆盖 → 原样返回（con_name 未命中页网）
        plain = IOPortAuditor()
        assert plain._resolve_display(page_conn, "WPS") == "WPS"

    def test_writer_manual_names_joins_page_net(self):
        """manual_names 让 IOPORT 'WPS' 加入 'WPS_LV' 页网（否则孤立）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="C1", library_id="CAPACITOR", loc_x=4500, loc_y=12000,
                pin_connections={"1": "WPS_LV", "2": "NET_B"},
            ),
        ]
        p1.off_pages = [{"name": "OP_WPS", "net_name": "WPS"}]
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        page_conn = conn.pages[0]
        body = CoordTransform.map_page_instances(page_conn.instances)
        # 默认：IOPORT 无法加入 WPS_LV 网
        _, _, npm_default = CSAWriter()._compute_pin_geometry(
            conn, page_conn, body,
        )
        assert "WPS" in npm_default
        assert not any(
            p["refdes"] == "IOPORT_0" for p in npm_default["WPS_LV"]
        )
        # manual_names：IOPORT 加入 WPS_LV 网
        cfg = RoutingConfig()
        cfg.ioport.manual_names = {"WPS": "WPS_LV"}
        _, _, npm_manual = CSAWriter(routing_cfg=cfg)._compute_pin_geometry(
            conn, page_conn, body,
        )
        assert any(
            p["refdes"] == "IOPORT_0" for p in npm_manual["WPS_LV"]
        )


class TestReport:
    def test_write_report_sections(self, tmp_path):
        auditor = IOPortAuditor()
        auditor._pages = 1
        auditor._ioport_total = 3
        auditor._unique_nets = {"a", "b", "c"}
        auditor._exempt_name_only = 1
        auditor._unwired.append(UnwiredIoport(
            page="05-P", idx=0, net="NET_C", coord=(500, 500), pins_on_page=1,
        ))
        auditor._name_conflicts.append(NameConflict(
            page="13-D", ioport_name="WPS", pin_net_names=["wps"], canonical="wps",
        ))
        auditor._orphans.append(OrphanIoport(
            page="15-P", net="UN$2$X", canonical="un2x", reason="auto-net",
        ))
        auditor._project_name = "HG5015-BE36_V10"
        path = auditor.write(tmp_path)
        assert path is not None
        text = path.read_text(encoding="utf-8")
        assert "=== IOPORT Audit Report: HG5015-BE36_V10 ===" in text
        assert "[SUMMARY] pages=1  ioport_total=3  unique_nets=3" in text
        assert "unwired=1  name_conflicts=1  orphan=1  exempt_name_only=1" in text
        assert "[UNWIRED] total=1" in text and "NET_C" in text
        assert "[NAME_CONFLICT] total=1" in text and "WPS" in text
        assert "[ORPHAN] total=1" in text and "UN$2$X" in text
        assert "[FIX_SUGGESTION]" in text
        assert "ioport.skip_orphan=true" in text
        assert "ioport.manual_names" in text

    def test_write_report_none_case(self, tmp_path):
        auditor = IOPortAuditor()
        auditor.audit_page(_page(["NET_A"], {"net_a": "NET_A"}, [
            {"name": "OP_A", "net_name": "NET_A"},
        ]), {"NET_A": [
            {"refdes": "R1", "pin": "1", "coord": (200, 200)},
            {"refdes": "IOPORT_0", "pin": "A", "coord": (300, 200)},
        ]}, _routed("NET_A", [_wire(200, 200, 300, 200)]))
        auditor.finalize(SimpleNamespace(
            cell_name="T", nets=[SimpleNamespace(display_name="NET_A")],
        ))
        path = auditor.write(tmp_path)
        text = path.read_text(encoding="utf-8")
        assert "unwired=0  name_conflicts=0  orphan=0" in text
        assert "  (none)" in text

    def test_disabled_write_returns_none(self, tmp_path):
        assert IOPortAuditor(enabled=False).write(tmp_path) is None

    def test_wires_skipped_note(self, tmp_path):
        auditor = IOPortAuditor()
        auditor.mark_wires_skipped()
        path = auditor.write(tmp_path)
        text = path.read_text(encoding="utf-8")
        assert "emit_csa_wires=false" in text


class TestCanonical:
    def test_canonical_name(self):
        assert canonical_name("WPS") == "wps"
        assert canonical_name("wps") == "wps"
        assert canonical_name("W_P_S") == "wps"
        assert canonical_name("GND\\g") == "gnd"
        assert canonical_name("GND") == "gnd"
        assert canonical_name("NET_A") == "neta"
        assert canonical_name("") == ""
