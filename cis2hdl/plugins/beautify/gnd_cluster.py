"""gnd_cluster 美化插件（FR4 / Phase XVII R3 / P1-D；S5 真实现）。

对应 writer 模块：``cis2hdl/core/writer/gnd_cluster_planner.py``
（``ensure_gnd_symbols`` / ``place_gnd_symbol`` / ``hub_short_wires``，
CSAWriter 在布线前调用 —— 页面 1/4 分块、GND 符号就近放置，顺序由
writer 内部保证）。

S5 语义：``beautify.params.gnd_distribution.enabled`` 为 enabled 门
（默认 False）。启用 → 应用完整 ``beautify.params`` 到全局
``config.routing``，writer 内置 GND 聚类逻辑按配置执行；返回 True。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import BeautifyPlugin

__all__ = ["GndClusterPlugin", "PLUGIN"]


class GndClusterPlugin(BeautifyPlugin):
    """GND 聚类（Phase XVII R3 迁移；gnd_cluster_planner 编排）。"""

    name = "gnd_cluster"
    description = (
        "GND 聚类（默认）：writer gnd_cluster_planner 编排"
        "（ensure_gnd_symbols/place_gnd_symbol/hub_short_wires）"
    )

    def _enabled_from_params(self, params: dict) -> bool:
        """enabled 门 = ``gnd_distribution.enabled``（默认 False）。"""
        return bool(params.get("enabled", False))


PLUGIN = PluginSpec(
    name="gnd_cluster",
    stage="beautify",
    description=GndClusterPlugin.description,
    cls=GndClusterPlugin,
    module=__name__,
    param_section="gnd_distribution",
    param_fields=("enabled", "cluster_radius"),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
