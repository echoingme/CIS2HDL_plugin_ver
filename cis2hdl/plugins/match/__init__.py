"""match 阶段插件包（FR2/FR3）。

S4：6 个真实现插件（S2 设计的 match 薄包装在 S4 从零创建）：

- ``matcher_pipeline`` —— 匹配阶段显式编排（委托 engine.run_match_stage）。
- ``exact`` / ``fuzzy`` / ``passive`` / ``fallback`` —— 参数化阶段插件
  （yaml match.plugins 顺序 = 优先级顺序；**链首启用者**充当阶段编排器，
  其余跳过；任一单独启用即足以运行完整匹配阶段，FR2）。
- ``manual_overrides`` —— 手动干预（chip_config/manual_matches/power_ic，
  FR3；默认 profile 不启用，启用后接管 apply_manual_overrides 钩子）。

``_SPECS`` 汇总（供 discover 读取）。私有助手（``_base`` / ``_match_params`` /
``_prefix_scope``）为模块内实现细节，不对外。
"""

from __future__ import annotations

from ..spec import PluginSpec
from . import (
    exact,
    fallback,
    fuzzy,
    manual_overrides,
    matcher_pipeline,
    passive,
)

_SPECS: list[PluginSpec] = [
    matcher_pipeline.PLUGIN,
    exact.PLUGIN,
    fuzzy.PLUGIN,
    passive.PLUGIN,
    fallback.PLUGIN,
    manual_overrides.PLUGIN,
]

__all__ = [
    "_SPECS",
    "matcher_pipeline",
    "exact",
    "fuzzy",
    "passive",
    "fallback",
    "manual_overrides",
]
