"""csa 输出文件插件（FR5 / S6）。

对应 writer 模块：``cis2hdl/core/writer/csa_writer.py``（CSA 页文件生成，
Phase XXIII 核心）。插件**编排调用**（不重写 CSA 逻辑）：

- ``cfg.app.emit_csa_wires`` 开启 → ``CSAWriter.write_all_with_conn(conn, mgr)``
  （共享连通性模型；含 LASTPIN/WIRE/DOT/SIG_NAME）。
- 关闭 → legacy ``CSAWriter.write_with_manager(page, mgr)`` 逐页（原
  generate() 分支，字节等价）。

CSAWriter 侧效应（占位符号 / 模拟图标 / aesthetic_report.txt /
ioport_audit_report.txt）由 writer 内部在写页过程中完成——本插件不干预
内容，只按 ``output.reports`` 成员关系**门控**诊断报告写出：

- ``"aesthetic"`` 不在 ``output.reports`` → 抑制 aesthetic_report.txt
  （临时把 routing.report.aesthetic / routing.aesthetic.report 置 False）。
- ``"ioport"`` 不在 ``output.reports`` → 抑制 ioport_audit_report.txt
  （临时把 routing.report.ioport_audit / routing.ioport.audit 置 False）。

默认 profile（reports 全 4）→ 不抑制 → 与 legacy 逐字节等价（FR9）。
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from ..context import ConversionContext
from ..spec import PluginSpec
from ._base import OutputFilePlugin

logger = logging.getLogger(__name__)

__all__ = ["CsaOutputPlugin", "PLUGIN"]


class CsaOutputPlugin(OutputFilePlugin):
    """CSA 页文件（Phase XXIII 核心；csa_writer 编排）。"""

    name = "csa"
    description = (
        "CSA 页文件（默认；CSAWriter 编排 —— emit_csa_wires 门 + "
        "output.reports 门控诊断报告侧效应）"
    )

    def _write(self, ctx: ConversionContext, mgr: Any, conn: Any) -> list[Any]:
        from cis2hdl.core.config import config as _cfg

        from cis2hdl.core.writer.csa_writer import CSAWriter

        reports: list[str] = list(ctx.cfg.output.reports) if ctx.cfg else []
        routing_cfg = _cfg.routing
        if "aesthetic" not in reports or "ioport" not in reports:
            # 门控诊断报告：复制 routing 配置（不改全局），writer 内部按
            # 配置开关决定是否创建收集器/写出报告（复用原逻辑，不重写）。
            routing_cfg = copy.deepcopy(routing_cfg)
            if "aesthetic" not in reports:
                routing_cfg.aesthetic.report = False
                routing_cfg.report.aesthetic = False
            if "ioport" not in reports:
                routing_cfg.report.ioport_audit = False
                routing_cfg.ioport.audit = False

        engine = self.engine
        csa_writer = CSAWriter(
            hdl_lib_name=_cfg.output.hdl_lib_dir or "hdl_lib",
            hdl_lib_path=getattr(engine, "_last_hdl_lib_path", None),
            routing_cfg=routing_cfg,
        )
        hdl_db = getattr(engine, "_hdl_db", None) or ctx.hdl_db
        if hdl_db:
            csa_writer._component_db = hdl_db
        if hasattr(csa_writer, "set_matches"):
            csa_writer.set_matches(ctx.matches)
        # Phase XVIII R4: CrossRef CSV 属性注入（缺失时回退 props）。
        if hasattr(csa_writer, "set_crossref_map"):
            csa_writer.set_crossref_map(
                getattr(engine, "_last_cross_ref_map", None) or {}
            )

        if _cfg.app.emit_csa_wires:
            return csa_writer.write_all_with_conn(conn, mgr)
        # emit_csa_wires 关闭 → legacy 逐页分支（原 generate() 语义）。
        from cis2hdl.core.writer.csa_writer import CSAWriter as _LegacyCSA

        legacy = _LegacyCSA()
        files: list[Any] = []
        for page in ctx.ir.pages:
            files.extend(legacy.write_with_manager(page, mgr))
        return files


PLUGIN = PluginSpec(
    name="csa",
    stage="output",
    description=CsaOutputPlugin.description,
    cls=CsaOutputPlugin,
    module=__name__,
    writes_keys=(),
    requires=("ir", "matches"),
    builtin=True,
)
