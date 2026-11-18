"""error 报告插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/error_logger.py``（ConversionLogger
错误日志 HTML + TXT，legacy ``_legacy_reports`` 第三步）。插件编排调用
``ConversionLogger.write``，不重写生成逻辑。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputReportPlugin

__all__ = ["ErrorReportPlugin", "PLUGIN"]


class ErrorReportPlugin(OutputReportPlugin):
    """error 报告（默认；ConversionLogger 错误日志编排）。"""

    name = "error"
    description = "error 报告（默认；ConversionLogger.write 编排）"

    def _write_report(self, ctx: ConversionContext) -> list[Any]:
        from cis2hdl.core.writer.error_logger import ConversionLogger

        input_path: Path | None = ctx.input_files[0] if ctx.input_files else None
        stem: str = (
            ctx.report.project_name
            or (input_path.stem if input_path is not None else "project")
        )
        log_paths = ConversionLogger.write(ctx.output_dir, stem)
        return list(log_paths)


PLUGIN = PluginSpec(
    name="error",
    stage="output",
    description=ErrorReportPlugin.description,
    cls=ErrorReportPlugin,
    module=__name__,
    writes_keys=(),
    requires=(),
    builtin=True,
)
