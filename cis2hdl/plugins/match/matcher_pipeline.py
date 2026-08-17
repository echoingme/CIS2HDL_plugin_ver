"""matcher_pipeline 匹配编排插件（S4 显式编排；双路径之一）。

默认 profile（``[exact, fuzzy, passive, fallback]``）由链首 ``exact`` 编排；
本插件提供**显式编排**入口——profile 写成 ``match.plugins: [matcher_pipeline]``
时，由它委托完整 legacy 匹配管线（行为与 ``exact`` 编排完全一致）。
"""

from __future__ import annotations

from ..spec import PluginSpec
from ._base import MatchStagePlugin

__all__ = ["MatcherPipelinePlugin", "PLUGIN"]


class MatcherPipelinePlugin(MatchStagePlugin):
    """匹配阶段显式编排插件（委托 engine.run_match_stage，与 legacy 等价）。"""

    name = "matcher_pipeline"
    description = (
        "匹配阶段编排（显式）：委托 engine.run_match_stage = "
        "_stage_match + _append_power_symbol_matches，与 legacy 等价"
    )


PLUGIN = PluginSpec(
    name="matcher_pipeline",
    stage="match",
    description=MatcherPipelinePlugin.description,
    cls=MatcherPipelinePlugin,
    module=__name__,
    param_fields=("weights", "prefix_scope", "thresholds"),
    writes_keys=("matches",),
    requires=("ir", "hdl_db"),
    builtin=True,
)
