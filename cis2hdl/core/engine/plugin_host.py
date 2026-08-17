"""PluginHost — 统一钩子调用器（S2 §4.1）。

设计依据：``docs/S2-plugin-base-design.md`` §4.1。

``call(ctx, hook_name, fallback)`` 语义：
- legacy 模式（``self.engine._pm is None``）→ 直接执行 fallback，返回
  ``(False, fallback())``（默认引擎零 pluggy 开销，等价 FR9）。
- plugin 模式 → 调 ``pm.hook.<hook_name>(ctx=ctx)``：
  - 任一插件返回真值 → ``(True, results)``（fallback **不**执行）
  - 全部返回假/None → fallback 执行 → ``(False, fallback())``
  - hook 抛异常 → warning + fallback → ``(False, fallback())``（NFR3 降级）
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

__all__ = ["PluginHost"]


def _any_truthy(results: list) -> bool:
    """hook 链中任一返回值是真值 → handled。"""
    return any(r for r in results)


class PluginHost:
    """统一钩子调用：hook 链无人处理 → 执行 legacy fallback。"""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def call(
        self,
        ctx: Any,
        hook_name: str,
        fallback: Callable[[], Any],
    ) -> tuple[bool, Any]:
        """返回 (handled: bool, result: Any)。

        - handled=True：插件链处理了该阶段（result = hook 结果列表）。
        - handled=False：fallback 已在方法内执行（result = fallback 返回值）；
          调用方**不得**再次执行 fallback。
        """
        pm = self.engine._pm
        if pm is None:
            return False, fallback()  # legacy 模式
        try:
            results = getattr(pm.hook, hook_name)(ctx=ctx)
        except Exception as exc:  # noqa: BLE001 — NFR3 降级
            logger.warning("hook %s failed: %s — fallback to legacy", hook_name, exc)
            return False, fallback()
        handled = _any_truthy(results)
        if handled:
            return True, results
        return False, fallback()
