"""wire_simplify 美化插件（FR4 / Phase XVII M4）。S2 占位：顺序记录 + enabled 感知 → False。"""

from __future__ import annotations

from .._stubs import make_beautify_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="wire_simplify",
    stage="beautify",
    description="电线化简（默认关；S5 真实现）",
    cls=make_beautify_stub("wire_simplify"),
    module=__name__,
    param_section="wire_simplify",
    param_fields=("enabled",),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
