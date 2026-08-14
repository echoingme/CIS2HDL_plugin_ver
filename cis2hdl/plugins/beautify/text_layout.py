"""text_layout 美化插件（FR4 / Phase XIV D1）。S2 占位：顺序记录 + enabled 感知 → False。"""

from __future__ import annotations

from .._stubs import make_beautify_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="text_layout",
    stage="beautify",
    description="文本/标签去冲突（默认关；S5 真实现）",
    cls=make_beautify_stub("text_layout"),
    module=__name__,
    param_section="text_layout",
    param_fields=("enabled",),
    writes_keys=("routed_nets",),
    requires=("ir", "matches"),
)
