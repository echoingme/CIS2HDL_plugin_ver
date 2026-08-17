"""wire_simplify 美化插件（FR4 / Phase XVII M4；S5 真实现）。

对应 writer 模块：``cis2hdl/core/writer/wire_simplifier.py``
（``simplify_wires`` —— merge → trim → remove_jogs → add_junctions，
SKiDL cleanup_wires 移植）。CSAWriter 在布线后调用（``wire_simplify.enabled``
门），顺序由 writer 内部保证。

S5 语义：``beautify.params.wire_simplify.enabled`` 为 enabled 门
（默认 False，CLI --wire-simplify 时代）。启用 → 应用完整
``beautify.params`` 到全局 ``config.routing``；返回 True。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import BeautifyPlugin

__all__ = ["WireSimplifyPlugin", "PLUGIN"]


class WireSimplifyPlugin(BeautifyPlugin):
    """电线化简（Phase XVII M4 迁移；wire_simplifier 编排）。"""

    name = "wire_simplify"
    description = (
        "电线化简（默认关）：writer wire_simplifier.simplify_wires 编排"
        "（merge/trim/remove_jogs/add_junctions 布线后处理）"
    )

    def _enabled_from_params(self, params: dict) -> bool:
        """enabled 门 = ``wire_simplify.enabled``（默认 False）。"""
        return bool(params.get("enabled", False))


PLUGIN = PluginSpec(
    name="wire_simplify",
    stage="beautify",
    description=WireSimplifyPlugin.description,
    cls=WireSimplifyPlugin,
    module=__name__,
    param_section="wire_simplify",
    param_fields=("enabled",),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
