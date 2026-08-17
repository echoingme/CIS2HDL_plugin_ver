"""pstxnet 网络注入插件（FR1，默认）。

S3 真实现：载入同目录 ``pstxprt.dat`` + ``pstxnet.dat`` → 写入
``design.metadata["pst_data"]``（键 ``pstxprt``/``pstxnet``）。

- ``pstxprt.dat``（PstxnetParser）：INS→refdes 桥接 + pstxnet_entries
  （catalog 重建的 EDIF 占位实例方位保留、pstchip 查找构建依赖它）。
- ``pstxnet.dat``（PstxnetNetlistParser）：完整 pin→net 连接（Stage 5.5b
  主注入的数据源，下游 convert() 自动消费）。

薄包装编排：调用 ``engine._load_pst_files(keys=["pstxprt", "pstxnet"],
log_summary=False)``（原 legacy Stage 2.3 块，不重写解析逻辑）。
PST 汇总事件由引擎 post-chain 统一输出一次（FR9 事件流一致）。

顺序语义：本插件在 ``edif``/``dsn`` 解析之后执行；``pstchip`` 插件随后
增量载入 ``pstchip.dat``。无文件 → 不接管（返回 False）。
"""

from __future__ import annotations

from typing import Any

from ..hookspecs import hookimpl
from ..context import ConversionContext
from ..spec import PluginSpec

__all__ = ["PstxnetInputPlugin", "PLUGIN"]


class PstxnetInputPlugin:
    """pstxnet 网络注入插件（默认，S3 真实现）。"""

    def __init__(self, engine: Any = None, **kwargs: Any) -> None:
        self.name = "pstxnet"
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
            keys=["pstxprt", "pstxnet"],
            log_summary=False,
        )
        return True

    def cleanup(self) -> None:
        self.engine = None
        self.params = {}


PLUGIN = PluginSpec(
    name="pstxnet",
    stage="input",
    description="pstxnet 网络注入（默认；pstxprt/pstxnet 载入，pin→net 数据源）",
    cls=PstxnetInputPlugin,
    module=__name__,
    writes_keys=("ir",),
    requires=(),
    builtin=True,
)
