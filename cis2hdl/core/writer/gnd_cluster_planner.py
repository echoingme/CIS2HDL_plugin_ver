"""GndClusterPlanner — GND 就近共用 + 簇内并联规划（Phase XVIII R6/R8）。

用户实测问题（B4）：GND 一页就 1 个；并联电容（C52/455/53/459/462）
各自单独引线接地而非就近共用；GND 符号落在元件正上方且连线穿元件；
GND 引脚连线不先延伸就拐弯。

本模块在既有 ``csa_writer._plan_and_inject_gnd_symbols``（Phase XVII 三期
GND 聚类）之上新增能力（``gnd_distribution.parallel_short=true`` 时）：

* ``route_cluster_parallel`` —— 簇内引脚**先在引脚附近并联（hub 短接）**
  再统一 1 条引出到 GND 符号。支持两种调用：
  - 设计 API：``route_cluster_parallel(cluster_pins, hub, outlines, stub_lead)``
    → 簇内短接 WIRE 段（引脚 → hub，每段先外引 stub_lead 再折向 hub）；
  - 旧式聚类 API：``route_cluster_parallel(pins, max_dist, gnd_coord)``
    → ``ParallelHub`` 列表（贪心最近邻，``parallel_short_dist`` 判定）。
* ``hub_for`` —— 簇 hub（包围盒中心 snap25；落 outline 内沿最小分离
  向量外推）；
* ``hub_short_wires`` —— 把 ``ParallelHub`` 转成簇内短接 WIRE 段；
* ``hub_to_symbol_wire`` —— 从 hub 到 GND 符号引脚的"1 条引出线"；
* ``place_gnd_symbol`` —— GND 符号避让元件 outline / 引脚禁区 / 页边
  （margin=50 + pin_avoid_radius=50 + edge_clearance=100）。

数据源铁律（STANDARDS Part I）：本模块只消费既有 DesignConnectivity
模型与 GND 簇计划（csa_writer 传入），不自行解析/自造数据；所有输出
坐标 ``_snap25`` 网格。

设计原则：独立模块 + 配置开关（``gnd_distribution.parallel_short``
默认 true，但 ``gnd_distribution.enabled`` 默认 false —— 开关整体
控制是否启用 GND 分布）；函数 <50 行；禁硬编码（数值进 routing.yaml）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

#: 25 网格（与全工程一致）。
_GRID: int = 25
#: GND_POWER 引脚相对 body 偏移（golden R3c，与 _power_pin_offset 同源）。
_GND_PIN_OFFSET: tuple[int, int] = (50, 100)
#: hub 外推避让 margin（= overlap.avoid_margin 默认 50）。
_HUB_PUSH_MARGIN: int = 50
#: C 纸页面边界（R5 边缘冗余区）。
_PAGE_X0: int = -10750
_PAGE_X1: int = -550
_PAGE_Y0: int = 400
_PAGE_Y1: int = 7200
#: Phase XXIII P1-3：页面 1/4 分块（2×2 象限）中线。
_BLOCK_X_MID: int = (_PAGE_X0 + _PAGE_X1) // 2
_BLOCK_Y_MID: int = (_PAGE_Y0 + _PAGE_Y1) // 2

#: 线段 = (x1, y1, x2, y2)；点 = (x, y)。
Segment = tuple[int, int, int, int]
Point = tuple[int, int]
Rect = tuple[int, int, int, int]


def _snap25(v: float) -> int:
    """Snap a coordinate to the 25-unit grid."""
    return int(round(v / _GRID)) * _GRID


@dataclass
class ParallelHub:
    """一个"簇内并联 hub"：一组同信号引脚在引脚附近短接后统一引出。

    Attributes:
        net: 信号名（如 ``GND`` / ``GND\\g``）。
        pin_coords: 参与并联的引脚绝对坐标列表。
        hub: 汇聚点绝对坐标（25 网格；通常取引脚包围盒中心）。
        outlet: 引出点绝对坐标（hub 向 GND 符号方向的引出端点）。
    """

    net: str
    pin_coords: list[tuple[int, int]] = field(default_factory=list)
    hub: tuple[int, int] = (0, 0)
    outlet: tuple[int, int] = (0, 0)

    @property
    def pin_count(self) -> int:
        """参与并联的引脚数（≥2 才有意义）。"""
        return len(self.pin_coords)


def _bbox_center(points: Sequence[tuple[int, int]]) -> tuple[int, int]:
    """包围盒中心（snap 25）。"""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if not xs:
        return (0, 0)
    return (_snap25((min(xs) + max(xs)) / 2), _snap25((min(ys) + max(ys)) / 2))


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """曼哈顿距离（25 网格对齐后仍整数）。"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _is_net_pin_style(pins: Sequence) -> bool:
    """True = 旧式 ``[(net, (x, y))]`` 输入（否则为坐标列表）。"""
    if not pins:
        return False
    first = pins[0]
    return (
        isinstance(first, (list, tuple)) and len(first) == 2
        and isinstance(first[0], str)
    )


