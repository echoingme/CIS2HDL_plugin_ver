"""input 阶段插件包（FR1）。

S2：5 个占位 stub（load_input → False 回退 legacy）；S3 逐个替换真实现。
``_SPECS`` 汇总（供 discover 读取）。
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
