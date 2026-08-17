"""text_layout 美化插件（FR4 / Phase XIV D1；S5 真实现）。

对应 writer 模块：``cis2hdl/core/writer/text_layout.py``
（``TextLayoutOptimizer`` —— solve_label_offsets 解算标签偏移，VALUE/
$LOCATION 标签方向/对齐）。CSAWriter 在布线后（文本/标签行写出前）调用，
顺序由 writer 内部保证（text_layout 是美化链最末尾的功能）。

S5 语义：``beautify.params.text_layout.enabled`` 为 enabled 门
（默认 False，CLI --text-layout/--aesthetic 置 True）。启用 → 应用完整
``beautify.params`` 到全局 ``config.routing``；返回 True。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import BeautifyPlugin

__all__ = ["TextLayoutPlugin", "PLUGIN"]


class TextLayoutPlugin(BeautifyPlugin):
    """文本/标签去冲突（Phase XIV D1 迁移；TextLayoutOptimizer 编排）。"""

    name = "text_layout"
    description = (
        "文本/标签去冲突（默认关）：writer TextLayoutOptimizer 编排"
        "（VALUE/$LOCATION 标签偏移解算，方向随元件 R 行）"
    )

    def _enabled_from_params(self, params: dict) -> bool:
        """enabled 门 = ``text_layout.enabled``（默认 False）。"""
        return bool(params.get("enabled", False))


PLUGIN = PluginSpec(
    name="text_layout",
    stage="beautify",
    description=TextLayoutPlugin.description,
    cls=TextLayoutPlugin,
    module=__name__,
    param_section="text_layout",
    param_fields=("enabled",),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
