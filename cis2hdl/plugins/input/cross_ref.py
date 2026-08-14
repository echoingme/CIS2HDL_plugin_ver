"""CrossRef CSV 输入插件（FR1）。S2 占位：load_input → False（S3 真实现）。"""

from __future__ import annotations

from .._stubs import make_input_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="cross_ref",
    stage="input",
    description="CrossRef CSV（可选；S3 真实现）",
    cls=make_input_stub("cross_ref"),
    module=__name__,
    writes_keys=("ir",),
)
