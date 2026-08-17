"""fallback 匹配插件（FR2 优先级 4；S4 参数化阶段插件）。

默认 profile 中位于 ``passive`` 之后：链首已编排 → 跳过。单独启用
（如 ``[fallback]``）或作为链首时 → 充当匹配阶段编排器，委托完整 legacy
匹配管线（与 legacy 等价），写 ``ctx.matches`` 返回 True。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import MatchStagePlugin

__all__ = ["FallbackMatchPlugin", "PLUGIN"]


class FallbackMatchPlugin(MatchStagePlugin):
    """fallback 匹配插件（优先级 4；链首启用时编排完整匹配阶段）。"""

    name = "fallback"
    description = (
        "fallback 匹配（优先级 4）：作为匹配链首个启用插件时编排完整匹配阶段"
        "（委托 legacy 管线，内部含 exact→fuzzy→passive→fallback 多级策略）"
    )


PLUGIN = PluginSpec(
    name="fallback",
    stage="match",
    description=FallbackMatchPlugin.description,
    cls=FallbackMatchPlugin,
    module=__name__,
    param_fields=("weights", "prefix_scope", "thresholds"),
    writes_keys=("matches",),
    requires=("ir", "hdl_db"),
    builtin=True,
)
