"""AestheticReport — Phase XIV 多模块共用的量化报告收集器（D1/D2/D5）。

D1 文本去冲突 / D2 元件重叠 / 布线统计 各模块向本收集器写入数据，
最后统一输出 ``aesthetic_report.txt``（与输出根目录同目录）。

默认关闭（``aesthetic.report=true`` 且 ``aesthetic.enabled=true``）；
开关关闭时 ``write()`` 不产生文件。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Overlap:
    """D2 元件重叠报告条目。"""

    page: int
    refdes_a: str
    refdes_b: str
    bbox_a: tuple[int, int, int, int]
    bbox_b: tuple[int, int, int, int]
    overlap_rect: tuple[int, int, int, int]
    area: int
    kind: str = "user"  # "placeholder" | "grid" | "user"


@dataclass
class MirrorEntry:
    """Phase XVI T1 镜像归一化报告条目（system_design0811-phase16.md A.5/A.6）。

    Attributes:
        page: 页面名（如 "13-DDR3"）。
        refdes: 实例位号（如 "L20"）。
        orient: EDIF orientation（MX / MY / MYR90 / MXR90）。
        rline: 等效 DEHDL ``R n`` 角度（0=不输出 R 行）。
        approx: True = 方向近似（镜像无法用纯旋转表达，需人工复核）；
            False = 精确（竖直双引脚无源件等）。
    """

    page: str
    refdes: str
    orient: str
    rline: int
    approx: bool = False


@dataclass
class AestheticReport:
    """多模块共用的量化报告收集器。

    Attributes:
        project_name: 项目名（报告标题）。
        overlaps: D2 重叠条目。
        text_before / text_after: D1 冲突数前后对比。
        unresolved_text: D1 无法自动解决的碰撞。
        net_align / port_align / diff_ok / diff_total: D1 对齐统计。
        off_grid_labels / off_grid_wires: 网格统计。
        enabled: 总开关（默认 False）。
    """

    project_name: str = ""
    overlaps: list[Overlap] = field(default_factory=list)
    mirrors: list[MirrorEntry] = field(default_factory=list)
    lastpin_misses: list[tuple[str, str, str, tuple, tuple, bool, str]] = field(
        default_factory=list,
    )
    text_before: int = 0
    text_after: int = 0
    unresolved_text: list[tuple[str, str]] = field(default_factory=list)
    net_align: float = 0.0
    port_align: float = 0.0
    diff_ok: int = 0
    diff_total: int = 0
    off_grid_labels: int = 0
    off_grid_wires: int = 0
    enabled: bool = True
    # Phase XXI I（用户 Cadence 16.6 实测 P19"电线穿芯片/元件"）：P0 布线
    # trunk 已避让 outline（Phase XIII T4），但**stub**（pin→trunk 直线段）
    # 对框内引脚（真实库元件）可能穿过元件体。完整绕障由 detour 布线器
    # 承担；p0 默认只**记录**穿体电线到报告（不阻塞转换）。
    # Phase XXII D2：自身引脚引出段（段端点 = 该 body 所属实例引脚坐标）
    # 属正常电气引出，豁免不计数 —— ``exempt`` 标志区分"真违规"与豁免。
    # Phase XXII QA 修复：``reason`` 记录豁免类别（self-pin / power_symbol），
    # 报告明确 ``detected/exempt/violations`` 三口径（total 曾误读）。
    wire_through_bodies: list[tuple[int, str, tuple, tuple, bool, str]] = field(
        default_factory=list,
    )
    # 跨页聚合（add_align_stats 按页累加，write 时取加权均值）
    _net_align_sum: float = 0.0
    _net_align_count: int = 0
    _port_align_sum: float = 0.0
    _port_align_count: int = 0

    # ------------------------------------------------------------------
    #  Collectors
    # ------------------------------------------------------------------

    def add_overlap(self, ov: Overlap) -> None:
        """Add a D2 overlap entry.

        Args:
            ov: Overlap entry to record.
        """
        self.overlaps.append(ov)

    def add_mirror(self, entry: MirrorEntry) -> None:
        """Add a Phase XVI T1 mirror-normalization entry.

        Args:
            entry: MirrorEntry to record（受 aesthetic.enabled /
                mirror.report 门控，由 CSAWriter 决定是否调用）。
        """
        self.mirrors.append(entry)

    def add_lastpin_miss(
        self, page: str, refdes: str, pin: str,
        coord: tuple[int, int], expected: tuple[int, int],
        exempt: bool = False, reason: str = "",
    ) -> None:
        """Add a Phase XVIII R3d LASTPIN coordinate-miss entry.

        LASTPIN 坐标 != body + rotate_point(css_offset, rot, mirror) 时
        记录（skip + 报告 [LASTPIN_MISS]）。

        Phase XXII D8：``exempt=True`` 的条目（同源偏移仍不命中的合法
        边缘，如真实库符号 offset 非 25 网格）计入报告但标记证据化豁免
        —— QA 以 ``total=N exempt=M`` 区分"真违规"与"豁免"。

        Args:
            page: 页面名。
            refdes: 实例位号。
            pin: 引脚号。
            coord: 实际 LASTPIN 坐标。
            expected: 期望坐标（body + rotate_point 派生）。
            exempt: True = 证据化豁免（合法边缘，非真违规）。
            reason: 豁免原因说明。
        """
        self.lastpin_misses.append(
            (page, refdes, pin, coord, expected, bool(exempt), str(reason))
        )

    def add_text_stats(
        self, before: int, after: int, unresolved: Optional[list] = None,
    ) -> None:
        """Record D1 text collision statistics（跨页累加）。

        Args:
            before: 解算前碰撞数。
            after: 解算后碰撞数。
            unresolved: 无法自动解决的碰撞 (key_a, key_b) 列表。
        """
        self.text_before += int(before)
        self.text_after += int(after)
        if unresolved:
            self.unresolved_text.extend(list(unresolved))

    def add_align_stats(
        self,
        net_align: float,
        port_align: float,
        diff_ok: int,
        diff_total: int,
    ) -> None:
        """Record D1 alignment statistics（跨页累加，write 时取均值）。

        Args:
            net_align: 网络名 x 对齐率 (0.0-1.0)。
            port_align: 同侧 Port 对齐率 (0.0-1.0)。
            diff_ok: 差分对方向正确数。
            diff_total: 差分对总数。
        """
        self._net_align_sum += float(net_align)
        self._net_align_count += 1
        self._port_align_sum += float(port_align)
        self._port_align_count += 1
        self.diff_ok += int(diff_ok)
        self.diff_total += int(diff_total)

    def add_grid_stats(self, off_grid_labels: int, off_grid_wires: int) -> None:
        """Record grid statistics（跨页累加）。

        Args:
            off_grid_labels: 偏离 25 网格的标签数。
            off_grid_wires: 偏离 25 网格的 WIRE 端点/坐标数。
        """
        self.off_grid_labels += int(off_grid_labels)
        self.off_grid_wires += int(off_grid_wires)

    def add_wire_through_body(
        self, page: int, net: str,
        seg: tuple[int, int, int, int], outline: tuple[int, int, int, int],
        exempt: bool = False, reason: str = "",
    ) -> None:
        """Record a wire segment passing through a body outline (Phase XXI I).

        P0 布线 trunk 避让已生效，但 stub 直线段对框内引脚可能穿过元件体。
        完整绕障由 detour 布线器承担；p0 默认只记录（不阻塞转换）。

        Phase XXII D2：真实库引脚在 outline 内，P→E 引出段必然穿过自己
        的 outline —— 这是正常电气引出。``exempt=True`` 时该穿体对记入
        报告但**不计入 violations**（自身引脚引出 / 电源符号挂轨）。

        Phase XXII QA 修复：报告三口径 ``detected / exempt / violations``
        —— ``detected`` = 总检出穿体对，``exempt`` = 豁免数，``violations``
        = 真违规数（非豁免）。**``violations`` 才是"真违规"口径**（旧版
        ``total`` 曾误读为总检出数）。

        Args:
            page: 页面号。
            net: 网络显示名。
            seg: 线段 (x1,y1,x2,y2)。
            outline: 被穿过的元件轮廓 (x0,y0,x1,y1)。
            exempt: True = 证据化豁免（自身引脚引出 / 电源符号挂轨）。
            reason: 豁免原因（``self-pin`` / ``power_symbol``；非豁免为空）。
        """
        self.wire_through_bodies.append(
            (
                int(page), str(net), tuple(seg), tuple(outline),
                bool(exempt), str(reason),
            )
        )

    # ------------------------------------------------------------------
    #  Output
    # ------------------------------------------------------------------

    def write(self, output_dir: Path) -> Optional[Path]:
        """Write ``aesthetic_report.txt`` into ``output_dir``.

        Args:
            output_dir: 输出根目录。

        Returns:
            生成的报告路径；开关关闭时返回 None。
        """
        if not self.enabled:
            return None
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "aesthetic_report.txt"
        lines: list[str] = []
        a = lines.append

        a(f"=== Aesthetic Report: {self.project_name or 'design'} ===")

        # ── D2 重叠 ───────────────────────────────────────────────
        by_page: dict[int, list[Overlap]] = {}
        for ov in self.overlaps:
            by_page.setdefault(ov.page, []).append(ov)
        if by_page:
            for page in sorted(by_page):
                ovs = by_page[page]
                a(f"[OVERLAP] page={page}  total={len(ovs)}")
                for ov in ovs:
                    a(
                        f"  {ov.refdes_a} {ov.bbox_a}  vs  {ov.refdes_b} {ov.bbox_b}"
                    )
                    a(
                        f"    overlap={ov.overlap_rect} area={ov.area} "
                        f"kind={ov.kind}"
                    )
                    if ov.kind == "placeholder":
                        a(
                            f"    fix_hint: {ov.refdes_a} 是未匹配占位，"
                            "建议 D3 人工匹配后重转"
                        )
        else:
            a("[OVERLAP] none")

        # ── Phase XVIII R3d: LASTPIN 坐标未命中 [LASTPIN_MISS] ────
        # Phase XXII D8：exempt 条目证据化豁免（合法边缘）——QA 用
        # total/exempt 区分"真违规"与"豁免"。
        if self.lastpin_misses:
            total = len(self.lastpin_misses)
            exempt = sum(1 for e in self.lastpin_misses if e[5])
            a(f"[LASTPIN_MISS] total={total} exempt={exempt}")
            for page, refdes, pin, coord, expected, _ex, reason in self.lastpin_misses:
                a(
                    f"  page={page} refdes={refdes}.{pin} "
                    f"coord={coord} expected={expected}"
                )
                if _ex:
                    a(f"    exempt reason: {reason}")
        else:
            a("[LASTPIN_MISS] none")

        # ── Phase XVI T1: 镜像归一化 [MIRROR] ──────────────────────
        if self.mirrors:
            exact = sum(1 for m in self.mirrors if not m.approx)
            approx = len(self.mirrors) - exact
            a(
                f"[MIRROR] total={len(self.mirrors)} "
                f"normalized={len(self.mirrors)} "
                f"exact={exact} approx={approx}"
            )
            for m in self.mirrors:
                rline_txt = f"R {m.rline}" if m.rline else "(no R line)"
                a(
                    f"  page={m.page}  refdes={m.refdes}  orient={m.orient}  "
                    f"→ {rline_txt}  {'exact' if not m.approx else 'approx'}"
                )
                if m.approx:
                    a("    note: 方向近似（镜像无法用纯旋转表达），需人工复核")
        else:
            a("[MIRROR] none")

        # ── D1 文本 / 对齐 ────────────────────────────────────────
        net_align = (
            self._net_align_sum / self._net_align_count
            if self._net_align_count else self.net_align
        )
        port_align = (
            self._port_align_sum / self._port_align_count
            if self._port_align_count else self.port_align
        )
        a(f"[TEXT]  collisions_before={self.text_before} "
          f"collisions_after={self.text_after} "
          f"unresolved={len(self.unresolved_text)}")
        for ka, kb in self.unresolved_text[:10]:
            a(f"    unresolved: {ka} vs {kb}")
        a(
            f"[ALIGN] net_name_x_align={net_align:.1%} "
            f"port_align={port_align:.1%} "
            f"diff_pair_ok={self.diff_ok}/{self.diff_total}"
        )

        # ── 网格统计 ──────────────────────────────────────────────
        a(
            f"[GRID]  off_grid_labels={self.off_grid_labels} "
            f"off_grid_wires={self.off_grid_wires}"
        )

        # ── Phase XXI I: 电线穿元件体 [WIRE_THROUGH_BODY] ──────────
        # Phase XXII D2：自身引脚引出段（exempt）不计入 violations ——
        # 真违规 = 穿**其他**元件体的段。
        # Phase XXII QA 修复：三口径 ``detected / exempt / violations``
        # —— detected=总检出、exempt=豁免数、violations=真违规（非豁免）。
        # **violations 才是"真违规"**（旧 total 曾误读为总检出数）。
        if self.wire_through_bodies:
            detected = len(self.wire_through_bodies)
            violations = sum(1 for e in self.wire_through_bodies if not e[4])
            exempt = detected - violations
            # Phase XXIII R-2：violations 分项 —— trunk_blocked（密集页
            # trunk 无解回退直穿，不可避免）vs non_trunk（非 trunk 线上的
            # 穿体，多为 stub 段——p0 三段式 stub 已避让但未全覆盖，完整
            # 绕障属 detour 布线器）。命名避开"avoidable"（避免被误读为
            # "可避让未避让"，Phase XXII total 误读教训）。
            trunk_blocked = sum(
                1 for e in self.wire_through_bodies
                if not e[4] and e[5] == "trunk_blocked"
            )
            non_trunk = violations - trunk_blocked
            a(
                f"[WIRE_THROUGH_BODY] detected={detected} "
                f"exempt={exempt} violations={violations} "
                f"(trunk_blocked={trunk_blocked}, non_trunk={non_trunk})"
            )
            for page, net, seg, outline, _exempt, reason in self.wire_through_bodies[:50]:
                _suffix = ""
                if _exempt:
                    _suffix = " exempt=" + reason
                elif reason:
                    _suffix = " reason=" + reason
                a(
                    f"  page={page} net={net} seg={seg} "
                    f"body={outline}{_suffix}"
                )
            a(
                "  note: 自身引脚引出段（段端点=该元件引脚坐标）与电源符号"
                "挂轨属正常电气，已豁免不计；violations = 穿其他元件体的真"
                "违规（trunk_blocked = 密集页 trunk 无解回退直穿；non_trunk "
                "= 非 trunk 线上的穿体，多为 stub 段，完整绕障属 detour，"
                "见 README 已知限制）。三段式 stub 已做 outline 避让"
                "（--routing detour 完整绕障）。"
            )
        else:
            a("[WIRE_THROUGH_BODY] none")

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Aesthetic report written: %s", report_path)
        return report_path
