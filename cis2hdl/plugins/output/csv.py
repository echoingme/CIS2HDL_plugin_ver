"""csv 输出文件插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/csv_writer.py``（页级 pageN.csv
CONNECTIVITY 文件）。插件编排调用
``PageCsvWriter().write_all_with_manager(conn, mgr)``，不重写生成逻辑。

注意：``{project}_mapping.csv``（MappingCSVWriter）属 **mapping 报告插件**
（output.reports），不在本文件插件范围。
"""

from __future__ import annotations

from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputFilePlugin

__all__ = ["CsvOutputPlugin", "PLUGIN"]


class CsvOutputPlugin(OutputFilePlugin):
    """csv 页级连通性文件（默认；PageCsvWriter 编排）。"""

    name = "csv"
    description = "csv 页级连通性文件（默认；PageCsvWriter.write_all_with_manager 编排）"

    def _write(self, ctx: ConversionContext, mgr: Any, conn: Any) -> list[Any]:
        from cis2hdl.core.writer.csv_writer import PageCsvWriter

        return PageCsvWriter().write_all_with_manager(conn, mgr)


PLUGIN = PluginSpec(
    name="csv",
    stage="output",
    description=CsvOutputPlugin.description,
    cls=CsvOutputPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
