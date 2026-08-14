"""ConversionContext — 插件间唯一通信通道 + 只读守卫（S2 §3.4）。

设计依据：``docs/S2-plugin-base-design.md`` §3.4。

只读守卫语义：
- **字段级**保护：插件声明 ``PluginSpec.writes_keys``；PluginHost 在调用前后
  快照非声明字段，被**赋值**（引用变化）→ warning（``strict_ctx=True`` 时 raise）。
- **仅保护字段赋值，不保护可变对象内部原地修改**——如 ``ctx.report.warnings``
  append 合法（报告聚合需要）；``ctx.ir`` 整体替换非法（除非声明 writes_keys）。
- 比较用**同一性**（``is``）：原地修改不改变引用，天然放行。
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from ..core.config import RoutingConfig  # noqa: F401 — 仅类型注解
    from ..core.engine.conversion_engine import ConversionReport
    from ..core.ir.design import DesignIR
    from ..core.ir.match import MatchResult
    from ..core.db.component_db import ComponentDB
    from ..core.pipeline_config import PipelineConfig

__all__ = ["ConversionContext", "ReadOnlyViolation"]


class ReadOnlyViolation(RuntimeError):
    """插件在未声明的 ctx 字段上做了赋值（strict_ctx=True 时抛出）。"""


@dataclass
class ConversionContext:
    """插件间唯一通信通道（仿 Cordis ctx.*；方案 §3.2 落实）。

    字段：
        cfg              S1 PipelineConfig（beautify.params 复用 RoutingConfig）
        profile          当前 profile 名
        input_files      Stage1 输入文件列表
        output_dir       输出目录（engine.output_dir）
        ir               Stage2 产物（load_input 写入）
        hdl_db           Stage3 产物（scan，引擎内部写）
        matches          Stage4 产物
        manual_overrides FR3 手动匹配
        routed_nets      美化阶段共享（S5）
        report           报告聚合（ConversionReport 超集）
    """

    cfg: "PipelineConfig"
    profile: str = "default"
    input_files: list[Path] = field(default_factory=list)
    output_dir: Path | None = None
    ir: "DesignIR | None" = None
    hdl_db: "ComponentDB | None" = None
    matches: list["MatchResult"] = field(default_factory=list)
    manual_overrides: dict[str, Any] = field(default_factory=dict)
    routed_nets: dict[str, Any] | None = None
    report: "ConversionReport" = field(default_factory=lambda: _new_report())

    # ── 只读守卫内部状态 ─────────────────────────────────────────────
    _locked: set[str] = field(default_factory=set, repr=False, compare=False)
    _snapshot: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    # ── 只读守卫：快照 / 校验 / writable ─────────────────────────────

    def _snapshot_fields(self, keys: set[str]) -> None:
        """快照指定字段的当前引用（守卫比较基准）。

        同时**重置** ``_locked``（writable() 声明）——新一轮插件调用
        从干净状态开始，避免上一插件的声明泄漏到下一插件。
        """
        self._snapshot = {k: getattr(self, k) for k in keys if hasattr(self, k)}
        self._locked.clear()

    def _verify_unchanged(self, allowed: set[str], strict: bool) -> list[str]:
        """检查被非法**赋值**的字段（引用变化），返回字段名列表。

        - 只比较快照过的字段（PluginHost 调用前已快照）
        - ``allowed``（writes_keys）∪ ``_locked``（writable() 临时声明）豁免
        - ``strict=True`` 时抛 :class:`ReadOnlyViolation`
        """
        allowed = set(allowed) | self._locked
        violated: list[str] = []
        for key, old in self._snapshot.items():
            if key in allowed:
                continue
            if getattr(self, key) is not old:
                violated.append(key)
        if violated and strict:
            raise ReadOnlyViolation(
                f"插件越权写 ctx 字段（未在 writes_keys 声明）: {sorted(violated)}"
            )
        return violated

    @contextlib.contextmanager
    def writable(self, *keys: str) -> Iterator["ConversionContext"]:
        """临时声明可写字段（插件内部细粒度控制）。

        Usage::

            with ctx.writable("ir"):
                ctx.ir = new_ir

        声明在**本次插件调用期间持续生效**（``_locked`` 并集进
        ``_verify_unchanged`` 的允许集）；下一插件调用前
        ``_snapshot_fields`` 会重置 ``_locked``，保证不泄漏。
        """
        for key in keys:
            self._locked.add(key)
        try:
            yield self
        finally:
            # 有意**不**在退出时移除：PluginHost 在调用后的 finally 校验
            # 需要看到本次调用期间的全部 writable 声明。
            pass


def _new_report() -> "ConversionReport":
    """惰性构造 ConversionReport（避免模块导入期循环依赖）。"""
    from ..core.engine.conversion_engine import ConversionReport

    return ConversionReport()
