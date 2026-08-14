"""TextLayoutOptimizer — D1 文本/标签去冲突 + 对齐（Phase XIV）。

只动标签坐标（CSA 的 DISPLAY / FORCEPROP 标签行），**绝不碰
LASTPIN / WIRE** —— 电气连接由坐标重合硬约束保证，标签不参与电气。

数据流（§A.1.1）：
    collect_text_items → detect_collisions → resolve → align → offsets

优先级（数字小先动）：
    0 = SIG_NAME（线上标签可沿 trunk 滑动）
    1 = VALUE / $LOCATION（就近 8 方向 25 网格微调）
    2 = PORT（IOPORT 标签）
    3 = PIN_TEXT / SIG_NAME_ON_PIN（禁动 —— 锚点即 LASTPIN 坐标）

对齐规则（§A.1.3）：
    * 网络名 x = snap25(trunk_min_x + 375)（7.5 格点 = 375 单位）；
    * 同侧 Port 对齐（边缘统一 x、y 等间距）；
    * 差分对 _P/_N → P 上 N 下（仅线上标签，禁动标签跳过）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .wire_layout import RoutedNet

logger = logging.getLogger(__name__)

#: CSA DISPLAY 缩放常量（与 csa_writer 顶部一致 —— 文本 bbox 估算用）。
_SCALE_VALUE: float = 0.851064
_SCALE_SIG_NAME: float = 0.659574
_SCALE_PN: float = 0.808511
_SCALE_IOPORT: float = 0.872340

#: 文本类型常量（kind 取值）。
KIND_LOCATION = "LOCATION"
KIND_VALUE = "VALUE"
KIND_SIG_NAME = "SIG_NAME"
KIND_PIN_TEXT = "PIN_TEXT"
KIND_PORT = "PORT"

#: 差分对后缀识别（§A.1.3：_P/_N 或 _P_/_N_）。
_DIFF_PATTERN = ("_P", "_N", "_P_", "_N_")


@dataclass
class TextItem:
    """页面可见文本条目（可移动性/优先级/锚点）。

    Attributes:
        key: 唯一键（"refdes.VALUE" / "net.SIG_NAME" 等）。
        kind: LOCATION | VALUE | SIG_NAME | PIN_TEXT | PORT。
        text: 显示文本。
        anchor: 当前锚点坐标（CSA 输出坐标）。
        font_size: css 高度（40/32/24…）。
        scale: CSA DISPLAY scale。
        movable: SIG_NAME_ON_WIRE=True；PIN_TEXT=False。
        priority: 0=SIG_NAME,1=LOCATION/VALUE,2=PORT,3=PIN_TEXT。
        net_key: 所属网（SIG_NAME 对齐/差分对用）。
        origin: 初始锚点（差分相对位移）。
        wire_min_x: 所属网 WIRE 的最小 x（网络名 x 对齐用，0=未知）。
    """

    key: str
    kind: str
    text: str
    anchor: tuple[int, int]
    font_size: int = 40
    scale: float = _SCALE_VALUE
    movable: bool = True
    priority: int = 1
    net_key: str = ""
    origin: tuple[int, int] = field(default=(0, 0))
    wire_min_x: int = 0
    orient: int = 0
    """Phase XXII D7: dehdl 旋转角（90/180/270；0 = 不输出 R 行）。

    VALUE/$LOCATION 标签方向随元件（与锚点旋转同源 ``rot_dehdl``）。
    """

    def __post_init__(self) -> None:
        if self.origin == (0, 0):
            self.origin = self.anchor

    def bbox(self) -> tuple[int, int, int, int]:
        """估算文本 bbox（左下角锚点 + 保守宽度/高度）。

        Returns:
            (x0, y0, x1, y1) 绝对矩形。
        """
        return TextLayoutOptimizer.estimate_bbox(
            self.text, self.anchor, self.font_size, self.scale,
        )


@dataclass
class TextLayoutResult:
    """D1 文本布局解算结果。"""

    offsets: dict[str, tuple[int, int]] = field(default_factory=dict)
    collisions_before: int = 0
    collisions_after: int = 0
    unresolved: list[tuple[str, str]] = field(default_factory=list)
    net_align: float = 0.0
    port_align: float = 0.0
    diff_ok: int = 0
    diff_total: int = 0
    label_orient: dict[str, int] = field(default_factory=dict)
    """Phase XXII D7: ``key → dehdl 旋转角``（VALUE/$LOCATION 标签方向随
    元件 R 行）。``optimize`` 末尾从 items 收集；0 = 不输出 R 行。"""


class TextLayoutOptimizer:
    """标签去冲突 + 对齐（只动标签坐标，绝不碰 LASTPIN/WIRE）。"""

    CHAR_WIDTH_FACTOR: float = 0.65
    LINE_HEIGHT_FACTOR: float = 1.2
    PADDING: int = 12
    MIN_TEXT_W: int = 75
    ALIGN_NET_LEFT_GRID: float = 7.5  # 网络名左对齐 7.5 格点（= 375 单位）
    GRID: int = 25

    def __init__(self, cfg: Optional[object] = None) -> None:
        """Initialize with optional TextLayoutCfg (reads factors)."""
        self.cfg = cfg
        if cfg is not None:
            self.CHAR_WIDTH_FACTOR = float(
                getattr(cfg, "char_width_factor", self.CHAR_WIDTH_FACTOR)
            )
            self.LINE_HEIGHT_FACTOR = float(
                getattr(cfg, "line_height_factor", self.LINE_HEIGHT_FACTOR)
            )
            self.PADDING = int(getattr(cfg, "padding", self.PADDING))
            self.MIN_TEXT_W = int(getattr(cfg, "min_text_w", self.MIN_TEXT_W))

    # ------------------------------------------------------------------
    #  Collection
    # ------------------------------------------------------------------

    def collect_text_items(
        self,
        page_conn,
        body_coords: dict[str, tuple[int, int]],
        pin_coords: dict[str, tuple[int, int]],
        routed_nets: dict[str, "RoutedNet"],
        net_pin_map: Optional[dict[str, list]] = None,
        ioport_positions: Optional[list[tuple[int, int]]] = None,
    ) -> list[TextItem]:
        """收集页面可见文本（VALUE/$LOCATION/PIN_TEXT/SIG_NAME/PORT）。

        Args:
            page_conn: PageConnectivity。
            body_coords: refdes → body (x, y)。
            pin_coords: "refdes.pin" → 绝对引脚坐标。
            routed_nets: ``{net_display: RoutedNet}``（布线结果）。
            net_pin_map: csa 的 net_pin_map（用于 source-pin 判定）；
                缺省时从 routed_nets 推导。
            ioport_positions: 实际 IOPORT 位置列表（csa 的
                ``_ioport_position_cfg`` 输出；缺省用默认位置公式）。

        Returns:
            TextItem 列表。
        """
        items: list[TextItem] = []

        # ── 元件标签（VALUE / $LOCATION）────────────────────────
        # Phase XVII P0-4 (问题 #10/#13): 标签基准偏移随旋转（与引脚
        # 同源 rotate_point，DEHDL R 行同步）—— text_layout 收集的锚点
        # 必须与 csa_writer 实际输出一致，否则 offsets 解算基于错误锚点。
        from .coord_transform import rotate_point
        for irec in page_conn.instances:
            if irec.is_power_symbol:
                continue
            x, y = body_coords.get(irec.refdes, (0, 0))
            rot = int(getattr(irec, "rotation", 0) or 0)
            # EDIF 角度 → DEHDL R 行角度（90↔270 互换，与 csa_writer
            # _dehdl_rotation 一致；避免顶层 import 循环依赖）。
            rot_dehdl = rot
            if rot_dehdl == 90:
                rot_dehdl = 270
            elif rot_dehdl == 270:
                rot_dehdl = 90
            _vbase = rotate_point(-5, -50, rot_dehdl)
            _lbase = rotate_point(-5, 220, rot_dehdl)
            value = getattr(irec, "value", "") or irec.refdes
            items.append(TextItem(
                key=f"{irec.refdes}.{KIND_VALUE}", kind=KIND_VALUE,
                text=str(value),
                anchor=(x + _vbase[0], y + _vbase[1]),
                font_size=40, scale=_SCALE_VALUE,
                movable=True, priority=1,
                orient=rot_dehdl,  # Phase XXII D7: 标签方向随元件 R 行
            ))
            items.append(TextItem(
                key=f"{irec.refdes}.{KIND_LOCATION}", kind=KIND_LOCATION,
                text=str(irec.refdes),
                anchor=(x + _lbase[0], y + _lbase[1]),
                font_size=40, scale=_SCALE_VALUE,
                movable=True, priority=1,
                orient=rot_dehdl,  # Phase XXII D7
            ))

            # ── PIN_TEXT（禁动 —— 锚点即 LASTPIN）──────────────
            for pre in irec.pins:
                coord = pin_coords.get(f"{irec.refdes}.{pre.pin_number}")
                if coord is None:
                    continue
                items.append(TextItem(
                    key=f"{irec.refdes}.{pre.pin_number}.{KIND_PIN_TEXT}",
                    kind=KIND_PIN_TEXT, text=str(pre.pin_number),
                    anchor=(coord[0] - 10, coord[1] + 10),
                    font_size=24, scale=_SCALE_PN,
                    movable=False, priority=3,
                ))

        # ── SIG_NAME（source pin 上 → 禁动；否则线上 → 可动）────
        sources = self._compute_source_pins(net_pin_map, routed_nets)
        for net_display, routed in routed_nets.items():
            if not routed.pins:
                continue
            first = routed.pins[0]
            on_pin = any(
                f"{p.get('refdes','')}.{p.get('pin','')}" in sources
                for p in (net_pin_map or {}).get(net_display, [])
                if isinstance(p, dict)
            ) if net_pin_map else False
            wire_min_x = 0
            if routed.wires:
                wire_min_x = min(
                    min(w.x1, w.x2) for w in routed.wires
                )
            if on_pin:
                items.append(TextItem(
                    key=f"{net_display}.{KIND_SIG_NAME}", kind=KIND_SIG_NAME,
                    text=net_display, anchor=(first[0] + 10, first[1] + 10),
                    font_size=24, scale=_SCALE_SIG_NAME,
                    movable=False, priority=0,
                    net_key=net_display, wire_min_x=wire_min_x,
                ))
            else:
                items.append(TextItem(
                    key=f"{net_display}.{KIND_SIG_NAME}", kind=KIND_SIG_NAME,
                    text=net_display, anchor=(first[0], first[1]),
                    font_size=24, scale=_SCALE_SIG_NAME,
                    movable=True, priority=0,
                    net_key=net_display, wire_min_x=wire_min_x,
                ))

        # ── PORT（IOPORT 标签；位置公式与 csa _ioport_position 一致）
        for idx, op in enumerate(getattr(page_conn, "off_pages", []) or []):
            name = str(op.get("name", "") or f"OFFPAGE_{idx}")
            if ioport_positions is not None and idx < len(ioport_positions):
                px, py = ioport_positions[idx]
            else:
                px, py = self._ioport_position(idx)
            items.append(TextItem(
                key=f"PORT.{name}.HDL_PORT", kind=KIND_PORT,
                text=name, anchor=(px + 325, py - 125),
                font_size=32, scale=_SCALE_IOPORT,
                movable=True, priority=2,
            ))

        return items

    # ------------------------------------------------------------------
    #  Collision detection / resolution
    # ------------------------------------------------------------------

    def detect_collisions(
        self, items: list[TextItem],
    ) -> list[tuple[TextItem, TextItem, tuple[int, int, int, int]]]:
        """O(n²) 两两 bbox 相交检测。

        Args:
            items: 文本条目列表（页面文本 < 500，可接受）。

        Returns:
            ``[(a, b, overlap_bbox)]`` 碰撞列表。
        """
        collisions: list[tuple[TextItem, TextItem, tuple[int, int, int, int]]] = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                ov = self._intersection(a.bbox(), b.bbox())
                if ov is not None:
                    collisions.append((a, b, ov))
        return collisions

    def resolve(
        self,
        items: list[TextItem],
        collisions: list[tuple[TextItem, TextItem, tuple[int, int, int, int]]],
    ) -> TextLayoutResult:
        """按优先级微调偏移（25 网格），迭代多轮。

        Args:
            items: 文本条目列表（原地修改 anchor）。
            collisions: detect_collisions 的结果。

        Returns:
            TextLayoutResult（offsets / 前后碰撞数 / 未解决列表）。
        """
        before = len(collisions)
        unresolved: list[tuple[str, str]] = []
        # Phase XIV: 可动标签先 snap 到 25 网格（原锚点 x-5/y+220 偏 5，
        # 微调后仍须留在网格；偏移量包含 snap 修正）。
        for it in items:
            if it.movable and (it.anchor[0] % self.GRID or it.anchor[1] % self.GRID):
                it.anchor = (
                    self._snap(it.anchor[0]), self._snap(it.anchor[1]),
                )
        # snap 后 bbox 微移 → 重新检测碰撞（保证解算基于最终锚点）。
        collisions = self.detect_collisions(items)
        before = len(collisions)
        max_iter = 4
        for _ in range(max_iter):
            changed = False
            for a, b, _ov in collisions:
                if a.priority > b.priority:
                    a, b = b, a
                mover = a if a.movable else (b if b.movable else None)
                if mover is None:
                    if (a.key, b.key) not in unresolved:
                        unresolved.append((a.key, b.key))
                    continue
                blocker = b if mover is a else a
                candidate = self._candidate_for(mover, blocker)
                if candidate is not None and candidate != mover.anchor:
                    mover.anchor = candidate
                    changed = True
            if not changed:
                break

        after = len(self.detect_collisions(items))
        offsets: dict[str, tuple[int, int]] = {}
        for it in items:
            dx = it.anchor[0] - it.origin[0]
            dy = it.anchor[1] - it.origin[1]
            if dx or dy:
                offsets[it.key] = (dx, dy)
        # 未解决 = 最终碰撞中双方都不可动的对（精确统计，非迭代中间值）。
        unresolved = [
            (a.key, b.key)
            for a, b, _ov in self.detect_collisions(items)
            if not a.movable and not b.movable
        ]
        return TextLayoutResult(
            offsets=offsets,
            collisions_before=before,
            collisions_after=after,
            unresolved=unresolved,
        )

    # ------------------------------------------------------------------
    #  Alignment (network names / ports / diff pairs)
    # ------------------------------------------------------------------

    def align_net_names(self, items: list[TextItem]) -> None:
        """网络名 x 对齐：x = snap25(trunk_min_x + 375)（仅线上标签）。

        Args:
            items: 文本条目列表（原地修改 SIG_NAME 线上标签的 x）。
        """
        for it in items:
            if it.kind != KIND_SIG_NAME or not it.movable:
                continue
            if it.wire_min_x == 0:
                continue
            align_x = self._snap(it.wire_min_x + int(self.ALIGN_NET_LEFT_GRID * 50))
            it.anchor = (align_x, it.anchor[1])

    def align_ports(self, items: list[TextItem]) -> float:
        """同侧 Port 对齐：右侧缘 x 统一、y 等间距（rank 连续）。

        以第一个 PORT（y 最大者）为锚：edge_x = 其 x，y 向下每 100
        等间距排布。确定性规则（不依赖众数/哈希序）。

        Args:
            items: 文本条目列表。

        Returns:
            对齐率（0.0-1.0，已对齐 PORT / 总 PORT）。
        """
        ports = sorted(
            [it for it in items if it.kind == KIND_PORT],
            key=lambda t: (-t.anchor[1], t.anchor[0]),
        )
        if not ports:
            return 1.0
        first = ports[0]
        edge_x = self._snap(first.anchor[0])
        base_y = self._snap(first.anchor[1])
        ok = 0
        for idx, it in enumerate(ports):
            target_y = self._snap(base_y - idx * 100)
            if it.anchor[0] == edge_x and it.anchor[1] == target_y:
                ok += 1
            else:
                it.anchor = (edge_x, target_y)
        return ok / len(ports) if ports else 1.0

    def enforce_diff_pairs(
        self, items: list[TextItem], net_names: Optional[list[str]] = None,
    ) -> tuple[int, int]:
        """差分对标签 P 上 N 下（仅线上可动标签；禁动标签跳过）。

        Args:
            items: 文本条目列表。
            net_names: 可选网名列表；缺省从 items 的 net_key 收集。

        Returns:
            (ok, total) 差分对方向正确数 / 总数。
        """
        names = list(net_names) if net_names else sorted(
            {it.net_key for it in items if it.net_key}
        )
        by_key: dict[str, TextItem] = {
            it.key: it for it in items if it.kind == KIND_SIG_NAME
        }
        ok = 0
        total = 0
        seen: set[str] = set()
        for name in names:
            parsed = self._diff_base(name)
            if parsed is None:
                continue
            base, _suffix = parsed
            if base in seen:
                continue
            seen.add(base)
            p_item = by_key.get(f"{base}_P.{KIND_SIG_NAME}")
            n_item = by_key.get(f"{base}_N.{KIND_SIG_NAME}")
            if p_item is None or n_item is None:
                continue
            total += 1
            if not (p_item.movable or n_item.movable):
                ok += 1  # 禁动 —— 不强行破坏 LASTPIN，视为维持现状
                continue
            if p_item.anchor[1] <= n_item.anchor[1]:
                # P 在 N 下方 → 上移 P（保持 25 网格）
                mover = p_item if p_item.movable else n_item
                if mover is p_item:
                    mover.anchor = (
                        mover.anchor[0], self._snap(n_item.anchor[1] + self.GRID),
                    )
                else:
                    mover.anchor = (
                        mover.anchor[0], self._snap(p_item.anchor[1] - self.GRID),
                    )
                ok += 1
            else:
                ok += 1
        return ok, total

    # ------------------------------------------------------------------
    #  Main entry
    # ------------------------------------------------------------------

    def optimize(
        self,
        page_conn,
        body_coords: dict[str, tuple[int, int]],
        pin_coords: dict[str, tuple[int, int]],
        routed_nets: dict[str, "RoutedNet"],
        net_pin_map: Optional[dict[str, list]] = None,
        ioport_positions: Optional[list[tuple[int, int]]] = None,
    ) -> TextLayoutResult:
        """收集 → 检测 → 解算 → 对齐（对齐开关由 cfg 控制）。

        Args:
            page_conn: PageConnectivity。
            body_coords: refdes → body (x, y)。
            pin_coords: "refdes.pin" → 绝对引脚坐标。
            routed_nets: ``{net_display: RoutedNet}``。
            net_pin_map: 可选 net_pin_map（source-pin 判定）。
            ioport_positions: 实际 IOPORT 位置列表（csa 传入）。

        Returns:
            TextLayoutResult（offsets 供 csa_writer 标签行使用）。
        """
        items = self.collect_text_items(
            page_conn, body_coords, pin_coords, routed_nets, net_pin_map,
            ioport_positions=ioport_positions,
        )
        collisions = self.detect_collisions(items)
        result = self.resolve(items, collisions)

        net_align = 0.0
        port_align = 1.0
        diff_ok = 0
        diff_total = 0
        cfg = getattr(self, "cfg", None)
        if cfg is None or getattr(cfg, "align_net_names", True):
            self.align_net_names(items)
            net_align = self._net_align_rate(items)
        if cfg is None or getattr(cfg, "align_ports", True):
            port_align = self.align_ports(items)
        if cfg is None or getattr(cfg, "diff_pair_pn", True):
            diff_ok, diff_total = self.enforce_diff_pairs(items)

        result.collisions_after = len(self.detect_collisions(items))
        result.unresolved = [
            (a.key, b.key)
            for a, b, _ov in self.detect_collisions(items)
            if not a.movable and not b.movable
        ]
        result.net_align = net_align
        result.port_align = port_align
        result.diff_ok = diff_ok
        result.diff_total = diff_total
        # 对齐后重新收集 offsets
        result.offsets = {}
        for it in items:
            dx = it.anchor[0] - it.origin[0]
            dy = it.anchor[1] - it.origin[1]
            if dx or dy:
                result.offsets[it.key] = (dx, dy)
        # Phase XXII D7: 标签方向随元件 —— key → dehdl 旋转角（0 不输出）。
        result.label_orient = {
            it.key: int(it.orient or 0) for it in items if it.orient
        }
        return result

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @classmethod
    def estimate_bbox(
        cls, text: str, anchor: tuple[int, int], font_size: int, scale: float,
    ) -> tuple[int, int, int, int]:
        """保守估算文本 bbox（左下角锚点）。

        Args:
            text: 显示文本。
            anchor: 锚点 (x, y)。
            font_size: css 高度。
            scale: CSA DISPLAY scale。

        Returns:
            (x0, y0, x1, y1)。
        """
        x, y = int(anchor[0]), int(anchor[1])
        char_w = font_size * scale * cls.CHAR_WIDTH_FACTOR
        height = font_size * scale * cls.LINE_HEIGHT_FACTOR
        width = max(cls.MIN_TEXT_W, len(str(text)) * char_w + cls.PADDING * 2)
        return (
            x - cls.PADDING,
            y - cls.PADDING,
            x + int(width) + cls.PADDING,
            y + int(height) + cls.PADDING,
        )

    @staticmethod
    def _intersection(
        a: tuple[int, int, int, int], b: tuple[int, int, int, int],
    ) -> Optional[tuple[int, int, int, int]]:
        """两矩形相交矩形；不相交返回 None。"""
        x0 = max(a[0], b[0])
        y0 = max(a[1], b[1])
        x1 = min(a[2], b[2])
        y1 = min(a[3], b[3])
        if x0 < x1 and y0 < y1:
            return (x0, y0, x1, y1)
        return None

    @staticmethod
    def _bbox_overlaps(
        a: tuple[int, int, int, int], b: tuple[int, int, int, int],
    ) -> bool:
        return TextLayoutOptimizer._intersection(a, b) is not None

    def _bbox_at(
        self, anchor: tuple[int, int], it: TextItem,
    ) -> tuple[int, int, int, int]:
        return self.estimate_bbox(it.text, anchor, it.font_size, it.scale)

    def _candidate_for(
        self, mover: TextItem, blocker: TextItem,
    ) -> Optional[tuple[int, int]]:
        """为可动标签找第一个不与 blocker bbox 相交的 25 网格锚点。

        SIG_NAME（线上）沿 trunk 滑动（只动 x 或只动 y）；
        其它（VALUE/LOCATION）8 方向就近最小移动。
        """
        if mover.kind == KIND_SIG_NAME and mover.movable:
            return self._slide_along_trunk(mover, blocker)
        return self._nearest_free_grid(mover, blocker)

    def _slide_along_trunk(
        self, mover: TextItem, blocker: TextItem,
    ) -> Optional[tuple[int, int]]:
        """SIG_NAME 沿 trunk 滑动：先 x 后 y，各 ±25×1..4 步。"""
        x, y = mover.anchor
        blocker_bbox = blocker.bbox()
        for k in range(1, 5):
            for cand in ((x + k * self.GRID, y), (x - k * self.GRID, y)):
                if not self._bbox_overlaps(self._bbox_at(cand, mover), blocker_bbox):
                    return cand
        for k in range(1, 5):
            for cand in ((x, y + k * self.GRID), (x, y - k * self.GRID)):
                if not self._bbox_overlaps(self._bbox_at(cand, mover), blocker_bbox):
                    return cand
        return None

    def _nearest_free_grid(
        self, mover: TextItem, blocker: TextItem,
    ) -> Optional[tuple[int, int]]:
        """8 方向最近 25 网格点（距离 1..4 格）。"""
        x, y = mover.anchor
        blocker_bbox = blocker.bbox()
        dirs = (
            (0, 1), (0, -1), (1, 0), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        )
        for d in range(1, 5):
            for dx, dy in dirs:
                cand = (x + dx * d * self.GRID, y + dy * d * self.GRID)
                if not self._bbox_overlaps(self._bbox_at(cand, mover), blocker_bbox):
                    return cand
        return None

    @staticmethod
    def _snap(value: float) -> int:
        """Round a coordinate to the DEHDL grid (nearest multiple of 25)."""
        return int(round(value / 25.0) * 25)

    @staticmethod
    def _ioport_position(index: int) -> tuple[int, int]:
        """IOPORT 位置（与 csa_writer._ioport_position 一致）。"""
        x = -600 - (index % 8) * 100
        y = 7300 - (index // 8) * 300
        return x, y

    @staticmethod
    def _compute_source_pins(
        net_pin_map: Optional[dict[str, list]],
        routed_nets: dict[str, "RoutedNet"],
    ) -> set[str]:
        """选择每网一个 source pin（SIG_NAME 挂在引脚上）。"""
        sources: set[str] = set()
        if net_pin_map:
            for pins in net_pin_map.values():
                if not pins:
                    continue
                real = [
                    p for p in pins
                    if not str(p.get("refdes", "")).startswith("IOPORT_")
                ]
                candidates = real or pins
                power_pins = [p for p in candidates if p.get("is_power_symbol")]
                chosen = power_pins[0] if power_pins else candidates[0]
                sources.add(f"{chosen['refdes']}.{chosen['pin']}")
        return sources

    @staticmethod
    def _net_align_rate(items: list[TextItem]) -> float:
        """网络名 x 对齐率：x == snap25(wire_min_x + 375) 的线上标签占比。"""
        wire_labels = [
            it for it in items
            if it.kind == KIND_SIG_NAME and it.movable and it.wire_min_x
        ]
        if not wire_labels:
            return 1.0
        ok = 0
        for it in wire_labels:
            target = TextLayoutOptimizer._snap(
                it.wire_min_x + int(TextLayoutOptimizer.ALIGN_NET_LEFT_GRID * 50)
            )
            if it.anchor[0] == target:
                ok += 1
        return ok / len(wire_labels)

    @staticmethod
    def _diff_base(name: str) -> tuple[str, str] | None:
        """识别差分对后缀：返回 (base, suffix)；无后缀返回 None。"""
        for suffix in _DIFF_PATTERN:
            if name.endswith(suffix) and len(name) > len(suffix):
                return name[: -len(suffix)], suffix
        return None
