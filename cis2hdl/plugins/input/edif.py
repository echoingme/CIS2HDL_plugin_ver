"""EDIF 输入插件（FR1，默认）。

S3 真实现：默认解析编排器。插件通过 ``engine``（构造注入）编排调用引擎
子步骤（薄包装，不重写解析逻辑）：

1. ``engine._resolve_parse_path`` —— P0-D2：``.dsn`` 且禁用 DSN 元件源时
   优先同名的 ``.EDF/.edf`` 兄弟文件（与 legacy 一致）。
2. ``engine._stage_parse`` —— ParserRegistry 按扩展名选 EDIF/DSN 解析器
   （EDIFParser/DSNParser 原样复用）。
3. ``engine._log_parse_statistics`` —— 页解析统计。
4. cross_ref / pst 子步骤按"增量插件是否启用"委托或内联：
   - ``cross_ref`` 插件未启用 → 内联 ``_load_cross_ref_csv``（legacy 行为；
     保证默认 profile 即使不含 cross_ref 也与 legacy 等价，FR9）。
   - ``pstxnet``/``pstchip`` 插件未启用 → 内联 ``_load_pst_files``（只加载
     未覆盖文件；``log_summary=False``，PST 汇总事件由引擎 post-chain
     ``_finalize_plugin_input`` 统一输出一次，事件流与 legacy 一致）。

返回 True 表示接管解析（ctx.ir 已写）；返回 False → 引擎回退 legacy 全链。
"""

from __future__ import annotations

from typing import Any

from ..hookspecs import hookimpl
from ..context import ConversionContext
from ..spec import PluginSpec

__all__ = ["EdifInputPlugin", "PLUGIN"]


class EdifInputPlugin:
    """EDIF 输入插件（默认解析编排器，S3 真实现）。

    依赖：``engine`` 由 PluginManager 构造注入（``resolve_params`` 检测
    构造签名含 ``engine`` 参数）。
    """

    def __init__(self, engine: Any = None, **kwargs: Any) -> None:
        self.name = "edif"
        self.engine = engine
        self.params = kwargs

    @hookimpl
    def load_input(self, ctx: ConversionContext) -> bool | None:
        if ctx is None or ctx.ir is not None:
            return False  # 已被其他解析插件接管（edif/dsn 互斥）
        engine = self.engine
        if engine is None:
            return False
        input_path = ctx.input_files[0] if ctx.input_files else None
        if input_path is None:
            return False

        parse_path = engine._resolve_parse_path(input_path)
        design = engine._stage_parse(parse_path, ctx.report, None)
        if design is None:
            return False
        ctx.ir = design
        engine._log_parse_statistics(design)

        cfg = ctx.cfg
        plugins = list(cfg.input.plugins) if cfg is not None else []

        # cross_ref 子步骤：cross_ref 插件未启用 → 内联（legacy 行为）
        if "cross_ref" not in plugins:
            engine._load_cross_ref_csv(design, input_path)

        # pst 子步骤：pstxnet/pstchip 插件未启用 → 对应文件内联
        # （log_summary=False：汇总事件由 post-chain 统一输出一次）
        pst_keys: list[str] = []
        if "pstxnet" not in plugins:
            pst_keys += ["pstxprt", "pstxnet"]
        if "pstchip" not in plugins:
            pst_keys += ["pstchip"]
        if pst_keys:
            engine._load_pst_files(design, input_path, keys=pst_keys, log_summary=False)

        return True

    def cleanup(self) -> None:
        self.engine = None
        self.params = {}


PLUGIN = PluginSpec(
    name="edif",
    stage="input",
    description="EDIF 解析（默认；P0-D2 EDIF 优先 + 完整 legacy 等价编排）",
    cls=EdifInputPlugin,
    module=__name__,
    writes_keys=("ir",),
    requires=(),
    builtin=True,
)
