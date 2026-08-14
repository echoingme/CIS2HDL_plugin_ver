"""Phase XXII T02 — 并联扩展到所有信号（D4，P1-5，Q4 仅接线）。

Covers:
  * plan_parallel_short：非 GND 同信号相近引脚簇 hub 短接计划
  * 每簇段数 = 簇内引脚数（hub 短接）+ 1（引出）
  * 端点 = 引脚坐标（坐标唯一原则）
  * wire_simplify.enabled 保持 false（不开整体化简）
"""

from __future__ import annotations


class TestPlanParallelShort:
    def test_nearby_cluster_hub_short(self):
        """间距 ≤500 的 3 引脚聚 1 簇：hub + 簇内短接段。"""
        from cis2hdl.core.writer.wire_simplifier import plan_parallel_short

        pins = [(-3000, 5000), (-2900, 5000), (-2800, 5000)]
        clusters, short = plan_parallel_short(pins, max_dist=500)
        assert len(clusters) == 1
        hub, members = clusters[0]
        assert hub == (-2900, 5000)  # 包围盒中心
        assert sorted(members) == sorted(pins)
        # 每引脚 → hub 至少 1 段（簇内短接），端点 = 引脚坐标。
        assert short
        endpoints = set()
        for s in short:
            endpoints.add((s[0], s[1]))
            endpoints.add((s[2], s[3]))
        for p in pins:
            assert p in endpoints, f"pin {p} not a short-wire endpoint"
        assert hub in endpoints, "hub must be a short-wire endpoint"

    def test_far_pin_not_clustered(self):
        """远端引脚（> 阈值）不并入簇。"""
        from cis2hdl.core.writer.wire_simplifier import plan_parallel_short

        pins = [(-3000, 5000), (-2900, 5000), (-1000, 6000)]
        clusters, _short = plan_parallel_short(pins, max_dist=500)
        assert len(clusters) == 1  # 只有近距 2 个聚簇
        _hub, members = clusters[0]
        assert (-1000, 6000) not in members

    def test_single_pin_no_cluster(self):
        """单引脚/空输入 → 无簇。"""
        from cis2hdl.core.writer.wire_simplifier import plan_parallel_short

        assert plan_parallel_short([]) == ([], [])
        assert plan_parallel_short([(0, 0)]) == ([], [])

    def test_all_coords_on_grid(self):
        """hub 与短接段全部 25 网格（引脚坐标保持输入不变）。"""
        from cis2hdl.core.writer.wire_simplifier import plan_parallel_short

        pins = [(-3000, 5000), (-2875, 5000), (-2775, 5000)]
        clusters, short = plan_parallel_short(pins, max_dist=500)
        for hub, _members in clusters:
            assert hub[0] % 25 == 0 and hub[1] % 25 == 0
        for s in short:
            for v in s:
                assert v % 25 == 0, f"off-grid {s}"


class TestParallelShortGate:
    def test_wire_simplify_enabled_still_false(self):
        """Q4：wire_simplify.enabled 保持 false（只接线 parallel_short）。"""
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig()
        assert cfg.wire_simplify.enabled is False
        assert cfg.wire_simplify.parallel_short is True
        assert cfg.wire_simplify.parallel_short_dist == 500

    def test_parallel_short_dist_loaded_from_yaml(self):
        """routing.yaml 加载后 parallel_short_dist=500 生效。"""
        import cis2hdl as _pkg
        from cis2hdl.core.config import config as cfg
        from pathlib import Path

        routing_config = Path(_pkg.__file__).parent / "config" / "routing.yaml"
        saved = cfg.routing
        try:
            if routing_config.exists():
                cfg.load_from_file(routing_config)
            assert cfg.routing.wire_simplify.parallel_short_dist == 500
        finally:
            cfg.routing = saved
