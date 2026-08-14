"""three_stage_stub 美化插件（FR4 / Phase XV R5）。S2 占位：顺序记录 + enabled 感知 → False。

参数源 = RoutingConfig **顶层**（param_section=""，S1 K1 复用）。
"""

from __future__ import annotations

from .._stubs import make_beautify_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="three_stage_stub",
    stage="beautify",
    description="三段式 stub（默认开；S5 真实现）",
    cls=make_beautify_stub("three_stage_stub"),
    module=__name__,
    param_section="",
    param_fields=("three_stage_stub",),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