def route_cluster_parallel(
    cluster_pins: Sequence,
    hub: Point | None = None,
    outlines: Iterable[Rect] = (),
    stub_lead: int = 100,
    max_dist: int = 500,
    gnd_coord: Point | None = None,
):
    """簇内引脚并联短接（双 API，R6/R8）。

    设计 API（R6 主线）：``route_cluster_parallel(cluster_pins, hub,
    outlines, stub_lead)`` → 每个引脚 → hub 的短接 WIRE 段（每段先沿
    引脚外引 ``stub_lead`` 再折向 hub，三段式；端点 = 引脚坐标不变）。

    旧式聚类 API（兼容既有调用）：``route_cluster_parallel(pins,
    max_dist, gnd_coord)``（``pins=[(net, (x, y))]``）→ ``ParallelHub``
    列表（贪心最近邻，距离 ≤ ``max_dist`` 的引脚并入同一簇）。

    Args:
        cluster_pins: 簇内引脚坐标列表（设计 API）或 ``[(net, coord)]``
            （旧式聚类 API）。
        hub: 簇 hub（设计 API；缺省用 ``hub_for`` 计算）。
        outlines: 元件 outline（设计 API 避让，可选）。
        stub_lead: 引脚外引距离（设计 API，默认 100）。
        max_dist: 并联判定距离阈值（旧式 API，``parallel_short_dist``）。
        gnd_coord: GND 符号坐标（旧式 API outlet 方向，可选）。

    Returns:
        设计 API → 正交 WIRE 段列表；旧式 API → ``ParallelHub`` 列表。
    """
    if _is_net_pin_style(cluster_pins):
        return _cluster_hubs(
            cluster_pins, max_dist=max_dist, gnd_coord=gnd_coord,
        )
    pins = [(int(p[0]), int(p[1])) for p in cluster_pins]
    if not pins:
        return []
    if hub is None:
        h = hub_for(pins, outlines)
    else:
        h = (int(hub[0]), int(hub[1]))
    out: list[Segment] = []
    for pin in pins:
        out.extend(_pin_to_hub_stub(pin, h, outlines, stub_lead))
    return out


