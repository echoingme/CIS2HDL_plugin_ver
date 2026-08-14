"""overlap_resolve 美化插件（FR4）。S2 占位：顺序记录 + enabled 感知 → False。"""

from __future__ import annotations

from .._stubs import make_beautify_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="overlap_resolve",
    stage="beautify",
    description="防重叠（默认；S5 真实现）",
    cls=make_beautify_stub("overlap_resolve"),
    module=__name__,
    param_section="overlap",
    param_fields=("check", "resolve", "avoid_margin"),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
