"""parallel_short 美化插件（FR4 / Phase XVIII R6/R8 / Q4；S5 真实现）。

对应 writer 模块：``cis2hdl/core/writer/wire_simplifier.py``
（``plan_parallel_short``，路由前 hub 短接计划）+ ``gnd_cluster_planner``
（``route_cluster_parallel`` / ``hub_short_wires``，簇内短接段）。CSAWriter
在布线前对非 GND 同信号引脚簇（间距 ≤ ``parallel_short_dist``）做 hub
短接，顺序由 writer 内部保证（GND 簇由 gnd_cluster_planner 处理）。

S5 语义：``beautify.params.gnd_distribution.parallel_short`` 为 enabled 门
（默认 True；同名 writer 门为 ``wire_simplify.parallel_short``，默认同为
True —— 完整 params 应用保证二者一致）。启用 → 应用完整 ``beautify.params``
到全局 ``config.routing``；返回 True。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import BeautifyPlugin

__all__ = ["ParallelShortPlugin", "PLUGIN"]


class ParallelShortPlugin(BeautifyPlugin):
    """并联优化（R6/R8 迁移；plan_parallel_short/route_cluster_parallel 编排）。"""

    name = "parallel_short"
    description = (
        "并联优化（默认）：writer wire_simplifier.plan_parallel_short 编排"
        "（路由前 hub 短接，簇内引脚先并联再统一引出）"
    )

    def _enabled_from_params(self, params: dict) -> bool:
        """enabled 门 = ``gnd_distribution.parallel_short``（默认 True）。"""
        return bool(params.get("parallel_short", False))


PLUGIN = PluginSpec(
    name="parallel_short",
    stage="beautify",
    description=ParallelShortPlugin.description,
    cls=ParallelShortPlugin,
    module=__name__,
    param_section="gnd_distribution",
    param_fields=("parallel_short", "parallel_short_dist"),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
