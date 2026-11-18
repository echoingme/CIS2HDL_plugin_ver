"""output 阶段插件基类（S6：7 文件插件 + 4 报告插件共用）。

设计依据：``docs/S2-plugin-base-design.md`` §3.5/§3.6 与 S4/S5 插件模式
（``docs/developer-guide.md`` S6 章节）。

铁律（FR9 默认等价 + FR2 细粒度独立启停 + NFR3 不重写输出逻辑）：

- **输出逻辑仍在 writer 模块**：``csa_writer`` / ``con_writer`` /
  ``xcon_writer`` / ``csv_writer`` / ``cpc_writer`` / ``output_manager``
  （cpm/cds_lib）/ ``mapping_csv_writer`` / ``error_logger`` 保持原实现，
  插件**不搬运、不重写**任何写文件算法。
- **插件职责 = 编排调用**：在 ``write_output`` / ``write_report`` 钩子中
  于正确时机调用 writer 子步骤，返回写出的文件路径（list[Path]|None）。
- **细粒度独立启停**：每个插件独立文件模块；``output.files`` /
  ``output.reports`` 控制启停（Manager ``_enabled_by_cfg`` 按名过滤）。
- **默认 profile 全开 = legacy 全文件**：7 文件 + 4 报告插件全启用时，
  引擎按 legacy 顺序聚合输出（``_OUTPUT_GROUP_ORDER``）→ 字节等价。

ctx 契约（PluginSpec.writes_keys = ``()``）：
- 插件**不写** ctx 字段（只读）；写出的路径经返回值交给引擎聚合。
- 插件内部可原地修改 ``ctx.report``（append errors/warnings —— 只读守卫
  只保护字段**赋值**，不保护可变对象内部修改）。
- 共享基础设施（OutputManager / DesignConnectivity / 目录 / hdl_lib /
  支撑文件）由引擎 ``engine._output_stage_shared`` 惰性构建一次。
"""

from __future__ import annotations

import logging
from typing import Any

from ..context import ConversionContext
from ..hookspecs import hookimpl

logger = logging.getLogger(__name__)

__all__ = ["OutputFilePlugin", "OutputReportPlugin"]


class OutputFilePlugin:
    """输出**文件**插件基类（write_output 钩子，S6）。

    子类只需设置 ``name`` / ``description`` 并实现
    ``_write(ctx, mgr, conn) -> list[Path]``（写对应文件并返回路径）。
    """

    name: str = ""
    description: str = ""

    def __init__(self, engine: Any = None, **params: Any) -> None:
        """构造（engine 由 PluginManager 注入；其余构造参数当前无使用）。"""
        self.engine = engine
        self.params = params
        self.order_trace: list[str] = []

    # ── 子类契约 ─────────────────────────────────────────────────────

    def _write(self, ctx: ConversionContext, mgr: Any, conn: Any) -> list[Any]:
        """写本插件负责的文件（子类实现）；返回路径列表。"""
        raise NotImplementedError

    # ── 钩子实现 ─────────────────────────────────────────────────────

    @hookimpl
    def write_output(self, ctx: ConversionContext) -> list[Any] | None:
        """write_output 钩子（S6 真实现：编排 writer 子步骤 → 返回路径）。

        - 前置未就绪（ctx.ir/output_dir 缺失 / 无 engine）→ 返回 []（本
          插件无产出；pluggy 会丢弃 None 返回值导致引擎聚合错位，故统一
          返回列表）。
        - 复用引擎共享输出状态（_output_stage_shared，惰性幂等）。
        - 单插件失败 → warning + ctx.report.errors 记录 + 返回 []（NFR3
          独立降级，不触发 legacy fallback、不阻断其它文件插件）。
        """
        self.order_trace.append(self.name)
        if ctx is None or self.engine is None:
            return []
        if ctx.ir is None or ctx.output_dir is None:
            return []
        try:
            mgr, conn, _infra = self.engine._output_stage_shared(
                ctx.ir, ctx.matches, ctx.output_dir, ctx.report,
            )
        except Exception as exc:  # noqa: BLE001 — NFR3 降级
            logger.warning("output 插件 %s 共享阶段失败: %s", self.name, exc)
            return []
        try:
            paths = self._write(ctx, mgr, conn) or []
            return [p for p in paths if p is not None]
        except Exception as exc:  # noqa: BLE001 — NFR3 独立降级
            logger.warning("output 插件 %s 写文件失败: %s", self.name, exc)
            ctx.report.errors.append(f"output 插件 {self.name} 写文件失败: {exc}")
            return []

    # ── 可逆卸载（Cordis unload 理念） ───────────────────────────────

    def cleanup(self) -> None:
        """复位状态（幂等）；engine 引用释放。"""
        self.engine = None
        self.params = {}


class OutputReportPlugin:
    """输出**报告**插件基类（write_report 钩子，S6）。

    子类只需设置 ``name`` / ``description`` 并实现
    ``_write_report(ctx) -> list[Path]``（写对应报告并返回路径）。
    """

    name: str = ""
    description: str = ""

    def __init__(self, engine: Any = None, **params: Any) -> None:
        self.engine = engine
        self.params = params
        self.order_trace: list[str] = []

    # ── 子类契约 ─────────────────────────────────────────────────────

    def _write_report(self, ctx: ConversionContext) -> list[Any]:
        """写本插件负责的报告（子类实现）；返回路径列表。"""
        raise NotImplementedError

    # ── 钩子实现 ─────────────────────────────────────────────────────

    @hookimpl
    def write_report(self, ctx: ConversionContext) -> list[Any] | None:
        """write_report 钩子（S6 真实现：编排报告 writer → 返回路径）。

        前置未就绪 → []（pluggy 丢弃 None 返回值，统一返回列表）；
        单插件失败 → warning + errors + []（NFR3）。
        """
        self.order_trace.append(self.name)
        if ctx is None or ctx.output_dir is None or ctx.report is None:
            return []
        try:
            paths = self._write_report(ctx) or []
            return [p for p in paths if p is not None]
        except Exception as exc:  # noqa: BLE001 — NFR3 独立降级
            logger.warning("report 插件 %s 写报告失败: %s", self.name, exc)
            ctx.report.errors.append(f"report 插件 {self.name} 写报告失败: {exc}")
            return []

    # ── 可逆卸载 ─────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """复位状态（幂等）；engine 引用释放。"""
        self.engine = None
        self.params = {}
