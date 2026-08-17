"""美化阶段插件基类（S5：6 个 beautify 插件共用）。

设计依据：``docs/S2-plugin-base-design.md`` §4.3（GndClusterPlugin 示例）与
S4 匹配链"薄包装编排"模式（``docs/developer-guide.md`` S4 章节）。

铁律（FR9 默认等价 + FR2 独立启停 + NFR3 不重写美化逻辑）：

- **美化逻辑仍在 writer 内部**：``overlap_resolver`` / ``gnd_cluster_planner``
  / ``wire_simplifier`` / ``wire_layout`` / ``text_layout`` 保持原实现，插件
  **不搬运、不重写**任何美化算法。
- **插件职责 = 配置编排（副作用）**：在 ``beautify`` 钩子（Stage 6 generate
  之前）把 yaml ``beautify.params``（RoutingConfig，S1 K1 复用）应用到全局
  ``config.routing`` —— CSAWriter 在 generate 时读取该对象，其内置美化逻辑
  按配置开关在**正确阶段**执行（overlap 在 pin 几何前、gnd/parallel 在布线
  前、wire_simplify 布线后、text_layout 末尾），顺序语义由 writer 内部保持，
  插件链顺序 = yaml 顺序（S2 逆序注册保证）。
- **完整 params 应用**（而非仅本插件 param_section）：与 S1 CLI
  ``cfg_obj.routing = cfg.to_routing_config()`` 完全等价 —— 保证
  ``routing.mode=detour``（max-beauty）、``wire_simplify.parallel_short_dist``
  等**未被单插件 param_fields 覆盖**的字段也全部生效（FR9 字节等价）。
  默认 profile 时应用结果 == RoutingConfig 默认 → no-op，天然等价。
- **每个插件有自己的 enabled 语义**（来自 params）：
    overlap_resolve  → ``overlap.resolve``（默认 True）
    gnd_cluster      → ``gnd_distribution.enabled``（默认 False）
    parallel_short   → ``gnd_distribution.parallel_short``（默认 True）
    three_stage_stub → ``routing.three_stage_stub``（默认 True，顶层）
    wire_simplify    → ``wire_simplify.enabled``（默认 False）
    text_layout      → ``text_layout.enabled``（默认 False）
  ``enabled=True`` → 应用完整 params + 写 ``ctx.routed_nets`` 摘要，返回 True
  （feature 已接管）；``enabled=False`` → 不应用、不写 ctx，返回 False。
- 链内**任意启用插件**应用完整 params → 与 legacy 全量应用一致；全部禁用/
  空链 → 不应用（全局 config 保持默认/调用方预置，与 legacy 默认 params 等价）。

ctx 契约（PluginSpec.writes_keys = ``("routed_nets",)``）：
- 插件写 ``ctx.routed_nets`` 摘要 dict：``{"applied_plugins": [...],
  "skipped_plugins": [...], "enabled": True}``（可观测性；只读守卫放行）。
- 全局 ``config.routing`` 修改属于引擎级副作用（非 ctx 字段赋值，守卫不拦截）。
"""

from __future__ import annotations

import logging
from typing import Any

from ..context import ConversionContext
from ..hookspecs import hookimpl

logger = logging.getLogger(__name__)

__all__ = ["BeautifyPlugin"]


class BeautifyPlugin:
    """美化插件基类（配置编排委托 + yaml 参数应用）。

    子类只需设置 ``name`` / ``description`` 并实现
    ``_enabled_from_params``（从构造 params 判定 feature 是否启用）。
    """

    name: str = ""
    description: str = ""

    def __init__(self, engine: Any = None, **params: Any) -> None:
        """构造（engine 由 PluginManager 注入；其余来自 beautify.params）。"""
        self.engine = engine
        self.params = params
        self.enabled = bool(self._enabled_from_params(params))
        self.order_trace: list[str] = []

    # ── 子类契约 ─────────────────────────────────────────────────────

    def _enabled_from_params(self, params: dict[str, Any]) -> bool:
        """从构造 params 判定 feature 是否启用（子类实现）。"""
        raise NotImplementedError

    # ── 钩子实现 ─────────────────────────────────────────────────────

    @hookimpl
    def beautify(self, ctx: ConversionContext) -> bool | None:
        """美化钩子链（S5 真实现：enabled → 应用 params → 写 ctx 摘要）。

        - 先记录执行顺序（``order_trace``，S2 顺序观测契约）。
        - enabled=False → 不应用、返回 False（feature 关）。
        - enabled=True → 委托 engine 应用完整 ``beautify.params`` 到全局
          ``config.routing``（writer 读取），写 ``ctx.routed_nets`` 摘要，
          返回 True（已接管）。
        """
        self.order_trace.append(self.name)
        if not self.enabled:
            self._record_skipped(ctx)
            return False
        if self.engine is None:
            logger.warning("beautify 插件 %s 无 engine 注入 — 跳过", self.name)
            self._record_skipped(ctx)
            return False
        self.engine.apply_beautify_params(ctx)
        self._record_applied(ctx)
        return True

    # ── ctx 摘要（可观测性） ─────────────────────────────────────────

    def _record_applied(self, ctx: ConversionContext) -> None:
        summary = dict(ctx.routed_nets or {})
        applied = list(summary.get("applied_plugins", []))
        if self.name not in applied:
            applied.append(self.name)
        summary["applied_plugins"] = applied
        summary.setdefault("skipped_plugins", [])
        summary["enabled"] = True
        ctx.routed_nets = summary

    def _record_skipped(self, ctx: ConversionContext) -> None:
        summary = dict(ctx.routed_nets or {})
        skipped = list(summary.get("skipped_plugins", []))
        if self.name not in skipped:
            skipped.append(self.name)
        summary["skipped_plugins"] = skipped
        summary.setdefault("applied_plugins", [])
        ctx.routed_nets = summary

    # ── 可逆卸载（Cordis unload 理念） ───────────────────────────────

    def cleanup(self) -> None:
        """复位状态（幂等）；engine 引用释放。"""
        self.enabled = False
        self.engine = None
        self.params = {}
