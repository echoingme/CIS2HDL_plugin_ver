"""PipelineHooks — CIS2HDL 插件契约（S2 §3.6，7 个 hook）。

设计依据：``docs/S2-plugin-base-design.md`` §3.6。

约定：
- 所有 hook 均 ``firstresult=False``（多插件链式协作，每个都要执行）。
- 返回值语义：
  - ``load_input`` / ``match_components`` / ``apply_manual_overrides`` / ``beautify``
    返回 ``bool|None``（True=已处理，None/False=未处理→引擎 legacy fallback）
  - ``write_output`` / ``write_report`` 返回 ``list[Path]|None``（写出的文件路径）
  - ``run_verification`` 返回 ``list[str]|None``（验证结果）
- 有序 hook（load_input/match_components/beautify）由 PluginManager **逆序注册**
  保证 yaml 顺序执行（D1：单 hook + 逆序注册 + LIFO 反转）；其 hookimpl
  **禁止** tryfirst/trylast。
- 插件通过 ``ctx`` 读写数据；写哪些字段由 ``PluginSpec.writes_keys`` 声明
  （只读守卫只保护字段赋值，不保护可变对象内部原地修改）。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pluggy import HookimplMarker, HookspecMarker

if TYPE_CHECKING:
    from .context import ConversionContext

PROJECT_NAME = "cis2hdl"

hookspec = HookspecMarker(PROJECT_NAME)
hookimpl = HookimplMarker(PROJECT_NAME)


class PipelineHooks:
    """CIS2HDL 插件契约（7 hook）。"""

    # ── FR1 输入解析 ──────────────────────────────────────────────────

    @hookspec(firstresult=False)
    def load_input(self, ctx: "ConversionContext") -> bool | None:
        """载入并解析一种输入格式/数据源（EDIF/DSN/CrossRef/pstxnet/pstchip）。

        S3 语义（真实现）：解析编排器（edif/dsn）返回 True 并写 ctx.ir；
        增量插件（cross_ref/pstxnet/pstchip）在 ctx.ir 就绪后增强
        design.metadata；全部返回 False/None → 引擎回退 legacy 内联解析块。
        插件链执行后引擎 post-chain ``_finalize_plugin_input`` 统一做
        PST 汇总 + catalog 重建 + 副作用暴露（FR9 字节等价）。
        """

    # ── FR2/FR3 元件匹配 ──────────────────────────────────────────────

    @hookspec(firstresult=False)
    def match_components(self, ctx: "ConversionContext") -> bool | None:
        """对 ctx.ir 做元件匹配（S4 拆分 exact/fuzzy/passive/fallback）。

        S2 语义：默认 matcher_pipeline 薄包装真委托 engine.match()，
        返回 True。
        """

    @hookspec(firstresult=False)
    def apply_manual_overrides(self, ctx: "ConversionContext") -> bool | None:
        """应用手动匹配/强制 mock（chip_config 插件化，FR3）。

        S2 语义：默认 manual_overrides 薄包装真委托
        engine._apply_phase14_matching()，返回 True。
        """

    # ── FR4 布线美化（每美化功能一个插件）──────────────────────────────

    @hookspec(firstresult=False)
    def beautify(self, ctx: "ConversionContext") -> bool | None:
        """美化钩子链：overlap_resolve/gnd_cluster/parallel_short/
        three_stage_stub/wire_simplify/text_layout，按 yaml 顺序执行。

        S5 语义（真实现，配置编排）：插件在 generate 之前把 yaml
        ``beautify.params``（RoutingConfig，S1 K1 复用）应用到全局
        ``config.routing``（``engine.apply_beautify_params``）—— writer
        内置美化逻辑（overlap_resolver/gnd_cluster_planner/wire_simplifier/
        wire_layout/text_layout）按配置开关在正确阶段执行，顺序由 writer
        内部保证（overlap 在 pin 几何前、gnd/parallel 在布线前、
        wire_simplify 布线后、text_layout 末尾）。每插件 enabled 门来自
        自身 params（见 ``beautify/_base.py``）：enabled → 应用完整 params
        + 写 ``ctx.routed_nets`` 摘要 + 返回 True；disabled → 返回 False。
        空链/全禁用 → 无人处理 → no-op（全局 config 保持默认/预置，FR9）。
        """

    # ── FR5 输出 ──────────────────────────────────────────────────────

    @hookspec(firstresult=False)
    def write_output(self, ctx: "ConversionContext") -> list[Path] | None:
        """写一种输出文件（S6 拆分 csa/con/xcon/csv/cpc/cpm/cds_lib）。

        S2 语义：默认 default_writer 薄包装真委托 engine.generate()
        （一次写全部文件），返回路径列表。
        """

    @hookspec(firstresult=False)
    def write_report(self, ctx: "ConversionContext") -> list[Path] | None:
        """写一种报告（aesthetic/ioport/mapping/error…）。

        S2 语义：默认 reports 薄包装真委托报告块（mapping csv/top3/
        错误日志/html），返回路径列表。
        """

    # ── FR6 测试（不在 convert() 内调用；S8 接入）─────────────────────

    @hookspec(firstresult=False)
    def run_verification(self, ctx: "ConversionContext") -> list[str] | None:
        """执行一类验证/测试（unit/e2e/qa-package）。S2 仅定义。"""
