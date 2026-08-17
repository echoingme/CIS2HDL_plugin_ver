"""CrossRef CSV 输入插件（FR1，可选，提高转换质量）。

S3 真实现：载入同目录 ``<input>.CSV/.csv`` → 构建 :class:`ComponentCatalog`
（元件身份单一事实源：refdes/value/坐标/页分配）→ 注入坐标到已解析实例。

薄包装编排：调用 ``engine._load_cross_ref_csv``（原 legacy Stage 2.5 块，
不重写解析逻辑）。副作用与原实现一致：
- ``design.metadata["component_catalog"]`` 写入 catalog；
- ``engine._last_cross_ref_map`` 写入 CrossRefParser 结果（backward compat）。

顺序语义：本插件在 ``edif``/``dsn`` 解析之后执行（ctx.ir 已就绪）；catalog
重建由引擎 post-chain ``_finalize_plugin_input`` 统一执行（此时 pst 插件已
载入 pst_data，JEDEC 注入等与 legacy 顺序一致）。

无 CSV → 不接管（返回 False）；有 CSV → 返回 True（增量已应用）。
"""

from __future__ import annotations

from typing import Any

from ..hookspecs import hookimpl
from ..context import ConversionContext
from ..spec import PluginSpec

__all__ = ["CrossRefInputPlugin", "PLUGIN"]


class CrossRefInputPlugin:
    """CrossRef CSV 输入插件（可选，S3 真实现）。"""

    def __init__(self, engine: Any = None, **kwargs: Any) -> None:
        self.name = "cross_ref"
        self.engine = engine
        self.params = kwargs

    @hookimpl
    def load_input(self, ctx: ConversionContext) -> bool | None:
        if ctx is None or ctx.ir is None:
            return False  # 无解析结果 → 不接管（引擎回退 legacy 全链）
        engine = self.engine
        if engine is None:
            return False
        input_path = ctx.input_files[0] if ctx.input_files else None
        if input_path is None:
            return False

        # 薄包装：原 legacy Stage 2.5（CSV → catalog + 坐标注入）。
        # 无 CSV → ({}, None)，无副作用；有 CSV → catalog 写入 metadata。
        _map, _catalog = engine._load_cross_ref_csv(ctx.ir, input_path)
        # catalog 重建由引擎 post-chain _finalize_plugin_input 统一执行
        # （保证 pst_data 已就绪后再重建，顺序与 legacy 一致）。
        return True

    def cleanup(self) -> None:
        self.engine = None
        self.params = {}


PLUGIN = PluginSpec(
    name="cross_ref",
    stage="input",
    description="CrossRef CSV 载入（可选；ComponentCatalog + 坐标注入，提高转换质量）",
    cls=CrossRefInputPlugin,
    module=__name__,
    writes_keys=("ir",),
    requires=(),
    builtin=True,
)
