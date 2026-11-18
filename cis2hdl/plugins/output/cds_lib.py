"""cds_lib 输出文件插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/cdslib_writer.py`` / OutputManager
（``cds.lib`` 库定义 + ``hdldirect.dat`` + 自包含 ``origin`` 库）。插件编排
调用 ``OutputManager.write_cdslib()`` / ``write_hdldirect_dat()`` /
``write_origin_lib()``（legacy ``generate_all_project_files`` 除 .cpm 外
的其余项目级文件），不重写生成逻辑。
"""

from __future__ import annotations

from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputFilePlugin

__all__ = ["CdsLibOutputPlugin", "PLUGIN"]


class CdsLibOutputPlugin(OutputFilePlugin):
    """cds.lib 库定义（默认；OutputManager 项目级文件编排）。"""

    name = "cds_lib"
    description = (
        "cds.lib 库定义（默认；write_cdslib/write_hdldirect_dat/"
        "write_origin_lib 编排）"
    )

    def _write(self, ctx: ConversionContext, mgr: Any, conn: Any) -> list[Any]:
        files: list[Any] = [
            mgr.write_cdslib(),
            mgr.write_hdldirect_dat(),
            mgr.write_origin_lib(),
        ]
        return files


PLUGIN = PluginSpec(
    name="cds_lib",
    stage="output",
    description=CdsLibOutputPlugin.description,
    cls=CdsLibOutputPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
