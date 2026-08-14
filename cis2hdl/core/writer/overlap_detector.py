"""OverlapDetector — D2 元件相互重叠检测（Phase XIV）+ 统一碰撞函数（M2）。

Phase XVII M2（用户问题 #10）：新增**统一几何碰撞函数**
``detect_collisions``（rect/point/segment，margin 膨胀），供
元件/线/DOT/GND/标签全类型复用；``OverlapDetector`` 改用统一函数做
元件 vs 元件矩形检测（只报告不移动，保守），输出到 ``AestheticReport``。

Phase XVIII R5（布线避让增强）：``detect_collisions`` 默认 margin
25→50（``overlap.avoid_margin``）；新增 ``self_intersections``（同网
线段自身重叠/交叉 → "线头"清单）与 ``segment_near_pin``（线段进入
引脚半径禁区告警，``overlap.pin_avoid_radius``）。

开关：``overlap.check``（默认 false；CLI ``--aesthetic`` 置 true）。
远期：``--aesthetic-placement`` 才自动移动（本 Phase 仅报告）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

from .aesthetic_report import AestheticReport, Overlap

if TYPE_CHECKING:
    from .csa_writer import CSAWriter

logger = logging.getLogger(__name__)

#: 默认最小重叠面积（1 格² = 25×25），过滤"仅仅贴边"的误报。
_DEFAULT_MIN_AREA: int = 625

#: 几何类型别名：矩形 (x0,y0,x1,y1) / 点 (x,y) / 正交线段 (x1,y1,x2,y2)。
Rect = tuple[int, int, int, int]
Point = tuple[int, int]
Segment = tuple[int, int, int, int]
Geometry = Union[Rect, Point, Segment]


@dataclass
class Collision:
    """一次碰撞：两个几何体 + 重叠信息 + 最小分离向量。"""

    a: Geometry
    b: Geometry
    kind: str = "rect-rect"
    overlap: tuple = ()
    separation: tuple[int, int] = (0, 0)
    """最小分离向量（把 a 沿该方向移动即可与 b 脱离）。"""
    margin: int = 25


def _norm_rect(rect: Rect) -> Rect:
    """归一化矩形（min/max 排序）。"""
    x0, y0, x1, y1 = rect
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _inflate(rect: Rect, margin: int) -> Rect:
    """矩形膨胀 margin 单位。"""
    x0, y0, x1, y1 = _norm_rect(rect)
    return (x0 - margin, y0 - margin, x1 + margin, y1 + margin)


def _rect_intersection(a: Rect, b: Rect) -> Optional[Rect]:
    """两矩形相交矩形；不相交返回 None。"""
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    if x0 < x1 and y0 < y1:
        return (x0, y0, x1, y1)
    return None


def _point_in_rect(p: Point, rect: Rect) -> bool:
    """点在矩形内（含边界）。"""
    x0, y0, x1, y1 = _norm_rect(rect)
    return x0 <= p[0] <= x1 and y0 <= p[1] <= y1


def _segments_intersect(
    a: Segment, b: Segment,
) -> Optional[Point]:
    """两线段相交点；不相交返回 None（含端点相接）。

    支持任意朝向（本项目线段正交，但实现为一般两段求交）。
    """
    (ax1, ay1, ax2, ay2) = a
    (bx1, by1, bx2, by2) = b

    def _orient(px, py, qx, qy, rx, ry) -> float:
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    o1 = _orient(ax1, ay1, ax2, ay2, bx1, by1)
    o2 = _orient(ax1, ay1, ax2, ay2, bx2, by2)
    o3 = _orient(bx1, by1, bx2, by2, ax1, ay1)
    o4 = _orient(bx1, by1, bx2, by2, ax2, ay2)

    def _on_segment(px, py, qx, qy, rx, ry) -> bool:
        return (
            min(px, qx) <= rx <= max(px, qx)
            and min(py, qy) <= ry <= max(py, qy)
        )

    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        # Proper intersection — compute the point.
        denom = (ax1 - ax2) * (by1 - by2) - (ay1 - ay2) * (bx1 - bx2)
        if abs(denom) < 1e-9:
            return None
        px = ((ax1 * ay2 - ay1 * ax2) * (bx1 - bx2)
              - (ax1 - ax2) * (bx1 * by2 - by1 * bx2)) / denom
        py = ((ax1 * ay2 - ay1 * ax2) * (by1 - by2)
              - (ay1 - ay2) * (bx1 * by2 - by1 * bx2)) / denom
        return (int(round(px)), int(round(py)))
    # Collinear / endpoint touching cases.
    if o1 == 0 and _on_segment(ax1, ay1, ax2, ay2, bx1, by1):
        return (bx1, by1)
    if o2 == 0 and _on_segment(ax1, ay1, ax2, ay2, bx2, by2):
        return (bx2, by2)
    if o3 == 0 and _on_segment(bx1, by1, bx2, by2, ax1, ay1):
        return (ax1, ay1)
    if o4 == 0 and _on_segment(bx1, by1, bx2, by2, ax2, ay2):
        return (ax2, ay2)
    return None


def _segment_intersects_rect(
    seg: Segment, rect: Rect, margin: int,
) -> Optional[Point]:
    """线段与膨胀矩形是否相交（含线段任一端点在矩形内）。"""
    r = _inflate(rect, margin)
    if _point_in_rect((seg[0], seg[1]), r) or _point_in_rect((seg[2], seg[3]), r):
        return (seg[0], seg[1])
    # 四条边求交。
    x0, y0, x1, y1 = r
    edges = (
        (x0, y0, x1, y0),  # bottom
        (x1, y0, x1, y1),  # right
        (x1, y1, x0, y1),  # top
        (x0, y1, x0, y0),  # left
    )
    for edge in edges:
        pt = _segments_intersect(seg, edge)
        if pt is not None:
            return pt
    return None


def _rect_separation(a: Rect, b: Rect, margin: int) -> tuple[int, int]:
    """rect a 相对 rect b 的最小分离向量（完全推出，避免振荡）。

    取四个候选平移（右/左/上/下）中幅度最小者 —— 平移量 = 让膨胀后的
    a 完全越过膨胀后的 b 的对应边（不再仅推重叠量，防止相邻帧方向反转）。

    Args:
        a: 可动矩形（原始坐标）。
        b: 固定矩形（原始坐标）。
        margin: 膨胀边距。

    Returns:
        ``(dx, dy)`` —— 把 a 沿该向量平移后膨胀矩形不再相交。
    """
    ra = _inflate(a, margin)
    rb = _inflate(b, margin)
    ox = min(ra[2], rb[2]) - max(ra[0], rb[0])
    oy = min(ra[3], rb[3]) - max(ra[1], rb[1])
    if ox <= 0 or oy <= 0:
        return (0, 0)
    candidates = (
        (rb[2] - ra[0], 0),   # push right (a 左缘越过 b 右缘)
        (rb[0] - ra[2], 0),   # push left
        (0, rb[3] - ra[1]),   # push up
        (0, rb[1] - ra[3]),   # push down
    )
    best = min(candidates, key=lambda c: abs(c[0]) + abs(c[1]))
    return (int(round(best[0])), int(round(best[1])))


def _point_rect_separation(p: Point, rect: Rect, margin: int) -> tuple[int, int]:
    """点相对矩形的最小分离向量（推出膨胀矩形）。"""
    r = _inflate(rect, margin)
    x0, y0, x1, y1 = r
    if not _point_in_rect(p, r):
        return (0, 0)
    dx_right = x1 - p[0] + 1
    dx_left = p[0] - x0 + 1
    dy_top = y1 - p[1] + 1
    dy_bottom = p[1] - y0 + 1
    m = min(dx_right, dx_left, dy_top, dy_bottom)
    if m == dx_right:
        return (dx_right, 0)
    if m == dx_left:
        return (-dx_left, 0)
    if m == dy_top:
        return (0, dy_top)
    return (0, -dy_bottom)


def detect_collisions(
    geoms_a: list[Geometry],
    geoms_b: list[Geometry],
    margin: int = 50,
) -> list[Collision]:
    """统一碰撞检测：rect/point/segment 两两求交（Phase XVII M2）。

    用户问题 #10（统一函数反复调用）：元件/线/DOT/GND/标签全部走本函数。
    矩形与矩形相交、点在矩形内、线段穿矩形、线段相交均覆盖；返回碰撞对
    + 最小分离向量（供 M3 腾挪器移动可动件）。

    Phase XVIII R5（Q3）：默认 margin 25→50（``overlap.avoid_margin``）；
    调用方显式传 ``edge_clearance`` / ``pin_avoid_radius`` 做更保守检测。

    Args:
        geoms_a: 几何体列表 A（可动件视角 —— separation 指把 a 推开）。
        geoms_b: 几何体列表 B（固定件/障碍）。
        margin: 膨胀边距（默认 = 50，R5/Q3 统一避让 margin）。

    Returns:
        Collision 列表（a 来自 geoms_a，b 来自 geoms_b）。
    """
    collisions: list[Collision] = []
    for a in geoms_a:
        for b in geoms_b:
            kind = _classify_pair(a, b)
            if kind == "rect-rect":
                ov = _rect_intersection(_inflate(a, margin), _inflate(b, margin))
                if ov is None:
                    continue
                sep = _rect_separation(a, b, margin)
                collisions.append(Collision(a=a, b=b, kind=kind, overlap=ov,
                                            separation=sep, margin=margin))
            elif kind == "point-rect":
                # 确定哪一个是点（调用方通常把可动点放 a、固定矩形放 b）。
                if _geom_kind(a) == "point":
                    pt, rect = a, b
                else:
                    pt, rect = b, a
                if not _point_in_rect(pt, _inflate(rect, margin)):
                    continue
                sep = _point_rect_separation(pt, rect, margin)
                collisions.append(Collision(a=a, b=b, kind=kind, overlap=pt,
                                            separation=sep, margin=margin))
            elif kind == "segment-rect":
                pt = _segment_intersects_rect(a, b, margin)
                if pt is None:
                    continue
                collisions.append(Collision(a=a, b=b, kind=kind, overlap=pt,
                                            separation=(0, 0), margin=margin))
            elif kind == "segment-segment":
                pt = _segments_intersect(a, b)
                if pt is None:
                    continue
                collisions.append(Collision(a=a, b=b, kind=kind, overlap=pt,
                                            separation=(0, 0), margin=margin))
            elif kind == "point-point":
                if _dist(a, b) <= margin:
                    collisions.append(Collision(a=a, b=b, kind=kind, overlap=a,
                                                separation=(0, 0), margin=margin))
    return collisions


def _classify_pair(a: Geometry, b: Geometry) -> str:
    """几何对类型（点/线段/矩形 → 组合）。"""
    a_kind = _geom_kind(a)
    b_kind = _geom_kind(b)
    if a_kind == "point" and b_kind == "point":
        return "point-point"
    if a_kind == "point" and b_kind == "rect":
        return "point-rect"
    if a_kind == "rect" and b_kind == "point":
        return "point-rect"  # 调用方需保证 a 为点；这里返回通用名
    if a_kind == "segment" and b_kind == "rect":
        return "segment-rect"
    if a_kind == "rect" and b_kind == "segment":
        return "segment-rect"
    if a_kind == "segment" and b_kind == "segment":
        return "segment-segment"
    return "rect-rect"


def _geom_kind(g: Geometry) -> str:
    """几何体类型：point（2 元组）/ segment（4 元组且非矩形）/ rect。"""
    if len(g) == 2:
        return "point"
    if len(g) == 4:
        x0, y0, x1, y1 = g
        if (x0 == x1 and y0 != y1) or (y0 == y1 and x0 != x1):
            return "segment"
        return "rect"
    return "rect"


def _dist(a: Point, b: Point) -> float:
    """欧氏距离。"""
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _point_on_segment(p: Point, seg: Segment) -> bool:
    """点是否在线段上（含端点，轴对齐与一般线段）。"""
    x, y = p
    x1, y1, x2, y2 = seg
    if x1 == x2:  # vertical
        return x == x1 and min(y1, y2) <= y <= max(y1, y2)
    if y1 == y2:  # horizontal
        return y == y1 and min(x1, x2) <= x <= max(x1, x2)
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > 1e-6:
        return False
    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def _point_segment_dist(p: Point, seg: Segment) -> float:
    """点到线段的最短距离（一般线段，含端点投影）。"""
    x, y = p
    x1, y1, x2, y2 = seg
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return _dist(p, (x1, y1))
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj = (x1 + t * dx, y1 + t * dy)
    return _dist(p, proj)


def _segments_overlap(a: Segment, b: Segment) -> bool:
    """两条共线线段是否重叠超过一个点（纯端点相接不算）。"""
    (ax1, ay1, ax2, ay2) = a
    (bx1, by1, bx2, by2) = b
    if ax1 == ax2 and bx1 == bx2 and ax1 == bx1:
        # 同 X 垂直线段。
        lo = max(min(ay1, ay2), min(by1, by2))
        hi = min(max(ay1, ay2), max(by1, by2))
        return hi > lo
    if ay1 == ay2 and by1 == by2 and ay1 == by1:
        # 同 Y 水平线段。
        lo = max(min(ax1, ax2), min(bx1, bx2))
        hi = min(max(ax1, ax2), max(bx1, bx2))
        return hi > lo
    return False


def self_intersections(
    wires: Iterable[Segment],
) -> list[tuple[Segment, Segment, Point]]:
    """同网线段自身重叠/交叉检测 → "线头"清单（Phase XVIII R5）。

    线头 = 同一网内两线段**非正常连接**的重叠/交叉：
    * 共线重叠（重叠区间长度 > 0 —— 电线折回压在自己身上）；
    * 一般 X 交叉（交点位于两段内部，两段互相穿过）。

    正常 T 型连接（一段端点落在另一段内部，stub 接到 trunk）是合法
    接点（会生成 DOT），**不**计入线头 —— 因此 ``self_intersections``
    为空是布线输出"零自身重叠"的验收断言。

    Args:
        wires: 同一网内线段列表（(x1,y1,x2,y2) 四元组）。

    Returns:
        ``[(seg_a, seg_b, 交点)]``；空 = 无自身重叠。
    """
    segs = [tuple(int(v) for v in s) for s in wires]
    out: list[tuple[Segment, Segment, Point]] = []
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if _segments_overlap(a, b):
                # 取重叠区间中点作代表交点。
                pt = _overlap_midpoint(a, b)
                out.append((a, b, pt))
                continue
            hit = _segments_intersect(a, b)
            if hit is None:
                continue
            # 排除纯端点相接（L 形）与 T 型（一段端点落在另一段内部）——
            # 这些是合法连接点。
            a_end = (a[0], a[1]) in ((b[0], b[1]), (b[2], b[3]))
            b_end = (b[0], b[1]) in ((a[0], a[1]), (a[2], a[3]))
            a_interior = _point_on_segment(hit, a) and not (
                hit == (a[0], a[1]) or hit == (a[2], a[3])
            )
            b_interior = _point_on_segment(hit, b) and not (
                hit == (b[0], b[1]) or hit == (b[2], b[3])
            )
            if a_interior and b_interior:
                # X 交叉（两段互穿）→ 线头。
                out.append((a, b, hit))
    return out


def _overlap_midpoint(a: Segment, b: Segment) -> Point:
    """共线重叠区间的中点（用于报告）。"""
    (ax1, ay1, ax2, ay2) = a
    if ax1 == ax2:  # vertical
        lo = max(min(ay1, ay2), min(b[1], b[3]))
        hi = min(max(ay1, ay2), max(b[1], b[3]))
        return (ax1, (lo + hi) // 2)
    lo = max(min(ax1, ax2), min(b[0], b[2]))
    hi = min(max(ax1, ax2), max(b[0], b[2]))
    return ((lo + hi) // 2, ay1)


def segment_near_pin(
    seg: Segment, pins: Iterable[Point], radius: int,
) -> Optional[Point]:
    """线段是否进入引脚半径禁区（防误连接，Phase XVIII R5）。

    返回距线段最近且距离 < ``radius`` 的引脚点；空 = 线段与所有引脚
    保持 ≥ ``radius`` 距离。用于：trunk 候选检查（trunk 不得在引脚
    ``pin_avoid_radius`` 内穿过，防 stub 端点落 trunk 造成短路）与
    布线后验收断言（无线段进入引脚半径）。

    Args:
        seg: 线段 (x1,y1,x2,y2)。
        pins: 引脚坐标集合。
        radius: 避让半径（``overlap.pin_avoid_radius``，默认 50）。

    Returns:
        最近引脚点（(x, y)）或 None。
    """
    if radius <= 0:
        return None
    seg_t = tuple(int(v) for v in seg)
    best: Optional[Point] = None
    best_d = float("inf")
    for p in pins:
        pt = (int(p[0]), int(p[1]))
        d = _point_segment_dist(pt, seg_t)
        if d < radius and d < best_d:
            best_d = d
            best = pt
    return best


class OverlapDetector:
    """两两相交检测器（只报告不移动，M2 统一函数）。"""

    def __init__(self, min_area: int = _DEFAULT_MIN_AREA) -> None:
        """Initialize with a minimum overlap area filter.

        Args:
            min_area: 重叠面积低于该值的贴边对不报告。
        """
        self.min_area = int(min_area)

    def detect(
        self,
        page,
        body_coords: dict[str, tuple[int, int]],
        outlines_by_refdes: Optional[dict[str, tuple[int, int, int, int]]] = None,
    ) -> list[Overlap]:
        """检测一个页面的元件重叠。

        Args:
            page: PageConnectivity（提供实例与页面号）。
            body_coords: refdes → body (x, y)。
            outlines_by_refdes: refdes → 绝对轮廓矩形；缺省时用页面轮廓。

        Returns:
            Overlap 列表（按面积降序）。
        """
        outlines: dict[str, tuple[int, int, int, int]] = {}
        if outlines_by_refdes:
            outlines.update(outlines_by_refdes)
        else:
            for irec in page.instances:
                x, y = body_coords.get(irec.refdes, (0, 0))
                outline = self._outline_for(irec)
                if outline is None:
                    continue
                outlines[irec.refdes] = (
                    x + outline[0], y + outline[1],
                    x + outline[2], y + outline[3],
                )

        refdes_list = list(outlines.keys())
        rects = [outlines[r] for r in refdes_list]
        page_num = int(getattr(page, "page_num", 0) or 0)
        overlaps: list[Overlap] = []
        # M2: 统一函数 —— 逐对调用 detect_collisions（margin=0 报告原始
        # 重叠；逐对调用避免相同矩形在索引映射中塌缩）。
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                cols = detect_collisions([rects[i]], [rects[j]], margin=0)
                if not cols:
                    continue
                col = cols[0]
                ra, rb = refdes_list[i], refdes_list[j]
                ba, bb = outlines[ra], outlines[rb]
                ov = col.overlap
                area = (ov[2] - ov[0]) * (ov[3] - ov[1])
                if area < self.min_area:
                    continue
                kind = self._classify(page, ra, rb)
                overlaps.append(Overlap(
                    page=page_num,
                    refdes_a=ra, refdes_b=rb,
                    bbox_a=ba, bbox_b=bb,
                    overlap_rect=ov, area=area, kind=kind,
                ))
        overlaps.sort(key=lambda o: o.area, reverse=True)
        if overlaps:
            logger.info(
                "OverlapDetector: page %d → %d overlap(s)", page_num, len(overlaps),
            )
        return overlaps

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _outline_for(irec) -> Optional[tuple[int, int, int, int]]:
        """Instance 的相对轮廓（与 csa_writer._collect_body_outlines 同源）。"""
        from ..parser.symbol_css import SymbolCssPinParser  # noqa: F401

        body_name = (getattr(irec, "cell_name", "") or "").lower()
        if getattr(irec, "is_power_symbol", False):
            if body_name == "vcc_circle":
                return (-75, 75, 75, -75)
            return (-50, 0, 50, -50)
        props = getattr(irec, "properties", {}) or {}
        outline_str = props.get("CDS_LMAN_SYM_OUTLINE", "")
        if not outline_str:
            n_pins = len(getattr(irec, "pins", []) or [])
            if n_pins > 1:
                # 占位轮廓：与 _placeholder_outline 同规则（小芯片两列 ±150）
                half = (n_pins + 1) // 2
                bottom = min(150 - (half - 1) * 100, -150)
                outline_str = f"-150,150,150,{bottom}"
        if not outline_str:
            outline_str = "-50,0,50,-25"
        try:
            x1, y1, x2, y2 = (float(v) for v in outline_str.split(","))
        except ValueError:
            return None
        return (
            int(min(x1, x2)), int(min(y1, y2)),
            int(max(x1, x2)), int(max(y1, y2)),
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
    def _classify(page, refdes_a: str, refdes_b: str) -> str:
        """重叠分类：placeholder（占位）/ grid（兜底网格）/ user（原始布局）。"""
        insts = {i.refdes: i for i in page.instances}
        kinds = []
        for ref in (refdes_a, refdes_b):
            irec = insts.get(ref)
            if irec is None:
                kinds.append("user")
                continue
            props = getattr(irec, "properties", {}) or {}
            n_pins = len(getattr(irec, "pins", []) or [])
            has_outline = bool(props.get("CDS_LMAN_SYM_OUTLINE", ""))
            if n_pins > 1 and not has_outline:
                kinds.append("placeholder")
            elif not (getattr(irec, "loc_x", 0) or getattr(irec, "loc_y", 0)):
                kinds.append("grid")
            else:
                kinds.append("user")
        if "placeholder" in kinds:
            return "placeholder"
        if "grid" in kinds:
            return "grid"
        return "user"

    def detect_and_report(
        self,
        page,
        body_coords: dict[str, tuple[int, int]],
        report: AestheticReport,
        outlines_by_refdes: Optional[dict] = None,
    ) -> int:
        """检测并写入 AestheticReport；返回重叠数。"""
        overlaps = self.detect(page, body_coords, outlines_by_refdes)
        for ov in overlaps:
            report.add_overlap(ov)
        return len(overlaps)