def _cluster_hubs(
    pins: Sequence[tuple[str, tuple[int, int]]],
    max_dist: int = 500,
    gnd_coord: tuple[int, int] | None = None,
) -> list[ParallelHub]:
    """贪心最近邻：把一组同信号引脚按就近原则聚成 hub 并联簇。

    从第一个引脚出发，把距离 ≤ ``max_dist`` 的引脚并入同一簇（曼哈顿
    距离）；每个簇生成一个 hub（包围盒中心，snap 25）与一个 outlet
    （hub 向 GND 符号方向偏移 50）。

    Args:
        pins: ``[(net, (x, y))]`` 同信号引脚列表（如 GND 网全部引脚）。
        max_dist: 并联判定距离阈值（``parallel_short_dist``，默认 500）。
        gnd_coord: GND 符号坐标（用于 outlet 方向；None 时默认 +y）。

    Returns:
        ``ParallelHub`` 列表；``pin_count < 2`` 的簇不产生 hub（返回空）。
    """
    if not pins:
        return []
    coords: list[tuple[int, int]] = [c for _n, c in pins]
    net = str(pins[0][0] or "GND")
    used: list[bool] = [False] * len(coords)
    hubs: list[ParallelHub] = []

    for i in range(len(coords)):
        if used[i]:
            continue
        cluster: list[tuple[int, int]] = [coords[i]]
        used[i] = True
        # 贪心并入近邻（允许链式：新成员再吸引更远引脚）。
        changed = True
        while changed:
            changed = False
            for j in range(len(coords)):
                if used[j]:
                    continue
                if any(_manhattan(coords[j], c) <= max_dist for c in cluster):
                    cluster.append(coords[j])
                    used[j] = True
                    changed = True
        if len(cluster) < 2:
            continue
        hub = _bbox_center(cluster)
        # outlet：hub 向 GND 符号方向外引 50（无 GND 时 +y）。
        if gnd_coord is not None:
            dx = 50 if gnd_coord[0] > hub[0] else -50
            dy = 50 if gnd_coord[1] > hub[1] else -50
        else:
            dx, dy = 0, 50
        outlet = (_snap25(hub[0] + dx), _snap25(hub[1] + dy))
        hubs.append(ParallelHub(net=net, pin_coords=cluster, hub=hub, outlet=outlet))
        logger.debug(
            "GND parallel hub: %d pins → hub %s outlet %s",
            len(cluster), hub, outlet,
        )
    return hubs


def _point_in_rect(p: Point, rect: Rect) -> bool:
    """点是否在矩形内（含边界）。"""
    x, y = p
    x0, y0, x1, y1 = rect
    return min(x0, x1) <= x <= max(x0, x1) and min(y0, y1) <= y <= max(y0, y1)


def _push_out_of_rect(p: Point, rect: Rect, margin: int) -> Point:
    """点相对矩形的最小分离向量外推（推出膨胀矩形外一格外）。

    Args:
        p: 点坐标。
        rect: 矩形（原始坐标）。
        margin: 外推边距（膨胀量）。

    Returns:
        外推后的点坐标（snap 25 网格；严格在膨胀矩形外）。
    """
    x, y = p
    lo_x, hi_x = min(rect[0], rect[2]), max(rect[0], rect[2])
    lo_y, hi_y = min(rect[1], rect[3]), max(rect[1], rect[3])
    candidates = (
        (hi_x + margin + _GRID, y),
        (lo_x - margin - _GRID, y),
        (x, hi_y + margin + _GRID),
        (x, lo_y - margin - _GRID),
    )
    best = min(candidates, key=lambda c: abs(c[0] - x) + abs(c[1] - y))
    return (_snap25(best[0]), _snap25(best[1]))


def hub_for(
    cluster_pins: Sequence[Point],
    outlines: Iterable[Rect] = (),
) -> Point:
    """簇 hub = 包围盒中心（snap 25）；落 outline 内沿最小分离向量外推。

    Args:
        cluster_pins: 簇内引脚坐标列表。
        outlines: 元件 outline 矩形（避让，可选）。

    Returns:
        ``(x, y)`` 全 25 网格的 hub 坐标。
    """
    pins = [(int(p[0]), int(p[1])) for p in cluster_pins]
    if not pins:
        return (0, 0)
    obs = [tuple(int(v) for v in o) for o in outlines]
    cx, cy = _bbox_center(pins)
    for _ in range(16):
        hit = next((o for o in obs if _point_in_rect((cx, cy), o)), None)
        if hit is None:
            break
        cx, cy = _push_out_of_rect((cx, cy), hit, margin=_HUB_PUSH_MARGIN)
    return (cx, cy)


