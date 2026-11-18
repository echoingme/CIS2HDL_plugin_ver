"""cpc 输出文件插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/cpc_writer.py``（页级 pageN.cpc
cell property 文件）。插件编排调用
``CpcWriter().write_all_with_manager(conn, mgr)``，不重写生成逻辑。
"""

from __future__ import annotations

from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputFilePlugin

__all__ = ["CpcOutputPlugin", "PLUGIN"]


class CpcOutputPlugin(OutputFilePlugin):
    """cpc 页级 property 文件（默认；CpcWriter 编排）。"""

    name = "cpc"
    description = "cpc 页级 property 文件（默认；CpcWriter.write_all_with_manager 编排）"

    def _write(self, ctx: ConversionContext, mgr: Any, conn: Any) -> list[Any]:
        from cis2hdl.core.writer.cpc_writer import CpcWriter

        return CpcWriter().write_all_with_manager(conn, mgr)


PLUGIN = PluginSpec(
    name="cpc",
    stage="output",
    description=CpcOutputPlugin.description,
    cls=CpcOutputPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
