"""mapping 报告插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/mapping_csv_writer.py``
（``{project}_mapping.csv`` + ``{project}_top3.txt``，legacy
``_legacy_reports`` 前两步）。插件编排调用
``MappingCSVWriter.write`` + ``write_top3_file``，不重写生成逻辑。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputReportPlugin

__all__ = ["MappingReportPlugin", "PLUGIN"]


class MappingReportPlugin(OutputReportPlugin):
    """mapping 报告（默认；MappingCSVWriter + Top3 编排）。"""

    name = "mapping"
    description = "mapping 报告（默认；MappingCSVWriter + write_top3_file 编排）"

    def _write_report(self, ctx: ConversionContext) -> list[Any]:
        from cis2hdl.core.writer.mapping_csv_writer import (
            MappingCSVWriter,
            write_top3_file,
        )

        input_path: Path = (
            ctx.input_files[0] if ctx.input_files else Path("")
        )
        project_name: str = ctx.report.project_name or input_path.stem

        mapping_csv_path = ctx.output_dir / f"{project_name}_mapping.csv"
        MappingCSVWriter.write(
            mapping_csv_path,
            ctx.ir,
            ctx.matches,
            ctx.report,
            ctx.output_dir,
            input_path,
        )

        top3_path = ctx.output_dir / f"{project_name}_top3.txt"
        # sources 不需要 —— 数据在 MatchResult.extra_data（legacy 同参）。
        write_top3_file(top3_path, [], ctx.matches)

        return [mapping_csv_path, top3_path]


PLUGIN = PluginSpec(
    name="mapping",
    stage="output",
    description=MappingReportPlugin.description,
    cls=MappingReportPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
