"""parallel_short 美化插件（FR4）。S2 占位：顺序记录 + enabled 感知 → False。"""

from __future__ import annotations

from .._stubs import make_beautify_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="parallel_short",
    stage="beautify",
    description="并联优化（默认；S5 真实现）",
    cls=make_beautify_stub("parallel_short"),
    module=__name__,
    param_section="gnd_distribution",
    param_fields=("parallel_short", "parallel_short_dist"),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
