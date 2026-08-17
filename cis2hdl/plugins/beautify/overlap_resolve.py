"""overlap_resolve 美化插件（FR4 / D2 检测 + R5 避让；S5 真实现）。

对应 writer 模块：``cis2hdl/core/writer/overlap_resolver.py``
（``OverlapResolver.resolve_passives``，CSAWriter 在 ``_compute_pin_geometry``
之前调用 —— body 位移后 pin/LASTPIN/WIRE 用新 body 重算，顺序由 writer
内部保证）。

S5 语义：``beautify.params.overlap.resolve`` 为 enabled 门（默认 True）。
启用 → 应用完整 ``beautify.params`` 到全局 ``config.routing``，writer 内置
OverlapResolver 逻辑按配置执行；返回 True。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import BeautifyPlugin

__all__ = ["OverlapResolvePlugin", "PLUGIN"]


class OverlapResolvePlugin(BeautifyPlugin):
    """防重叠（D2 检测 + R5 避让；overlap_resolver 编排）。"""

    name = "overlap_resolve"
    description = (
        "防重叠（默认）：writer OverlapResolver.resolve_passives 编排"
        "（passive/connector 微调避让，body 位移 snap 50 网格）"
    )

    def _enabled_from_params(self, params: dict) -> bool:
        """enabled 门 = ``overlap.resolve``（默认 True）。"""
        return bool(params.get("resolve", False))


PLUGIN = PluginSpec(
    name="overlap_resolve",
    stage="beautify",
    description=OverlapResolvePlugin.description,
    cls=OverlapResolvePlugin,
    module=__name__,
    param_section="overlap",
    param_fields=("check", "resolve", "avoid_margin"),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