def _seg_intersects_rect(seg: Segment, rect: Rect) -> bool:
    """线段是否与矩形相交（含端点贴边）。"""
    x1, y1, x2, y2 = seg
    lo_x, hi_x = min(rect[0], rect[2]), max(rect[0], rect[2])
    lo_y, hi_y = min(rect[1], rect[3]), max(rect[1], rect[3])
    if x1 == x2:  # vertical
        return lo_x <= x1 <= hi_x and min(y1, y2) <= hi_y and max(y1, y2) >= lo_y
    if y1 == y2:  # horizontal
        return lo_y <= y1 <= hi_y and min(x1, x2) <= hi_x and max(x1, x2) >= lo_x
    if (lo_x <= x1 <= hi_x and lo_y <= y1 <= hi_y) or \
       (lo_x <= x2 <= hi_x and lo_y <= y2 <= hi_y):
        return True
    return False


def _pin_to_hub_stub(
    pin: Point, hub: Point,
    outlines: Sequence[Rect],
    stub_lead: int,
) -> list[Segment]:
    """单引脚 → hub 短接段（R5 复用 + Phase XXII QA 修复 Issue 1）。

    Phase XXII QA 修复：优先 **2 段 L 路径**（pin→corner→hub，端点不变）
    —— 簇内引脚间距 ≤ ``parallel_short_dist`` 已很近，无需每引脚三段式
    引出（显著降低 WIRE 段数）。L 路径穿 outline（或 pin==hub 时）回退
    原三段式路径（R5：延伸→折线→调头，避让）。

    Args:
        pin: 引脚坐标（端点不动）。
        hub: 簇 hub 坐标。
        outlines: 元件 outline（避让）。
        stub_lead: 引出距离（回退路径用）。

    Returns:
        2-4 段正交 WIRE 段（端点 pin 不变，全 25 网格）。
    """
    px, py = int(pin[0]), int(pin[1])
    hx, hy = int(hub[0]), int(hub[1])
    obs = [tuple(int(v) for v in o) for o in outlines]

    # ── 优先 2 段 L（两种角点，取第一个不与 outline 冲突的）────────
    _corner_choices: list[Point] = []
    if abs(hx - px) >= abs(hy - py):
        _corner_choices = [(hx, py), (px, hy)]
    else:
        _corner_choices = [(px, hy), (hx, py)]
    for _corner in _corner_choices:
        _l_out: list[Segment] = []
        for a, b in (((px, py), _corner), (_corner, (hx, hy))):
            if a != b:
                _l_out.append((a[0], a[1], b[0], b[1]))
        if not _l_out:
            break  # pin == hub → 回退原三段式（小回路）
        if not any(_seg_intersects_rect(s, o) for s in _l_out for o in obs):
            return _l_out

    # ── 回退：原三段式短接段（R5：延伸→折线→调头）──────────────────
    dx, dy = hx - px, hy - py
    # 1. E：沿最大偏差轴外引 stub_lead（背离 hub）。
    if dx == 0 and dy == 0:
        ex, ey = px, _snap25(py - stub_lead)
        lead_axis = "y"
    elif abs(dx) >= abs(dy):
        ex = _snap25(px - (1 if dx > 0 else -1) * stub_lead)
        ey = py
        lead_axis = "x"
    else:
        ex = px
        ey = _snap25(py - (1 if dy > 0 else -1) * stub_lead)
        lead_axis = "y"

    def _path(j: Point) -> list[Segment]:
        jx, jy = j
        if abs(hx - jx) >= abs(hy - jy):
            corner = (hx, jy)
        else:
            corner = (jx, hy)
        out: list[Segment] = []
        for a, b in (
            ((px, py), (ex, ey)),
            ((ex, ey), (jx, jy)),
            ((jx, jy), corner),
            (corner, (hx, hy)),
        ):
            if a != b:
                out.append((a[0], a[1], b[0], b[1]))
        return out

    base_path = _path((ex, ey))
    if not any(_seg_intersects_rect(s, o) for s in base_path for o in obs):
        return base_path
    # 3. J 垂直方向外推（两个方向、递增 50，最多 6 次），取最近空闲。
    for k in range(1, 7):
        off = 150 + k * 50
        for sign in (1, -1):
            if lead_axis == "x":
                cand = (ex, _snap25(ey + sign * off))
            else:
                cand = (_snap25(ex + sign * off), ey)
            path = _path(cand)
            if not any(
                _seg_intersects_rect(s, o) for s in path for o in obs
            ):
                return path
    return base_path


