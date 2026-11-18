"""cpm 输出文件插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/cpm_writer.py`` / OutputManager
（Cadence DEHDL Project Manager ``<cell>.cpm``，输出根目录）。插件编排
调用 ``OutputManager.write_cpm()``（legacy ``generate_all_project_files``
第一步），不重写生成逻辑。
"""

from __future__ import annotations

from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputFilePlugin

__all__ = ["CpmOutputPlugin", "PLUGIN"]


class CpmOutputPlugin(OutputFilePlugin):
    """cpm Project Manager 文件（默认；OutputManager.write_cpm 编排）。"""

    name = "cpm"
    description = "cpm Project Manager 文件（默认；OutputManager.write_cpm 编排）"

    def _write(self, ctx: ConversionContext, mgr: Any, conn: Any) -> list[Any]:
        return [mgr.write_cpm()]


PLUGIN = PluginSpec(
    name="cpm",
    stage="output",
    description=CpmOutputPlugin.description,
    cls=CpmOutputPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
