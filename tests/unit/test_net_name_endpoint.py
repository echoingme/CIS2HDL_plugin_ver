"""Phase XVIII R7 — 网络名标签落电线末端（net_name_connect 扩展）。

Covers:
  * `net_name_endpoints`：跨页网 WIRE 悬空端补 SIG_NAME 标签
  * 端点判定：悬空端 ≠ 引脚坐标
"""

from __future__ import annotations


class TestNetNameEndpoints:
    def test_dangling_end_gets_label(self):
        """WIRE 段一端接引脚、一端悬空 → 悬空端补标签。"""
        from cis2hdl.core.writer.net_name_connect import net_name_endpoints

        segs = {"NET_A": [(0, 0, 200, 0)]}
        pins = {"NET_A": [{"refdes": "C1", "pin": "1", "coord": (0, 0)}]}
        labels = net_name_endpoints(pins, segs, {"net_a"}, use_net_name=True)
        assert len(labels) == 1
        assert labels[0][0] == (200, 0)
        assert labels[0][1] == "NET_A"

    def test_use_net_name_off(self):
        """开关关闭时不生成。"""
        from cis2hdl.core.writer.net_name_connect import net_name_endpoints

        segs = {"NET_A": [(0, 0, 200, 0)]}
        pins = {"NET_A": [{"refdes": "C1", "pin": "1", "coord": (0, 0)}]}
        assert net_name_endpoints(pins, segs, {"net_a"}, use_net_name=False) == []

    def test_non_cross_page_skipped(self):
        """非跨页网不处理。"""
        from cis2hdl.core.writer.net_name_connect import net_name_endpoints

        segs = {"LOCAL": [(0, 0, 200, 0)]}
        pins = {"LOCAL": [{"refdes": "C1", "pin": "1", "coord": (0, 0)}]}
        assert net_name_endpoints(pins, segs, {"net_a"}, use_net_name=True) == []

    def test_no_dangling_end(self):
        """段两端都接引脚 → 无标签。"""
        from cis2hdl.core.writer.net_name_connect import net_name_endpoints

        segs = {"NET_A": [(0, 0, 200, 0)]}
        pins = {
            "NET_A": [
                {"refdes": "C1", "pin": "1", "coord": (0, 0)},
                {"refdes": "C2", "pin": "1", "coord": (200, 0)},
            ],
        }
        assert net_name_endpoints(pins, segs, {"net_a"}, use_net_name=True) == []

    def test_farthest_dangling_preferred(self):
        """多悬空端取距引脚最远者。"""
        from cis2hdl.core.writer.net_name_connect import net_name_endpoints

        segs = {"NET_A": [(0, 0, 100, 0), (100, 0, 300, 0)]}
        pins = {"NET_A": [{"refdes": "C1", "pin": "1", "coord": (0, 0)}]}
        labels = net_name_endpoints(pins, segs, {"net_a"}, use_net_name=True)
        assert labels[0][0] == (300, 0)


class TestNetNameEndpointD3:
    """Phase XXII D3（Q3 单一调用点）：跨页悬空端全补 + 不双标签。"""

    def test_all_cross_page_dangling_labeled(self):
        """多个跨页网各有悬空端 → 每网补 1 个标签（全补）。"""
        from cis2hdl.core.writer.net_name_connect import net_name_endpoints

        segs = {
            "NET_A": [(0, 0, 200, 0), (200, 0, 400, 0)],  # 悬空端 (400,0)
            "NET_B": [(0, 0, 150, 0)],                    # 悬空端 (150,0)
        }
        pins = {
            "NET_A": [{"refdes": "C1", "pin": "1", "coord": (0, 0)}],
            "NET_B": [{"refdes": "C2", "pin": "1", "coord": (0, 0)}],
        }
        labels = net_name_endpoints(
            pins, segs, {"net_a", "net_b"}, use_net_name=True,
        )
        nets = {net for _, net in labels}
        assert nets == {"NET_A", "NET_B"}, f"labels={labels}"
        # 每网至多 1 个标签（同网不双标签）。
        from collections import Counter

        counts = Counter(net for _, net in labels)
        assert all(c == 1 for c in counts.values()), f"duplicate: {counts}"

    def test_no_double_label_dedup_in_csa(self, monkeypatch):
        """csa_writer 去重：网已在 _extra_sig_names → 泛化 has_label 循环跳过
        （不产生同网双标签）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.writer import net_name_connect as nnc
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csa_writer import CSAWriter

        import re

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="U1", library_id="U1", loc_x=4500, loc_y=12000,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        p2 = PageIR(page_id="2.1", page_name="06-Power_Supply2")
        p2.instances = [
            ComponentInstanceIR(
                refdes="U2", library_id="U2", loc_x=4500, loc_y=12000,
                pin_connections={"1": "NET_A"},
            ),
        ]
        design = DesignIR(project_name="T", pages=[p1, p2])
        conn = ConnectivityModelBuilder(design, matches=[]).build()

        # 模拟 net_name_endpoints 为 NET_A 返回悬空端标签；source_pins 置空
        # 使泛化 has_label 循环本会补 NET_A —— 去重后不得双标签。
        monkeypatch.setattr(
            nnc, "net_name_endpoints",
            lambda *a, **k: [((100, 100), "NET_A")],
        )
        cfg = RoutingConfig()
        cfg.ioport.use_net_name = True
        writer = CSAWriter(routing_cfg=cfg)
        monkeypatch.setattr(writer, "_choose_sig_name_sources", lambda nm: set())
        content = writer._build_csa_content_conn(conn, conn.pages[0])
        sig_a = re.findall(r"SIG_NAME NET_A\b", content)
        assert len(sig_a) == 1, f"NET_A double label: {sig_a}"
        # NET_B（非跨页，无悬空端）由泛化循环补 1 条。
        sig_b = re.findall(r"SIG_NAME NET_B\b", content)
        assert len(sig_b) == 1, f"NET_B missing: {sig_b}"