def hub_short_wires(
    hub: ParallelHub,
    outlines: Sequence[Rect] = (),
    stub_lead: int = 100,
) -> list[Segment]:
    """把 ``ParallelHub`` 转成簇内短接 WIRE 段（引脚 → hub）。

    每个引脚先沿外引 ``stub_lead`` 再折向 hub（三段式，R5 复用）；
    hub 自身的引脚（pin == hub）无需段。返回段端点 = 引脚坐标不变。
    调用方负责从 hub 引出 1 条到 GND 符号（``hub_to_symbol_wire``）。

    Args:
        hub: ``route_cluster_parallel``（旧式 API）返回的 ParallelHub。
        outlines: 元件 outline（避让，可选）。
        stub_lead: 引脚外引距离（默认 100）。

    Returns:
        正交 WIRE 段列表（可能为空；全部 25 网格）。
    """
    out: list[Segment] = []
    for pin in hub.pin_coords:
        out.extend(_pin_to_hub_stub(pin, hub.hub, outlines, stub_lead))
    return out


def hub_to_symbol_wire(
    hub: Point, symbol_pin: Point,
    outlines: Sequence[Rect] = (),
) -> list[Segment]:
    """从簇 hub 到 GND 符号引脚的"1 条引出线"（正交 L，零长剔除）。

    Phase XXIII P1-3：``outlines`` 非空时检查 L 路径是否穿元件体
    （语义同 ``WireLayoutEngine._stub_direct_blocked`` 的 outline 检查）；
    受阻时在网格上试 90° 折线绕行（Z 路径，最多 2 次折弯），全部受阻
    回退第一条 L 路径（尽力而为，不阻塞电气连接）。

    Args:
        hub: 簇 hub（或 ParallelHub.outlet 引出点）。
        symbol_pin: GND 符号引脚坐标（body + pin_offset）。
        outlines: 元件 outline（避让，可选；默认空 = 零回归直连）。

    Returns:
        1-3 段正交 WIRE 段（可能为空）。
    """
    hx, hy = int(hub[0]), int(hub[1])
    sx, sy = int(symbol_pin[0]), int(symbol_pin[1])
    if (hx, hy) == (sx, sy):
        return []
    obs = [tuple(int(v) for v in o) for o in outlines]

    def _segs(pts: Sequence[Point]) -> list[Segment]:
        out: list[Segment] = []
        for a, b in zip(pts, pts[1:]):
            if a != b:
                out.append((a[0], a[1], b[0], b[1]))
        return out

    def _clear(segs: list[Segment]) -> bool:
        if not obs:
            return True
        return not any(_seg_intersects_rect(s, o) for s in segs for o in obs)

    def _l(corner: Point) -> list[Segment]:
        return _segs(((hx, hy), corner, (sx, sy)))

    # ── 1. 直接 L（两种角点，取第一个不穿 outline 的）────────────
    for corner in ((sx, hy), (hx, sy)):
        path = _l(corner)
        if _clear(path):
            return path
    if not obs:
        return _l((sx, hy))

    # ── 2. 90° 折线绕行（Z 路径，≤2 次折弯）─────────────────────
    # 候选：hub → (jx,hy) → (jx,sy) → symbol（x 方向错位）与
    #       hub → (hx,jy) → (sx,jy) → symbol（y 方向错位）。
    # 错位车道从 hub/符号坐标向两侧递增 50，最多 8 轮。
    step = 50
    for k in range(0, 9):
        offsets = [0] if k == 0 else [k * step, -k * step]
        for off in offsets:
            for jx in (hx + off, sx + off):
                path = _segs(((hx, hy), (jx, hy), (jx, sy), (sx, sy)))
                if len(path) <= 3 and _clear(path):
                    return path
            for jy in (hy + off, sy + off):
                path = _segs(((hx, hy), (hx, jy), (sx, jy), (sx, sy)))
                if len(path) <= 3 and _clear(path):
                    return path
    # ── 3. 回退：第一条 L 路径（密集页尽力而为）──────────────────
    logger.debug(
        "GND hub→symbol wire blocked near %s→%s → fallback L", hub, symbol_pin,
    )
    return _l((sx, hy))


