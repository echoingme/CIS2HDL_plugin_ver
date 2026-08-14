"""PinConnectAuditor — M6 引脚连接审计（Phase XVII）。

逐引脚评估连接状态（已接/悬空/网名不匹配/引脚名不匹配），输出
``[PIN_AUDIT]`` / ``[HANGING]`` 报告。数据源 = **DesignConnectivity 模型**
（数据源铁律：不读 csa 输出文本，只消费连接模型）。只读诊断，不影响
CSA 输出内容。

状态定义：
* ``connected``    —— 引脚有网，且该网连接数 > 1（真实连接）；
* ``hanging``      —— 引脚无网（NC）或所在网只有它自己（悬空，待布线）；
* ``net_mismatch`` —— 引脚引用的 net_id 在 conn.nets 中找不到；
* ``pin_mismatch`` —— 实例引脚数/引脚不在匹配 cell 的引脚定义中。

配置开关：``pin_audit.enabled``（默认 true）、``pin_audit.report_hanging``
（默认 true；false 时 [HANGING] 条目只统计不逐条输出）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PinAuditEntry:
    """一条引脚审计记录。"""

    page: int
    refdes: str
    pin_number: str
    pin_name: str = ""
    net_name: str = ""
    status: str = "connected"
    detail: str = ""


@dataclass
class PinAuditResult:
    """M6 审计汇总。"""

    entries: list[PinAuditEntry] = field(default_factory=list)
    total: int = 0
    connected: int = 0
    hanging: int = 0
    net_mismatch: int = 0
    pin_mismatch: int = 0

    @property
    def hanging_entries(self) -> list[PinAuditEntry]:
        """悬空引脚清单（[HANGING]）。"""
        return [e for e in self.entries if e.status == "hanging"]


class PinConnectAuditor:
    """逐引脚连接状态审计器（基于 DesignConnectivity 模型）。"""

    def __init__(
        self,
        enabled: bool = True,
        report_hanging: bool = True,
    ) -> None:
        """Initialize the auditor.

        Args:
            enabled: 总开关（``pin_audit.enabled``）。
            report_hanging: 悬空引脚逐条报告（``pin_audit.report_hanging``）。
        """
        self.enabled: bool = enabled
        self.report_hanging: bool = report_hanging

    # ------------------------------------------------------------------
    #  Audit
    # ------------------------------------------------------------------

    def audit(self, conn) -> PinAuditResult:
        """审计设计级连接模型的全部引脚。

        Args:
            conn: DesignConnectivity（instances/pins/nets/cells）。

        Returns:
            PinAuditResult（条目 + 分状态统计）。
        """
        result = PinAuditResult()
        if not self.enabled or conn is None:
            return result

        net_by_id: dict[str, object] = {}
        for net in getattr(conn, "nets", []) or []:
            net_by_id[getattr(net, "net_id", "")] = net

        cell_pin_names: dict[str, set[str]] = {}
        for cell in getattr(conn, "cells", []) or []:
            cell_pin_names[cell.cell_id] = set(
                getattr(cell, "pin_names", {}) or {}
            )

        for page_conn in getattr(conn, "pages", []) or []:
            page_num = int(getattr(page_conn, "page_num", 0) or 0)
            for irec in getattr(page_conn, "instances", []) or []:
                refdes = getattr(irec, "refdes", "") or ""
                pins = getattr(irec, "pins", []) or []
                # 引脚名不匹配：实例引脚不在匹配 cell 引脚定义中。
                cell_id = getattr(irec, "cell_id", "") or ""
                known = cell_pin_names.get(cell_id)
                for pre in pins:
                    pin_number = getattr(pre, "pin_number", "") or ""
                    pin_name = getattr(pre, "pin_name", "") or ""
                    net_id = getattr(pre, "net_id", "") or ""
                    net_name = ""
                    status = "connected"
                    detail = ""

                    if not net_id or net_id.upper() == "NC":
                        status = "hanging"
                        detail = "no net (NC)"
                    else:
                        net_rec = net_by_id.get(net_id)
                        if net_rec is None:
                            status = "net_mismatch"
                            detail = f"net_id {net_id} not found in conn.nets"
                        else:
                            net_name = str(
                                getattr(net_rec, "internal_name", "") or net_id
                            )
                            conns = list(
                                getattr(net_rec, "connections", []) or []
                            )
                            # 该网连接数：仅自己 → 悬空。
                            if len(conns) <= 1:
                                status = "hanging"
                                detail = (
                                    f"net {net_name} has only this pin "
                                    "(待 Allegro 布线)"
                                )
                            else:
                                detail = (
                                    f"net {net_name} ({len(conns)} pins)"
                                )

                    if status == "connected" and known is not None:
                        if (pin_number not in known
                                and pin_name not in known
                                and str(pin_number).upper() not in known):
                            status = "pin_mismatch"
                            detail = (
                                f"pin {pin_number} not in cell {cell_id} "
                                "pin definitions"
                            )

                    result.total += 1
                    if status == "connected":
                        result.connected += 1
                    elif status == "hanging":
                        result.hanging += 1
                    elif status == "net_mismatch":
                        result.net_mismatch += 1
                    else:
                        result.pin_mismatch += 1

                    result.entries.append(PinAuditEntry(
                        page=page_num,
                        refdes=refdes,
                        pin_number=pin_number,
                        pin_name=pin_name,
                        net_name=net_name,
                        status=status,
                        detail=detail,
                    ))

        if result.total:
            logger.info(
                "PinAudit: %d pins — connected=%d hanging=%d "
                "net_mismatch=%d pin_mismatch=%d",
                result.total, result.connected, result.hanging,
                result.net_mismatch, result.pin_mismatch,
            )
        return result

    # ------------------------------------------------------------------
    #  Report
    # ------------------------------------------------------------------

    def format_report(self, result: PinAuditResult) -> str:
        """把审计结果格式化为文本报告。

        Args:
            result: PinAuditResult。

        Returns:
            报告文本（[PIN_AUDIT] / [HANGING] 节）。
        """
        lines: list[str] = []
        a = lines.append
        a("PIN CONNECT AUDIT REPORT")
        a("=" * 40)
        a(f"total pins       : {result.total}")
        a(f"connected        : {result.connected}")
        a(f"hanging          : {result.hanging}")
        a(f"net_mismatch     : {result.net_mismatch}")
        a(f"pin_mismatch     : {result.pin_mismatch}")
        a("")
        a("[PIN_AUDIT]")
        for e in result.entries:
            if e.status == "hanging" and not self.report_hanging:
                continue
            a(
                f"  page {e.page}: {e.refdes}.{e.pin_number} "
                f"({e.pin_name or '-'}) → {e.status.upper()} — {e.detail}"
            )
        a("")
        a("[HANGING]")
        for e in result.hanging_entries:
            a(
                f"  page {e.page}: {e.refdes}.{e.pin_number} "
                f"({e.pin_name or '-'}) 待 Allegro 布线"
            )
        return "\n".join(lines) + "\n"

    def write(
        self, result: PinAuditResult, output_root: Path,
    ) -> Optional[Path]:
        """写出 pin_audit_report.txt。

        Args:
            result: PinAuditResult。
            output_root: 输出根目录。

        Returns:
            报告文件路径；禁用/无条目返回 None。
        """
        if not self.enabled or result.total == 0:
            return None
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        out = root / "pin_audit_report.txt"
        out.write_text(self.format_report(result), encoding="utf-8")
        logger.info("PinAudit report → %s", out)
        return out
