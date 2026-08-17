"""exact 匹配插件（FR2 优先级 1；S4 参数化阶段插件）。

默认 profile ``[exact, fuzzy, passive, fallback]`` 的**链首插件**——充当
匹配阶段编排器：应用 yaml ``match`` 段参数（weights/prefix_scope/thresholds）
后委托完整 legacy 匹配管线（内部含 exact→fuzzy→passive→fallback 多级
策略，与 legacy 逐字节等价，FR9），写 ``ctx.matches`` 返回 True。
链中后续位置（fuzzy/passive/fallback 之后）时跳过。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import MatchStagePlugin

__all__ = ["ExactMatchPlugin", "PLUGIN"]


class ExactMatchPlugin(MatchStagePlugin):
    """exact 匹配插件（优先级 1；链首启用时编排完整匹配阶段）。"""

    name = "exact"
    description = (
        "exact 匹配（优先级 1）：作为匹配链首个启用插件时编排完整匹配阶段"
        "（委托 legacy 管线，内部含 exact→fuzzy→passive→fallback 多级策略）"
    )


PLUGIN = PluginSpec(
    name="exact",
    stage="match",
    description=ExactMatchPlugin.description,
    cls=ExactMatchPlugin,
    module=__name__,
    param_fields=("weights", "prefix_scope", "thresholds"),
    writes_keys=("matches",),
    requires=("ir", "hdl_db"),
    builtin=True,
)