def _start_point(
    candidate: Point | Sequence[Point],
    outlines: Sequence[Rect],
) -> Point:
    """归一化起点：候选点直接 snap；簇引脚列表取 hub。"""
    if (
        isinstance(candidate, (list, tuple))
        and len(candidate) > 0
        and isinstance(candidate[0], (list, tuple))
        and not isinstance(candidate[0], str)
    ):
        return hub_for(candidate, outlines)
    return (_snap25(candidate[0]), _snap25(candidate[1]))


def _page_band(edge_clearance: int) -> tuple:
    """页边冗余带（C 纸边界 ± edge_clearance）；0 = 无约束。"""
    if edge_clearance <= 0:
        return (None, None, None, None)
    return (
        _PAGE_X0 + edge_clearance,
        _PAGE_X1 - edge_clearance,
        _PAGE_Y0 + edge_clearance,
        _PAGE_Y1 - edge_clearance,
    )


def _symbol_spot_free(
    px: int, py: int,
    outlines: Sequence[Rect], margin: int,
    pin_points: set[Point], pin_offset: tuple[int, int],
    x_lo: int | None, x_hi: int | None,
    y_lo: int | None, y_hi: int | None,
    edge_clearance: int,
) -> bool:
    """GND 符号位置是否空闲（outline / 引脚禁区 / 页边）。"""
    if x_lo is not None:
        in_band = x_lo <= px <= x_hi and y_lo <= py <= y_hi
        near_origin_clear = px >= edge_clearance and py >= edge_clearance
        if not (in_band or near_origin_clear):
            return False
    ox, oy = int(pin_offset[0]), int(pin_offset[1])
    gnd_pin = (px + ox, py + oy)
    for (x0, y0, x1, y1) in outlines:
        if x0 - margin <= px <= x1 + margin and y0 - margin <= py <= y1 + margin:
            return False
        if x0 - margin <= gnd_pin[0] <= x1 + margin and \
           y0 - margin <= gnd_pin[1] <= y1 + margin:
            return False
    if pin_points and any(
        ((gnd_pin[0] - pp[0]) ** 2 + (gnd_pin[1] - pp[1]) ** 2) ** 0.5 < margin
        for pp in pin_points
    ):
        return False
    return True


def _spiral_search(
    x: int, y: int, free, max_tries: int, step: int,
) -> Point | None:
    """从 (x, y) 出发螺旋搜索第一个 ``free`` 位置（25 网格）。"""
    for ring in range(1, max_tries + 1):
        for dx in range(-ring * step, ring * step + 1, step):
            for dy in range(-ring * step, ring * step + 1, step):
                if max(abs(dx), abs(dy)) != ring * step:
                    continue
                px, py = _snap25(x + dx), _snap25(y + dy)
                if free(px, py):
                    return (px, py)
    return None


