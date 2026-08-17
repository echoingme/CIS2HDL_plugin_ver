"""beautify 阶段插件包（FR4）。

S5：6 个真实现插件（配置编排 —— 在 generate 前把 ``beautify.params``
应用到全局 ``config.routing``，writer 内置美化逻辑在正确阶段执行），
``_SPECS`` 汇总（供 discover 读取）。
"""

from __future__ import annotations

from ..spec import PluginSpec
from . import (
    gnd_cluster,
    overlap_resolve,
    parallel_short,
    text_layout,
    three_stage_stub,
    wire_simplify,
)

_SPECS: list[PluginSpec] = [
    overlap_resolve.PLUGIN,
    gnd_cluster.PLUGIN,
    parallel_short.PLUGIN,
    wire_simplify.PLUGIN,
    three_stage_stub.PLUGIN,
    text_layout.PLUGIN,
]

__all__ = [
    "_SPECS",
    "overlap_resolve",
    "gnd_cluster",
    "parallel_short",
    "wire_simplify",
    "three_stage_stub",
    "text_layout",
]
