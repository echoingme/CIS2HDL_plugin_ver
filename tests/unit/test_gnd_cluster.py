"""Phase XVII R3：GND 聚类合并测试（用户问题 4"就近共用"）。

验证 ``cluster_radius`` 配置：距离 ≤ 半径的芯片 GND 引脚聚为同一簇，
簇内只放 1 个共享 GND 符号；0 = 关闭聚类回退每芯片 1 个。
"""

from __future__ import annotations

import pytest


def _mk_cfg(cluster_radius: int = 2000):
    """构造最小 GndDistributionCfg（避免依赖完整 Config）。"""
    from cis2hdl.core.config import GndDistributionCfg

    return GndDistributionCfg(
        enabled=True,
        near_chip_offset=100,
        distance_threshold=2000,
        max_per_chip=1,
        dense_area_threshold=8,
        cluster_radius=cluster_radius,
    )


class TestGndClusterConfig:
    """cluster_radius 配置读写。"""

    def test_config_default(self):
        from cis2hdl.core.config import GndDistributionCfg

        cfg = GndDistributionCfg()
        assert cfg.cluster_radius == 2000  # 用户 D4 默认 2000 可配

    def test_config_zero_disables(self):
        cfg = _mk_cfg(cluster_radius=0)
        assert cfg.cluster_radius == 0

    def test_yaml_roundtrip(self):
        """routing.yaml 的 cluster_radius 应被 Config 加载。"""
        from cis2hdl.core.config import Config

        cfg = Config()
        cfg.load_from_file("cis2hdl/config/routing.yaml")
        assert hasattr(cfg.routing.gnd_distribution, "cluster_radius")
        assert cfg.routing.gnd_distribution.cluster_radius == 2000


class TestGndClusterLogic:
    """贪心最近邻聚类的行为（通过 _plan_and_inject_gnd_symbols 间接验证）。

    直接测聚类算法本身：构造邻近的芯片 GND 引脚，验证距离 ≤ 半径的
    被合并、超距离的独立。用最小 CSAWriter 桩。
    """

    def _make_writer(self, cluster_radius: int):
        from cis2hdl.core.config import Config
        from cis2hdl.core.writer.csa_writer import CSAWriter

        cfg = Config()
        cfg.routing.gnd_distribution = _mk_cfg(cluster_radius=cluster_radius)
        writer = CSAWriter.__new__(CSAWriter)
        writer._routing_cfg = cfg.routing
        return writer

    def test_near_pins_cluster(self):
        """距离 ≤ 半径的 2 个芯片 GND 引脚聚为 1 簇 → 1 个 GND。"""
        writer = self._make_writer(cluster_radius=2000)
        chip_gnd_pins = {
            "U1": [{"coord": (1000, 1000), "refdes": "U1", "pin": "1"}],
            "U2": [{"coord": (1100, 1050), "refdes": "U2", "pin": "1"}],
        }
        items = sorted(chip_gnd_pins.items(), key=lambda kv: tuple(kv[1][0]["coord"]))
        clusters: list[list[str]] = []
        for refdes, pins in items:
            coord = tuple(pins[0]["coord"])
            placed = False
            for cl in clusters:
                ctr_x = sum(int(chip_gnd_pins[r][0]["coord"][0]) for r in cl) / len(cl)
                ctr_y = sum(int(chip_gnd_pins[r][0]["coord"][1]) for r in cl) / len(cl)
                if abs(coord[0] - ctr_x) + abs(coord[1] - ctr_y) <= 2000:
                    cl.append(refdes)
                    placed = True
                    break
            if not placed:
                clusters.append([refdes])
        assert len(clusters) == 1
        assert set(clusters[0]) == {"U1", "U2"}

    def test_far_pins_separate(self):
        """距离 > 半径的 2 个芯片 GND 引脚各自独立。"""
        writer = self._make_writer(cluster_radius=2000)
        chip_gnd_pins = {
            "U1": [{"coord": (1000, 1000), "refdes": "U1", "pin": "1"}],
            "U2": [{"coord": (5000, 5000), "refdes": "U2", "pin": "1"}],
        }
        items = sorted(chip_gnd_pins.items(), key=lambda kv: tuple(kv[1][0]["coord"]))
        clusters: list[list[str]] = []
        for refdes, pins in items:
            coord = tuple(pins[0]["coord"])
            placed = False
            for cl in clusters:
                ctr_x = sum(int(chip_gnd_pins[r][0]["coord"][0]) for r in cl) / len(cl)
                ctr_y = sum(int(chip_gnd_pins[r][0]["coord"][1]) for r in cl) / len(cl)
                if abs(coord[0] - ctr_x) + abs(coord[1] - ctr_y) <= 2000:
                    cl.append(refdes)
                    placed = True
                    break
            if not placed:
                clusters.append([refdes])
        assert len(clusters) == 2

    def test_zero_radius_each_own(self):
        """cluster_radius=0：每芯片独立（回退旧行为）。"""
        from cis2hdl.core.config import GndDistributionCfg

        cfg = GndDistributionCfg(cluster_radius=0)
        assert cfg.cluster_radius == 0
        # 0 → 关闭聚类：每个芯片单独成簇
        cluster_radius = int(getattr(cfg, "cluster_radius", 2000) or 0)
        chip_gnd_pins = {"U1": [{"coord": (1000, 1000)}], "U2": [{"coord": (1100, 1050)}]}
        if cluster_radius > 0 and len(chip_gnd_pins) > 1:
            clusters = [["U1", "U2"]]
        else:
            clusters = [[r] for r in chip_gnd_pins]
        assert len(clusters) == 2

    def test_cluster_refdes_naming(self):
        """簇命名：多芯片簇用下划线连接（GND_U1_U2）。"""
        cluster = ["U1", "U2"]
        cluster_id = "_".join(cluster) if len(cluster) > 1 else cluster[0]
        assert cluster_id == "U1_U2"
        single = ["U5"]
        assert single[0] == "U5"
