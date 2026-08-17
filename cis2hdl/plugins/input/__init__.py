"""input 阶段插件包（FR1）。

S3：5 个真实现插件（edif/dsn/cross_ref/pstxnet/pstchip），load_input 接管
解析（返回 True）；引擎 post-chain ``_finalize_plugin_input`` 统一做
PST 汇总 + catalog 重建 + 副作用暴露，保证默认 profile 与 legacy 字节等价
（FR9）。``_SPECS`` 汇总（供 discover 读取）。
"""

from __future__ import annotations

from ..spec import PluginSpec
from . import cross_ref, dsn, edif, pstchip, pstxnet

_SPECS: list[PluginSpec] = [
    edif.PLUGIN,
    dsn.PLUGIN,
    cross_ref.PLUGIN,
    pstxnet.PLUGIN,
    pstchip.PLUGIN,
]

__all__ = ["_SPECS", "edif", "dsn", "cross_ref", "pstxnet", "pstchip"]
