"""pstchip 引脚名恢复插件（FR1，默认）。

S3 真实现：载入同目录 ``pstchip.dat`` → 写入 ``design.metadata["pst_data"]``
（键 ``pstchip``）。

- ``pstchip.dat``（PstchipParser）：primitive 定义（JEDEC_TYPE/VALUE/pins）。
- 下游消费：
  - catalog 重建的 PST JEDEC 注入（``pst_jedec_type``/``pst_value``/
    ``pst_part_name``，匹配质量提升）；
  - Stage 5.5c 引脚名校验/补位 + ``pstchip_pin_names`` 真实功能名恢复
    （ConnectivityModelBuilder 显示用）。

薄包装编排：调用 ``engine._load_pst_files(keys=["pstchip"], log_summary=False)``
（原 legacy Stage 2.3 块，不重写解析逻辑）。PST 汇总事件由引擎 post-chain
统一输出一次（FR9 事件流一致）。

顺序语义：本插件通常排在 ``pstxnet`` 之后增量载入；无文件 → 不接管
（返回 False）。
"""

from __future__ import annotations

from typing import Any

from ..hookspecs import hookimpl
from ..context import ConversionContext
from ..spec import PluginSpec

__all__ = ["PstchipInputPlugin", "PLUGIN"]


class PstchipInputPlugin:
    """pstchip 引脚名恢复插件（默认，S3 真实现）。"""

    def __init__(self, engine: Any = None, **kwargs: Any) -> None:
        self.name = "pstchip"
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

        engine._load_pst_files(
            ctx.ir, input_path,
            keys=["pstchip"],
            log_summary=False,
        )
        return True

    def cleanup(self) -> None:
        self.engine = None
        self.params = {}


PLUGIN = PluginSpec(
    name="pstchip",
    stage="input",
    description="pstchip 引脚名恢复（默认；pstchip.dat 载入，JEDEC + 真实引脚名）",
    cls=PstchipInputPlugin,
    module=__name__,
    writes_keys=("ir",),
    requires=(),
    builtin=True,
)