def place_gnd_symbol(
    candidate: Point | Sequence[Point],
    outlines: Sequence[tuple[int, int, int, int]] = (),
    margin: int = 50,
    max_tries: int = 12,
    step: int = 100,
    pin_points: Sequence[Point] | None = None,
    pin_offset: tuple[int, int] = _GND_PIN_OFFSET,
    edge_clearance: int = 0,
) -> tuple[int, int]:
    """找一个不落在任何元件 outline（含 margin 膨胀）内的 GND 符号位置。

    从候选点（或簇引脚列表的 hub）出发，按螺旋/步进搜索空闲格点
    （优先下方/右方等空旷方向），全部排除后取第一个空闲点。

    Phase XVIII R5/R6：候选须同时满足 —— body 点不在膨胀 outline 内、
    GND 引脚点（body + pin_offset）不在膨胀 outline 内、引脚点不进
    引脚禁区（距任一引脚 ≥ margin）、``edge_clearance>0`` 时不进入
    C 纸页边 ± edge_clearance 带（或距原点角 ≥ edge_clearance）。

    Args:
        candidate: 首选坐标（点 ``(x, y)``）或簇引脚列表（自动取 hub）。
        outlines: ``(x0, y0, x1, y1)`` 元件包围盒列表（绝对坐标）。
        margin: 元件外侧避让冗余区（``overlap.avoid_margin``，默认 50）。
        max_tries: 搜索最大环数。
        step: 搜索步长（默认 100，snap 25）。
        pin_points: 已占用引脚坐标（禁区，可选）。
        pin_offset: GND 引脚相对 body 偏移（默认 golden (50,100)）。
        edge_clearance: 页边冗余区（0 = 不检查页边）。

    Returns:
        空闲坐标（25 网格）；找不到时返回 hub 上方外推点。
    """
    x, y = _start_point(candidate, outlines)
    pts = (
        {(int(p[0]), int(p[1])) for p in pin_points}
        if pin_points else set()
    )
    x_lo, x_hi, y_lo, y_hi = _page_band(edge_clearance)
    if not outlines and not pts and x_lo is None:
        return (x, y)

    def _free(px: int, py: int) -> bool:
        return _symbol_spot_free(
            px, py, outlines, margin, pts, pin_offset,
            x_lo, x_hi, y_lo, y_hi, edge_clearance,
        )

    if _free(x, y):
        return (x, y)
    found = _spiral_search(x, y, _free, max_tries, step)
    if found is not None:
        return found
    logger.warning(
        "GND place: no free slot near %s within %d tries", (x, y), max_tries,
    )
    return (_snap25(x), _snap25(y + 100))


# ---------------------------------------------------------------------------
#  Phase XXIII P1-3: GND 密度补点（ensure_gnd_symbols）
# ---------------------------------------------------------------------------


def _block_of(p: Point) -> int:
    """返回点所在页面 1/4 分块编号（1..4，2×2 象限）。"""
    x, y = int(p[0]), int(p[1])
    col = 0 if x < _BLOCK_X_MID else 1
    row = 0 if y < _BLOCK_Y_MID else 1
    return row * 2 + col + 1


def _block_center(block: int) -> Point:
    """返回分块中心（snap 25 网格）。"""
    if block == 1:
        cx = (_PAGE_X0 + _BLOCK_X_MID) / 2
        cy = (_PAGE_Y0 + _BLOCK_Y_MID) / 2
    elif block == 2:
        cx = (_PAGE_X0 + _BLOCK_X_MID) / 2
        cy = (_BLOCK_Y_MID + _PAGE_Y1) / 2
    elif block == 3:
        cx = (_BLOCK_X_MID + _PAGE_X1) / 2
        cy = (_PAGE_Y0 + _BLOCK_Y_MID) / 2
    else:
        cx = (_BLOCK_X_MID + _PAGE_X1) / 2
        cy = (_BLOCK_Y_MID + _PAGE_Y1) / 2
    return (_snap25(cx), _snap25(cy))


