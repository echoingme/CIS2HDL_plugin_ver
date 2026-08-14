"""pstxnet 网络注入插件（FR1）。S2 占位：load_input → False（S3 真实现）。"""

from __future__ import annotations

from .._stubs import make_input_stub
from ..spec import PluginSpec

PLUGIN = PluginSpec(
    name="pstxnet",
    stage="input",
    description="pstxnet 网络注入（默认；S3 真实现）",
    cls=make_input_stub("pstxnet"),
    module=__name__,
    writes_keys=("ir",),
)
