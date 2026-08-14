"""IOPortAuditor — Phase XVI T2 IOPORT 一致性核对（system_design0811-phase16.md Part B）。

三类检测，全部基于 **DesignConnectivity 模型**（stage 后、pin_connections
已注入）与 CSAWriter 生成的页级坐标（pin_coords / net_pin_map / routed_nets）：

1. **接线核对**（B.1.1，每页）：IOPORT 所在网有 ≥2 元件引脚时必须已布线，
   断言 ioport_coord ∈ 该网 WIRE 端点；仅 IOPORT 单引脚网豁免（按网名连接）。
2. **网名跨页一致性**（B.1.2，全局）：canonical 归一化分组，报告"疑似同一网
   不同名"；只报告不自动合并（跨页改名有电气风险）。
3. **孤立 connector**（B.1.3，全局）：IOPORT 网名在全工程任何页元件引脚
   SIG_NAME 均不出现 → 标记孤立。

⚠️ 数据源铁律：禁止直接对 raw EDIFParser 的 PageIR 做孤立检测（pin_connections
未注入时会 100% 误报）；本模块只消费 ConnectivityModelBuilder 构建的
DesignConnectivity / PageConnectivity（``connectivity_model.py`` 已注入
``inst.pin_connections``）。

本模块不 import 具体 writer 类（防循环依赖，沿用 Phase XIV D5 模式）。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class UnwiredIoport:
    """接线缺失条目：IOPORT 所在网有元件引脚但 IOPORT 引脚不是 WIRE 端点。"""

    page: str
    idx: int
    net: str
    coord: tuple
    pins_on_page: int


@dataclass
class NameConflict:
    """网名一致性条目：疑似同一网不同名（只报告，不自动合并）。"""

    page: str
    ioport_name: str
    pin_net_names: list
    canonical: str


@dataclass
class OrphanIoport:
    """孤立 connector 条目：IOPORT 网名全工程无任何元件引脚引用。"""

    page: str
    net: str
    canonical: str
    reason: str


def canonical_name(name: str) -> str:
    """Canonical 归一化：去下划线/空白、去 ``\\g`` 电源后缀、转小写。

    Examples:
        "WPS" / "wps" / "W_P_S" → "wps"
        "GND\\g" / "GND" → "gnd"
    """
    return re.sub(r"[_\s]+", "", str(name)).replace("\\g", "").lower()


class IOPortAuditor:
    """IOPORT 三节审计收集器 + ``ioport_audit_report.txt`` 报告写出。

    Attributes:
        enabled: 总开关（默认 True；writer 在 ``ioport.audit=false`` 时
            不实例化本类）。
        skip_orphan: 孤立 connector 是否不生成（默认 False=只报告）。
        manual_names: 人工网名覆盖 {raw_name: canonical_target}。
    """

    def __init__(
        self,
        enabled: bool = True,
        skip_orphan: bool = False,
        manual_names: dict | None = None,
    ) -> None:
        self._enabled = bool(enabled)
        self._skip_orphan = bool(skip_orphan)
        self._manual_names: dict[str, str] = dict(manual_names or {})
        self._unwired: list[UnwiredIoport] = []
        self._name_conflicts: list[NameConflict] = []
        self._name_conflict_by_canon: dict[str, NameConflict] = {}
        self._orphans: list[OrphanIoport] = []
        # A 集：所有 IOPORT 网名（canonical → 去重 raw 集合）
        self._ioport_raw_names: dict[str, set[str]] = {}
        self._ioport_page_by_raw: dict[str, str] = {}
        # B 集：全工程元件引脚 SIG_NAME 网名（canonical）
        self._pin_net_canonicals: set[str] = set()
        self._ioport_total: int = 0
        self._unique_nets: set[str] = set()
        self._exempt_name_only: int = 0
        self._pages: int = 0
        self._project_name: str = ""
        self._wires_skipped: bool = False

    # ------------------------------------------------------------------
    #  Static utilities（与 CSAWriter 解耦，供 skip_orphan 预计算复用）
    # ------------------------------------------------------------------

    @staticmethod
    def canonical(name: str) -> str:
        """Canonical 归一化（见模块级 :func:`canonical_name`）。"""
        return canonical_name(name)

    @staticmethod
    def orphan_ioport_names(conn, manual_names: dict | None = None) -> set[str]:
        """返回全工程孤立的 IOPORT 原始网名集合（供 skip_orphan 跳过生成）。

        数据源：DesignConnectivity（stage 后）——B 集 = 所有 NetRecord /
        PageNetRecord display_name + 电源符号 power_nets 的 canonical；
        A 集 = 所有 off_pages 的 net_name。canonical(n) ∉ B → 孤立。

        Args:
            conn: DesignConnectivity（pin_connections 已注入）。
            manual_names: 人工网名覆盖 {raw: target}（覆盖后再判孤立）。

        Returns:
            Set of raw IOPORT net names that are orphan.
        """
        manual = dict(manual_names or {})
        pin_canonicals: set[str] = set()
        for nr in getattr(conn, "nets", []) or []:
            if getattr(nr, "display_name", ""):
                pin_canonicals.add(canonical_name(nr.display_name))
        for page_conn in getattr(conn, "pages", []) or []:
            for nr in getattr(page_conn, "nets", []) or []:
                if getattr(nr, "display_name", ""):
                    pin_canonicals.add(canonical_name(nr.display_name))
            for irec in getattr(page_conn, "instances", []) or []:
                for pnet in getattr(irec, "power_nets", []) or []:
                    pin_canonicals.add(canonical_name(pnet))
        orphan: set[str] = set()
        for page_conn in getattr(conn, "pages", []) or []:
            for op in getattr(page_conn, "off_pages", []) or []:
                op_name = str(op.get("name", "") or "")
                if not op_name:
                    continue
                raw = str(op.get("net_name", "") or op_name)
                check = manual.get(raw, raw)
                if canonical_name(check) not in pin_canonicals:
                    orphan.add(raw)
        return orphan

    @staticmethod
    def _orphan_reason(raw: str) -> str:
        """孤立原因：auto-net 残留 vs 无元件引脚引用。"""
        if raw.startswith("UN$") or raw.startswith("$") or (
                raw and raw[0].isdigit()):
            return "auto-net"
        return "no-component-pin"

    @staticmethod
    def _is_power_norm(raw: str, display: str) -> bool:
        """``GND`` → ``GND\\g`` 这类电源网显示名归一化不是网名冲突。"""
        return display.endswith("\\g") and canonical_name(raw) == canonical_name(display)

    def _resolve_display(self, page_conn, net_name: str) -> str:
        """与 CSAWriter._power_net_display 同源的页网显示名解析。

        Args:
            page_conn: PageConnectivity（net_by_bare 已构建）。
            net_name: IOPORT 原始网名（manual_names 已应用时更佳）。

        Returns:
            页网显示名；未命中时返回原样 net_name。
        """
        from ..net_utils import con_name
        if net_name in self._manual_names:
            net_name = self._manual_names[net_name]
        bare = con_name(net_name)
        pnr = page_conn.net_by_bare.get(bare)
        if pnr is not None:
            return pnr.display_name
        return net_name

    # ------------------------------------------------------------------
    #  Collection API
    # ------------------------------------------------------------------

    def audit_page(
        self,
        page_conn,
        net_pin_map: dict,
        routed_nets: dict,
        ioport_list: list | None = None,
    ) -> None:
        """接线核对（B.1.1）+ 收集 A/B 集（B.1.2/B.1.3 输入）。

        在 ``_build_csa_content_conn`` 的 ``_route_nets`` 之后调用；
        ``emit_csa_wires=false`` 时 writer 不调用本方法并在报告注明。

        Args:
            page_conn: PageConnectivity。
            net_pin_map: 页网显示名 → 引脚列表（Pass1 已注入 IOPORT 引脚）。
            routed_nets: ``{net_display: RoutedNet}``（布线结果）。
            ioport_list: 实际发射的 ``(idx, op)`` 列表（skip_orphan 时
                effective idx 与 enumerate 不同；None = 全部 off_pages）。
        """
        if not self._enabled:
            return
        self._pages += 1
        self._collect_page_net_names(page_conn)

        entries = ioport_list
        if entries is None:
            entries = [
                (i, op) for i, op in enumerate(getattr(page_conn, "off_pages", []) or [])
                if str(op.get("name", "") or "")
            ]
        for idx, op in entries:
            self._audit_one_ioport(page_conn, net_pin_map, routed_nets, idx, op)

    def _collect_page_net_names(self, page_conn) -> None:
        """收集 B 集：页元件引脚 SIG_NAME 网名（DesignConnectivity 模型）。"""
        for nr in getattr(page_conn, "nets", []) or []:
            if getattr(nr, "display_name", ""):
                self._pin_net_canonicals.add(canonical_name(nr.display_name))
        for irec in getattr(page_conn, "instances", []) or []:
            for pnet in getattr(irec, "power_nets", []) or []:
                self._pin_net_canonicals.add(canonical_name(pnet))

    def _audit_one_ioport(self, page_conn, net_pin_map, routed_nets,
                          idx: int, op: dict) -> None:
        """单个 IOPORT 的接线核对（B.1.1）+ 网名一致性（B.1.2 检测 2）。"""
        op_name = str(op.get("name", "") or f"OFFPAGE_{idx}")
        net_name = str(op.get("net_name", "") or op_name)
        if net_name in self._manual_names:
            net_name = self._manual_names[net_name]
        canon = canonical_name(net_name)
        self._ioport_total += 1
        self._unique_nets.add(canon)
        self._ioport_raw_names.setdefault(canon, set()).add(net_name)
        self._ioport_page_by_raw.setdefault(net_name, page_conn.page_name)

        # 找到 writer 实际注入该 IOPORT 引脚所用的网 key（稳健匹配）
        ioport_key = f"IOPORT_{idx}"
        net_key = None
        for key, pins in net_pin_map.items():
            if any(str(p.get("refdes", "")) == ioport_key for p in pins):
                net_key = key
                break
        net_display = self._resolve_display(page_conn, net_name)
        pins = net_pin_map.get(net_key or net_display, [])
        comp_pins = [
            p for p in pins
            if not str(p.get("refdes", "")).startswith("IOPORT_")
        ]
        ioport_pins = [p for p in pins if str(p.get("refdes", "")) == ioport_key]
        if not comp_pins:
            # 本页该网仅有 IOPORT（跨页网本页常只有连接器）→ 豁免
            self._exempt_name_only += 1
            return
        ioport_coord = (
            tuple(ioport_pins[0]["coord"]) if ioport_pins else (0, 0)
        )
        routed = routed_nets.get(net_key or net_display)
        endpoints: set[tuple[int, int]] = set()
        if routed is not None:
            for w in getattr(routed, "wires", []) or []:
                endpoints.add((w.x1, w.y1))
                endpoints.add((w.x2, w.y2))
        if ioport_coord not in endpoints:
            self._unwired.append(UnwiredIoport(
                page=page_conn.page_name, idx=idx, net=net_display,
                coord=ioport_coord, pins_on_page=len(comp_pins),
            ))
        # 网名一致性（B.1.2 检测 2）：IOPORT raw 与页内引脚显示名不同拼写
        if net_name != net_display and not self._is_power_norm(net_name, net_display):
            self._add_name_conflict(
                page_conn.page_name, net_name, [net_display], canon,
            )

    def finalize(self, conn) -> None:
        """全局收尾：B.1.2 网名一致性分组 + B.1.3 孤立 connector。

        Args:
            conn: DesignConnectivity（用于 project_name + 全局 B 集兜底）。
        """
        if not self._enabled:
            return
        self._project_name = getattr(conn, "cell_name", "") or ""
        for nr in getattr(conn, "nets", []) or []:
            if getattr(nr, "display_name", ""):
                self._pin_net_canonicals.add(canonical_name(nr.display_name))
        # B.1.2 检测 1：A 集内 canonical 分组 → 组内 distinct raw > 1
        for canon, raws in self._ioport_raw_names.items():
            if len(raws) > 1:
                raw_list = sorted(raws)
                page = self._ioport_page_by_raw.get(raw_list[0], "")
                self._add_name_conflict(page, raw_list[0], raw_list, canon)
        # B.1.3：canonical(n) ∉ canonical(B) → 孤立
        for canon in sorted(self._ioport_raw_names):
            if canon in self._pin_net_canonicals:
                continue
            for raw in sorted(self._ioport_raw_names[canon]):
                page = self._ioport_page_by_raw.get(raw, "")
                self._orphans.append(OrphanIoport(
                    page=page, net=raw, canonical=canon,
                    reason=self._orphan_reason(raw),
                ))

    def mark_wires_skipped(self) -> None:
        """``emit_csa_wires=false`` 时接线核对被跳过（报告注明）。"""
        self._wires_skipped = True

    def _add_name_conflict(
        self, page: str, ioport_name: str, pin_net_names: list, canon: str,
    ) -> None:
        """按 canonical 合并网名冲突（同一网只报一条，累积 pin_net_names）。"""
        existing = self._name_conflict_by_canon.get(canon)
        if existing is None:
            nc = NameConflict(
                page=page, ioport_name=ioport_name,
                pin_net_names=list(pin_net_names), canonical=canon,
            )
            self._name_conflict_by_canon[canon] = nc
            self._name_conflicts.append(nc)
        else:
            for n in pin_net_names:
                if n not in existing.pin_net_names:
                    existing.pin_net_names.append(n)

    # ------------------------------------------------------------------
    #  Output
    # ------------------------------------------------------------------

    def write(self, output_dir: Path) -> Path | None:
        """Write ``ioport_audit_report.txt`` into ``output_dir``.

        Args:
            output_dir: 输出根目录。

        Returns:
            生成的报告路径；开关关闭时返回 None。
        """
        if not self._enabled:
            return None
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "ioport_audit_report.txt"
        lines: list[str] = []
        a = lines.append

        a(f"=== IOPORT Audit Report: {self._project_name or 'design'} ===")
        a(
            f"[SUMMARY] pages={self._pages}  "
            f"ioport_total={self._ioport_total}  "
            f"unique_nets={len(self._unique_nets)}"
        )
        a(
            f"          unwired={len(self._unwired)}  "
            f"name_conflicts={len(self._name_conflicts)}  "
            f"orphan={len(self._orphans)}  "
            f"exempt_name_only={self._exempt_name_only}"
        )
        self._write_unwired(a)
        self._write_name_conflict(a)
        self._write_orphan(a)
        self._write_fix_suggestion(a)

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("IOPORT audit report written: %s", report_path)
        return report_path

    def _write_unwired(self, a) -> None:
        """[UNWIRED] 接线核对节。"""
        a(f"[UNWIRED] total={len(self._unwired)}")
        if self._wires_skipped and not self._unwired:
            a("  (skipped: emit_csa_wires=false — 未生成 WIRE，无接线可核对)")
        elif not self._unwired:
            a("  (none)")
        else:
            for u in self._unwired:
                a(
                    f"  page={u.page}  net={u.net}  coord={u.coord}  "
                    f"pins_on_page={u.pins_on_page}"
                )

    def _write_name_conflict(self, a) -> None:
        """[NAME_CONFLICT] 网名一致性节（只报告，不自动合并）。"""
        a(f"[NAME_CONFLICT] total={len(self._name_conflicts)}  "
          "疑似同一网不同名 —— 人工裁决，不自动合并")
        if not self._name_conflicts:
            a("  (none)")
            return
        for nc in self._name_conflicts:
            a(
                f"  page={nc.page}  ioport={nc.ioport_name!r}  "
                f"page-pins={nc.pin_net_names!r}  canonical={nc.canonical!r}"
            )

    def _write_orphan(self, a) -> None:
        """[ORPHAN] 孤立 connector 节。"""
        a(f"[ORPHAN] total={len(self._orphans)}  "
          "IOPORT 网名全工程无元件引脚引用")
        if not self._orphans:
            a("  (none)")
            return
        for o in self._orphans:
            a(
                f"  page={o.page}  net={o.net!r}  canonical={o.canonical!r}  "
                f"reason={o.reason}  建议=不生成该 IOPORT"
            )

    @staticmethod
    def _write_fix_suggestion(a) -> None:
        """[FIX_SUGGESTION] 修复建议节。"""
        a("[FIX_SUGGESTION]")
        a("  unwired: 布线层修复（网名一致则 WIRE 必达；若否检查 net_pin_map 归属）")
        a("  orphan:  config ioport.skip_orphan=true → 不生成该 IOPORT")
        a("  name_conflict: config ioport.manual_names={\"WPS\":\"wps\"} → 解析时覆盖")