def ensure_gnd_symbols(
    gnd_pins: Sequence[Point],
    existing_symbol_pins: Sequence[Point] = (),
    outlines: Sequence[Rect] = (),
    pin_points: Sequence[Point] = (),
    margin: int = 50,
    min_pins: int = 3,
    min_dist: int = 1500,
    pin_offset: tuple[int, int] = _GND_PIN_OFFSET,
    edge_clearance: int = 0,
    max_tries: int = 12,
) -> list[dict]:
    """GND 密度补点：页面 1/4 分块，每块补 1 个 GND 符号（Phase XXIII P1-3）。

    对页面做 2×2 分块（象限）。某块若同时满足：
      * 块内非电源 GND 引脚数 ≥ ``min_pins``（默认 3）；
      * 块内最近引脚到最近已有 GND 符号引脚的距离 > ``min_dist``
        （默认 1500；无已有符号时恒满足）；
    则在块中心（snap25）经 ``place_gnd_symbol`` 避让路径补 1 个 GND 符号
    ``GND_SYM_B{block}`` —— 与 ``place_gnd_symbol`` 同样避让元件 outline /
    引脚禁区 / 页边冗余区，符号引脚 = body + ``pin_offset``。

    Args:
        gnd_pins: 页面上 GND 网引脚坐标（非电源引脚；密度判定对象）。
        existing_symbol_pins: 已有 GND 符号引脚坐标（判定"距最近符号"）。
        outlines: 元件 outline 矩形（避让，可选）。
        pin_points: 已占用引脚坐标（禁区，可选）。
        margin: 元件外侧避让冗余区（``overlap.avoid_margin``）。
        min_pins: 触发补点的最小块内引脚数。
        min_dist: 距最近 GND 符号的补点距离阈值。
        pin_offset: GND 引脚相对 body 偏移（默认 golden (50,100)）。
        edge_clearance: 页边冗余区（0 = 不检查页边）。
        max_tries: 螺旋搜索最大环数。

    Returns:
        ``[{"refdes": "GND_SYM_B{block}", "x", "y", "net": "GND",
        "pin_coord": (x, y)}]`` —— 全部 25 网格。
    """
    pins = [(int(p[0]), int(p[1])) for p in gnd_pins]
    if not pins:
        return []
    existing = [(int(p[0]), int(p[1])) for p in existing_symbol_pins]
    obs = [tuple(int(v) for v in o) for o in outlines]
    pts = {(int(p[0]), int(p[1])) for p in pin_points}
    symbols: list[dict] = []
    for block in (1, 2, 3, 4):
        block_pins = [p for p in pins if _block_of(p) == block]
        if len(block_pins) < min_pins:
            continue
        # 块内最近引脚到最近已有符号的距离 > min_dist 才补点。
        nearest = min(
            (_manhattan(p, s) for p in block_pins for s in existing),
            default=None,
        )
        if nearest is not None and nearest <= min_dist:
            continue
        cx, cy = _block_center(block)
        sx, sy = place_gnd_symbol(
            (cx, cy), obs, margin=margin, max_tries=max_tries,
            pin_points=sorted(pts), pin_offset=pin_offset,
            edge_clearance=edge_clearance,
        )
        spx, spy = sx + int(pin_offset[0]), sy + int(pin_offset[1])
        symbols.append({
            "refdes": f"GND_SYM_B{block}",
            "x": sx, "y": sy,
            "net": "GND",
            "pin_coord": (_snap25(spx), _snap25(spy)),
        })
        pts.add((_snap25(spx), _snap25(spy)))
        logger.debug(
            "GND density block %d: %d pins → symbol %s",
            block, len(block_pins), (sx, sy),
        )
    return symbols
