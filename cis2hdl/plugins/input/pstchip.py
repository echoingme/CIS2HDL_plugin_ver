"""pstchip 引脚名恢复插件（FR1）。S2 占位：load_input → False（S3 真实现）。"""

from __future__ import annotations

from .._stubs import make_input_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="pstchip",
    stage="input",
    description="pstchip 引脚名恢复（默认；S3 真实现）",
    cls=make_input_stub("pstchip"),
    module=__name__,
    writes_keys=("ir",),
)
