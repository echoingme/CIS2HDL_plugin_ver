"""ioport 报告插件（FR5 / S6，no-op 门）。

对应 writer 模块：``cis2hdl/core/writer/ioport_audit.py``。

S6 语义：``ioport_audit_report.txt`` 由 **csa 插件**在 CSA 生成时写出
（``CSAWriter.write_all_with_conn`` 侧效应，接线/网名/孤立三节；受
``routing.report.ioport_audit`` / ``routing.ioport.audit`` 开关控制）。
本插件是 ``output.reports`` 的**白名单门**：

- 位于 ``output.reports`` → csa 插件不抑制（默认写出，legacy 等价）。
- 不在 ``output.reports`` → csa 插件抑制（report.ioport_audit / 等
  置 False）。

本插件自身 ``write_report`` 返回 ``[]``（报告已随 CSA 侧效应写出，此处
无独立写文件动作；返回值空仍算"已接管"——PluginHost.call_output 语义）。
"""

from __future__ import annotations

from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputReportPlugin

__all__ = ["IoportReportPlugin", "PLUGIN"]


class IoportReportPlugin(OutputReportPlugin):
    """ioport 报告（no-op 门；报告由 csa 插件侧效应写出）。"""

    name = "ioport"
    description = (
        "ioport 报告（no-op 门；ioport_audit_report.txt 由 csa 插件"
        "在 CSA 生成时侧效应写出）"
    )

    def _write_report(self, ctx: ConversionContext) -> list[Any]:
        return []


PLUGIN = PluginSpec(
    name="ioport",
    stage="output",
    description=IoportReportPlugin.description,
    cls=IoportReportPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
