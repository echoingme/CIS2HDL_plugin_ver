"""匹配阶段编排基类（exact/fuzzy/passive/fallback/matcher_pipeline 共用；S4）。

匹配插件链语义（FR9 默认等价 + FR2 独立启停）：

- yaml ``match.plugins`` 顺序 = **优先级顺序**（exact 优先 → fuzzy →
  passive → fallback），由 PluginManager 逆序注册保证（S2 决策 D1）。
- **链中第一个启用的匹配插件**充当**阶段编排器**：把 yaml ``match`` 段参数
  （``weights`` / ``prefix_scope`` / ``thresholds``）应用到 matcher 运行时
  配置后，委托 ``engine.run_match_stage()``（= ``_stage_match`` +
  ``_append_power_symbol_matches``，与 legacy convert() 逐字节等价），写
  ``ctx.matches``，返回 True。
- 链中后续插件见 ``ctx.matches`` 已就绪 → **跳过**（返回 False，不重复匹配、
  不覆盖）。

设计依据：
- 铁律"不重写匹配逻辑"：本类只**编排调用 + 配置应用**，不改任何 matcher
  源码（exact/fuzzy/passive_matcher/fallback/active_matcher 保持原实现）。
- 默认 profile ``[exact, fuzzy, passive, fallback]``：exact（链首）编排 →
  行为与 legacy 完全一致（FR9）。
- 任一匹配插件单独启用（如 ``[fuzzy]``）也足以运行完整匹配阶段——插件名
  表达**优先级序位**，链内首个启用者执行（FR2 可独立启停）。
- ``matcher_pipeline`` 为显式编排插件（同语义，profile 可直用）。
"""

from __future__ import annotations

import logging
from typing import Any

from ..hookspecs import hookimpl
from ..context import ConversionContext
from ._match_params import AppliedMatchParams, apply_match_params, restore_match_params
from ._prefix_scope import apply_prefix_scope

logger = logging.getLogger(__name__)

__all__ = ["MatchStagePlugin"]


class MatchStagePlugin:
    """匹配阶段插件基类（编排委托 + yaml 参数应用）。

    子类只需设置 ``name`` / ``description``（PluginSpec 同名字段）。
    """

    name: str = ""
    description: str = ""

    def __init__(
        self,
        engine: Any = None,
        weights: dict[str, float] | None = None,
        prefix_scope: dict[str, list[str]] | None = None,
        thresholds: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        """构造（engine 由 PluginManager 注入；其余来自 yaml match 段）。"""
        self.engine = engine
        self.weights = weights
        self.prefix_scope = prefix_scope
        self.thresholds = thresholds
        self.params = kwargs

    @hookimpl
    def match_components(self, ctx: ConversionContext) -> bool | None:
        """匹配阶段钩子：链首启用插件编排完整匹配，其余跳过。"""
        if ctx is None:
            return False
        if ctx.matches:
            return False  # 已被链中先前插件接管
        if ctx.ir is None or ctx.hdl_db is None:
            return False  # 前置产物未就绪 → 回退 legacy
        if self.engine is None:
            return False
        self._run_match_stage(ctx)
        return True

    def _run_match_stage(self, ctx: ConversionContext) -> None:
        """应用 yaml 参数 → 委托 engine.run_match_stage → 写 ctx.matches。

        参数应用与委托均在 try/finally 中保证恢复（异常也不残留全局配置）。
        """
        applied: AppliedMatchParams = apply_match_params(
            thresholds=self.thresholds,
            weights=self.weights,
        )
        try:
            scope_db = apply_prefix_scope(self.prefix_scope, ctx.hdl_db)
            ctx.matches = self.engine.run_match_stage(
                ctx.ir,
                scope_db,
                ctx.report,
                cross_ref_map=getattr(self.engine, "_last_cross_ref_map", None),
                pc=None,
            )
        finally:
            restore_match_params(applied)

    def cleanup(self) -> None:
        """可逆卸载：释放 engine 引用（幂等）。"""
        self.engine = None
        self.params = {}
