"""Phase XXII T03 — IO port 按网络聚类（D5，P1-2）。

Covers:
  * edge_layout 开启时按同网页内引脚 y 均值重排 IOPORT 槽位（确定性）
  * 同网 IOPORT 与页内引脚平均距离较等距基线下降
  * 无 IOPORT 坐标重叠
"""

from __future__ import annotations

from types import SimpleNamespace


def _writer(edge_layout: bool = True):
    from cis2hdl.core.config import IoportCfg, RoutingConfig
    from cis2hdl.core.writer.csa_writer import CSAWriter

    cfg = RoutingConfig(ioport=IoportCfg(
        edge_layout=edge_layout, edge_x=-600, edge_step=100, edge_margin=300,
    ))
    return CSAWriter(routing_cfg=cfg)


def _page(off_pages: list[dict]):
    from cis2hdl.core.writer.connectivity_model import PageConnectivity

    pc = PageConnectivity(page_num=1, page_name="01-Test")
    pc.off_pages = off_pages
    pc.net_by_bare = {}  # 回退 raw net_name
    return pc


class TestIoportClustering:
    def test_order_by_pin_y_mean_desc(self):
        """按同网页内引脚 y 均值降序分配槽位（高引脚网 → 顶部）。"""
        w = _writer()
        pc = _page([
            {"name": "OP_A", "net_name": "NET_A"},
            {"name": "OP_B", "net_name": "NET_B"},
        ])
        net_pin_map = {
            "NET_A": [{"refdes": "C1", "pin": "1", "coord": (-3000, 6200)}],
            "NET_B": [{"refdes": "C2", "pin": "1", "coord": (-3000, 4500)}],
        }
        w._build_ioport_cluster_order(pc, net_pin_map)
        # NET_A 引脚更高（6200）→ ordinal 0（顶）；NET_B → ordinal 1。
        assert w._ioport_cluster_order == {0: 0, 1: 1}
        y_a = w._ioport_position_cfg(0)[1]
        y_b = w._ioport_position_cfg(1)[1]
        assert y_a > y_b  # 顶→下无重叠

    def test_distance_mean_decrease_vs_baseline(self):
        """聚类后同网 IOPORT 与页内引脚平均距离较等距基线下降。

        原始 off_page 顺序（等距基线）与引脚位置无关（NET_B 低引脚先排）
        —— 聚类按 y 均值重排后总距离下降（多引脚网分布场景）。
        """
        w = _writer()
        # 等距基线：off_page 原序 [NET_B, NET_C, NET_A]（NET_B 低引脚先排）。
        pc = _page([
            {"name": "OP_B", "net_name": "NET_B"},
            {"name": "OP_C", "net_name": "NET_C"},
            {"name": "OP_A", "net_name": "NET_A"},
        ])
        net_pin_map = {
            "NET_A": [
                {"refdes": "U1", "pin": "1", "coord": (-3000, 6800)},
                {"refdes": "U1", "pin": "2", "coord": (-3000, 6900)},
            ],
            "NET_B": [{"refdes": "C2", "pin": "1", "coord": (-3000, 5000)}],
            "NET_C": [{"refdes": "C3", "pin": "1", "coord": (-3000, 6200)}],
        }

        def mean_dist(order: dict[int, int]) -> float:
            total = 0.0
            count = 0
            for idx, op in enumerate(pc.off_pages):
                net_name = op["net_name"]
                pins = [
                    p for p in net_pin_map.get(net_name, [])
                    if not str(p.get("refdes", "")).startswith("IOPORT_")
                ]
                ioport_y = _PositionHelper.y(order.get(idx, idx))
                for p in pins:
                    total += abs(ioport_y - int(p["coord"][1]))
                    count += 1
            return total / max(count, 1)

        # 等距基线 = 原序（order identity）。
        baseline = mean_dist({0: 0, 1: 1, 2: 2})
        w._build_ioport_cluster_order(pc, net_pin_map)
        clustered = mean_dist(w._ioport_cluster_order)
        assert clustered < baseline, (
            f"clustered {clustered} >= baseline {baseline}"
        )

    def test_no_overlap_and_deterministic(self):
        """无 IOPORT 坐标重叠 + 确定性（两次计算一致）。"""
        w = _writer()
        pc = _page([
            {"name": "OP_A", "net_name": "NET_A"},
            {"name": "OP_B", "net_name": "NET_B"},
            {"name": "OP_C", "net_name": "NET_C"},
        ])
        net_pin_map = {
            "NET_A": [{"refdes": "C1", "pin": "1", "coord": (-3000, 6000)}],
            "NET_B": [{"refdes": "C2", "pin": "1", "coord": (-3000, 5800)}],
            "NET_C": [{"refdes": "C3", "pin": "1", "coord": (-3000, 5600)}],
        }
        w._build_ioport_cluster_order(pc, net_pin_map)
        first = dict(w._ioport_cluster_order)
        w._build_ioport_cluster_order(pc, net_pin_map)
        assert w._ioport_cluster_order == first  # 确定性

        positions = [w._ioport_position_cfg(i) for i in range(3)]
        assert len({p for p in positions}) == 3  # 无重叠
        ys = [p[1] for p in positions]
        assert len(set(ys)) == 3  # 无同 y

    def test_disabled_edge_layout_keeps_original(self):
        """edge_layout 关闭时不做聚类（保持原等距/默认公式）。"""
        w = _writer(edge_layout=False)
        pc = _page([
            {"name": "OP_A", "net_name": "NET_A"},
            {"name": "OP_B", "net_name": "NET_B"},
        ])
        w._build_ioport_cluster_order(pc, {"NET_A": [], "NET_B": []})
        assert w._ioport_cluster_order == {}


class _PositionHelper:
    """辅助：按 ordinal 返回 edge_layout 槽位 y（与 _ioport_position_cfg
    同源公式，供测试计算基线距离）。"""

    @staticmethod
    def y(ordinal: int) -> int:
        return (7200 - 300) - ordinal * 100
