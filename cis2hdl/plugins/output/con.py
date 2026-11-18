"""con 输出文件插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/con_writer.py``（S-Expr 约束文件
<cell>.con）。插件编排调用 ``ConWriter().write_with_manager(conn, mgr)``，
不重写生成逻辑。
"""

from __future__ import annotations

from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputFilePlugin

__all__ = ["ConOutputPlugin", "PLUGIN"]


class ConOutputPlugin(OutputFilePlugin):
    """con 约束文件（S-Expr；ConWriter 编排）。"""

    name = "con"
    description = "con 约束文件（默认；ConWriter.write_with_manager 编排）"

    def _write(self, ctx: ConversionContext, mgr: Any, conn: Any) -> list[Any]:
        from cis2hdl.core.writer.con_writer import ConWriter

        return ConWriter().write_with_manager(conn, mgr)


PLUGIN = PluginSpec(
    name="con",
    stage="output",
    description=ConOutputPlugin.description,
    cls=ConOutputPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
