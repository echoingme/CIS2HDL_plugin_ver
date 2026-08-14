"""WireSimplifier — M4 走线化简后处理（Phase XVII，SKiDL cleanup_wires 移植）。

用户 17 条共性问题 #1/#2/#3/#9/#12（电线爆炸/连接点过多/凸出折回）：
把 SKiDL ``cleanup_wires`` 的算法移植为独立后处理模块（MIT 许可），
作为 wire_layout 的后处理阶段，只合并**同网**段、端点引脚坐标不动
（满足 DEHDL 几何重合硬约束）。

四个核心函数（对应 SKiDL route.py 核实算法）：
* ``merge_segments`` —— 同 Y 水平段 / 同 X 垂直段排序后贪心合并重叠区间
  （段数削减主力）；
* ``trim_stubs``    —— 从引脚段做连通图搜索，删除连不到任何引脚的悬空段
  （用户"凸出又折回"修复）；
* ``remove_jogs``   —— 3 段阶梯/礼帽 jog 替换为 2 段直角（obstructed 避让
  检查，防撞元件 bbox 或其他网平行段）；
* ``add_junctions`` —— 仅 T/X 真交点生成 DOT（排除直角端点相接；
  **先 merge 后找**，与 SKiDL 顺序一致）。

另提供 ``long_wire_report``（超长电线阈值检测，用户 D5 max_wire_len）。

配置开关：``wire_simplify.enabled=false``（默认关，可回退）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

#: 线段 = (x1, y1, x2, y2)；点 = (x, y)。
Segment = tuple[int, int, int, int]
Point = tuple[int, int]


@dataclass
class SimplifyResult:
    """M4 化简结果。"""

    wires: list[Segment] = field(default_factory=list)
    """化简后的线段列表。"""
    junctions: list[Point] = field(default_factory=list)
    """T/X 真交点（供 DOT 输出）。"""
    merged_count: int = 0
    trimmed_count: int = 0
    jog_count: int = 0
    long_segments: list[Segment] = field(default_factory=list)
    """超过 max_wire_len 的线段（超长断线 → 网络名远程连接候选）。"""
    net_labels: list[tuple[Point, str]] = field(default_factory=list)
    """R8：超长段断开后的断口标签坐标 ``[(端点, net_display)]``。"""


def _norm(seg: Segment) -> Segment:
    """规范化线段方向（x1<=x2；垂直段 y1<=y2）。"""
    x1, y1, x2, y2 = seg
    if x1 == x2:
        if y1 > y2:
            return (x1, y2, x2, y1)
        return seg
    if x1 > x2:
        return (x2, y2, x1, y1)
    return seg


def _is_h(seg: Segment) -> bool:
    return seg[1] == seg[3]


def _is_v(seg: Segment) -> bool:
    return seg[0] == seg[2]


def merge_segments(wires: Iterable[Segment]) -> list[Segment]:
    """共线重叠合并：同 Y 水平段 / 同 X 垂直段排序后贪心合并。

    SKiDL ``merge_segments``（route.py L2516）移植：按 Y（水平）分组、
    按 p1.x 排序，贪心合并重叠/相邻区间。垂直段同理按 X 分组。

    Args:
        wires: 线段列表（正交）。

    Returns:
        合并后的线段列表（无重叠/相邻共线段）。
    """
    segs = [_norm(s) for s in wires if _is_h(s) or _is_v(s)]
    merged: list[Segment] = []

    # 水平段按 y 分组。
    h_by_y: dict[int, list[Segment]] = {}
    v_by_x: dict[int, list[Segment]] = {}
    for s in segs:
        if _is_h(s):
            h_by_y.setdefault(s[1], []).append(s)
        else:
            v_by_x.setdefault(s[0], []).append(s)

    for y, group in h_by_y.items():
        group.sort(key=lambda s: (s[0], s[2]))
        cur: Optional[Segment] = None
        for s in group:
            if cur is None:
                cur = s
                continue
            # 贪心合并：当前段终点 >= 下段起点（重叠或相邻）。
            if cur[2] >= s[0]:
                cur = (cur[0], y, max(cur[2], s[2]), y)
            else:
                merged.append(cur)
                cur = s
        if cur is not None:
            merged.append(cur)

    for x, group in v_by_x.items():
        group.sort(key=lambda s: (s[1], s[3]))
        cur: Optional[Segment] = None
        for s in group:
            if cur is None:
                cur = s
                continue
            if cur[3] >= s[1]:
                cur = (x, cur[1], x, max(cur[3], s[3]))
            else:
                merged.append(cur)
                cur = s
        if cur is not None:
            merged.append(cur)

    return merged


def _segment_endpoints(seg: Segment) -> tuple[Point, Point]:
    return ((seg[0], seg[1]), (seg[2], seg[3]))


def _point_on_segment(p: Point, seg: Segment) -> bool:
    """点在线段上（含端点）。"""
    x, y = p
    x1, y1, x2, y2 = seg
    if x1 == x2:  # vertical
        return x == x1 and min(y1, y2) <= y <= max(y1, y2)
    if y1 == y2:  # horizontal
        return y == y1 and min(x1, x2) <= x <= max(x1, x2)
    # 一般线段：叉积 + 包围盒。
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > 1e-6:
        return False
    return (min(x1, x2) <= x <= max(x1, x2)
            and min(y1, y2) <= y <= max(y1, y2))


def trim_stubs(wires: Iterable[Segment], pins: Iterable[Point]) -> list[Segment]:
    """删除连不到任何引脚的悬空段（SKiDL ``trim_stubs`` L2621 移植）。

    建邻接图：两段共享端点（或 T 型端点落在线段内部）即相邻；从
    "锚定段"（任一端点/内部点命中引脚坐标）做 BFS，保留可达段。

    Args:
        wires: 线段列表。
        pins: 引脚坐标（绝对）。

    Returns:
        保留的线段列表（悬空 stub 已删除）。
    """
    segs = list(wires)
    if not segs:
        return []
    pin_set = {(int(p[0]), int(p[1])) for p in pins}

    def _anchored(seg: Segment) -> bool:
        p1, p2 = _segment_endpoints(seg)
        if p1 in pin_set or p2 in pin_set:
            return True
        # T 型：引脚落在线段内部。
        for pin in pin_set:
            if _point_on_segment(pin, seg):
                return True
        return False

    def _share_point(a: Segment, b: Segment) -> bool:
        """两段共享连接点（端点相接或 T 型相交）。"""
        a1, a2 = _segment_endpoints(a)
        b1, b2 = _segment_endpoints(b)
        # 端点-端点
        if a1 in (b1, b2) or a2 in (b1, b2):
            return True
        # 端点落在线段内部（T）
        if _point_on_segment(a1, b) or _point_on_segment(a2, b):
            return True
        if _point_on_segment(b1, a) or _point_on_segment(b2, a):
            return True
        return False

    adj: dict[int, list[int]] = {i: [] for i in range(len(segs))}
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if _share_point(segs[i], segs[j]):
                adj[i].append(j)
                adj[j].append(i)

    # BFS 从锚定段出发。
    queue = [i for i, s in enumerate(segs) if _anchored(s)]
    seen: set[int] = set(queue)
    while queue:
        cur = queue.pop()
        for nxt in adj[cur]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

    kept = [segs[i] for i in sorted(seen)]
    trimmed = len(segs) - len(kept)
    if trimmed:
        logger.debug("wire_simplifier.trim_stubs: removed %d dangling segment(s)", trimmed)
    return kept


def remove_jogs(
    wires: Iterable[Segment],
    obstacles: Iterable[tuple[int, int, int, int]] = (),
) -> list[Segment]:
    """3 段阶梯/礼帽 jog 替换为 2 段直角（SKiDL ``remove_jogs`` L2816 移植）。

    检测模式（H-V-H 或 V-H-V）：
    * H-V-H：两水平段同向、y 不同，中间垂直段连接；可替换为一条水平 +
      一条垂直（2 段），前提是新段不撞障碍（元件 bbox / 其他平行段）。
    * V-H-V：同理（x 不同）。

    Args:
        wires: 线段列表。
        obstacles: 障碍矩形（元件 outline），新段不得与之相交。

    Returns:
        化简后的线段列表（jog 已替换为直角 2 段）。
    """
    segs = [_norm(s) for s in wires if _is_h(s) or _is_v(s)]
    obs = [tuple(int(v) for v in o) for o in obstacles]
    changed = True
    while changed:
        changed = False
        for i in range(len(segs) - 2):
            a, b, c = segs[i], segs[i + 1], segs[i + 2]
            repl = _try_replace_jog(a, b, c, obs)
            if repl is None:
                continue
            # 替换：i..i+2 → repl（2 段）。
            segs = segs[:i] + list(repl) + segs[i + 3:]
            changed = True
            break
    return segs


def _try_replace_jog(
    a: Segment, b: Segment, c: Segment, obstacles: list,
) -> Optional[tuple[Segment, Segment]]:
    """尝试把 (a,b,c) 3 段 jog 替换为 2 段直角。

    仅处理连续路径 a→b→c（a∥c、b⊥a，b 连接 a 的某一端点与 c 的某一
    端点）：把"外端点 a_far → 外端点 c_far"用一条 L（2 段）替代，
    保留两端点拓扑（SKiDL ``remove_jogs`` 思想）。两条候选 L 均须
    不撞障碍。

    Args:
        a/b/c: 相邻 3 段（已规范化）。
        obstacles: 元件 outline 列表。

    Returns:
        ``(seg1, seg2)`` 2 段直角；不适用/被障碍挡住返回 None。
    """
    # 要求 a∥c 且 b⊥a。
    if not ((_is_h(a) and _is_v(b) and _is_h(c)) or
            (_is_v(a) and _is_h(b) and _is_v(c))):
        return None

    a_pts = [(a[0], a[1]), (a[2], a[3])]
    b_pts = [(b[0], b[1]), (b[2], b[3])]
    c_pts = [(c[0], c[1]), (c[2], c[3])]

    # b 的端点必须分别落在 a 与 c 上。
    a_inner = next((p for p in a_pts if p in b_pts), None)
    c_inner = next((p for p in c_pts if p in b_pts), None)
    if a_inner is None or c_inner is None:
        return None
    a_far = a_pts[1] if a_pts[0] == a_inner else a_pts[0]
    c_far = c_pts[1] if c_pts[0] == c_inner else c_pts[0]

    # 候选 L：a_far → c_far（两条 Manhattan 路径）。
    fx, fy = a_far
    tx, ty = c_far
    candidates = (
        ((fx, fy, tx, fy), (tx, fy, tx, ty)),   # 水平先
        ((fx, fy, fx, ty), (fx, ty, tx, ty)),   # 垂直先
    )
    for seg1, seg2 in candidates:
        if (_seg_intersects_obstacles(seg1, obstacles)
                or _seg_intersects_obstacles(seg2, obstacles)):
            continue
        return (seg1, seg2)
    return None


def _seg_intersects_obstacles(seg: Segment, obstacles: list) -> bool:
    """线段是否与任一障碍矩形相交（含贴边）。"""
    x1, y1, x2, y2 = seg
    for (ox0, oy0, ox1, oy1) in obstacles:
        # 线段与矩形相交：任一端点在矩形内 OR 矩形边与线段相交。
        if (ox0 <= x1 <= ox1 and oy0 <= y1 <= oy1) or \
           (ox0 <= x2 <= ox1 and oy0 <= y2 <= oy1):
            return True
        # 轴对齐简化：水平/垂直线段与矩形区间重叠即相交。
        if x1 == x2 and ox0 <= x1 <= ox1:
            if min(y1, y2) <= oy1 and max(y1, y2) >= oy0:
                return True
        if y1 == y2 and oy0 <= y1 <= oy1:
            if min(x1, x2) <= ox1 and max(x1, x2) >= ox0:
                return True
    return False


def add_junctions(wires: Iterable[Segment], dot_merge: int = 50) -> list[Point]:
    """仅 T/X 真交点生成 DOT（排除直角端点相接；先 merge 后找）。

    SKiDL ``add_junctions``（route.py L3054）移植：水平/垂直段分离，
    找 H 内部与 V 内部的交点；交点必须至少在一段的**内部**（T：在一段
    内部、另一端点是端点；X：两段都在内部）。纯直角端点相接（两段各取
    端点）不产生 DOT。``dot_merge`` 为就近合并阈值（重复交点吸到一起）。

    Args:
        wires: 线段列表（调用方应先 merge_segments）。
        dot_merge: 邻近 DOT 合并距离阈值。

    Returns:
        DOT 坐标列表（去重、网格对齐）。
    """
    segs = [_norm(s) for s in wires if _is_h(s) or _is_v(s)]
    h_segs = [s for s in segs if _is_h(s)]
    v_segs = [s for s in segs if _is_v(s)]
    junctions: list[Point] = []
    seen: set[Point] = set()
    for hs in h_segs:
        for vs in v_segs:
            x, y = vs[0], hs[1]
            # x 在 hs 内部（含端点）；y 在 vs 内部（含端点）。
            x_in_h = hs[0] <= x <= hs[2]
            y_in_v = vs[1] <= y <= vs[3]
            if not (x_in_h and y_in_v):
                continue
            # 直角端点相接：交点同时是 hs 的端点且是 vs 的端点 → 排除。
            h_endpoint = (x == hs[0] or x == hs[2])
            v_endpoint = (y == vs[1] or y == vs[3])
            if h_endpoint and v_endpoint:
                continue
            pt = (int(round(x / 25.0) * 25), int(round(y / 25.0) * 25))
            if pt in seen:
                continue
            seen.add(pt)
            junctions.append(pt)

    # 就近合并：距离 <= dot_merge 的交点保留第一个。
    merged: list[Point] = []
    for pt in sorted(junctions):
        if any(abs(pt[0] - m[0]) + abs(pt[1] - m[1]) <= dot_merge
               for m in merged):
            continue
        merged.append(pt)
    return merged


def parallel_short_wires(
    pins: Iterable[Point],
    max_dist: int = 500,
    stub_lead: int = 100,
    outlines: Iterable[tuple[int, int, int, int]] = (),
) -> list[Segment]:
    """同类同信号相近引脚先短接再引出（Phase XVIII R8，复用 R6 算法）。

    把间距 ≤ ``max_dist`` 的引脚聚成簇（``gnd_cluster_planner``
    ``route_cluster_parallel`` 贪心最近邻），每簇生成 hub 短接 WIRE 段
    （引脚 → hub）。csa_writer 在路由前对"并联组"（如 C270/283/260
    同网并联电容）调用本函数，短接段并入网后再统一引出。

    Args:
        pins: 同信号引脚坐标列表。
        max_dist: 并联判定距离阈值（``parallel_short_dist``，默认 500）。
        stub_lead: 引脚外引距离。
        outlines: 元件 outline（避让，可选）。

    Returns:
        短接 WIRE 段列表（端点 = 引脚坐标不变，全 25 网格）。
    """
    from .gnd_cluster_planner import hub_short_wires, route_cluster_parallel

    pairs = [("", (int(p[0]), int(p[1]))) for p in pins]
    hubs = route_cluster_parallel(pairs, max_dist=max_dist)
    out: list[Segment] = []
    for h in hubs:
        out.extend(hub_short_wires(h, outlines, stub_lead))
    return out


def plan_parallel_short(
    pins: Iterable[Point],
    max_dist: int = 500,
    stub_lead: int = 100,
    outlines: Iterable[tuple[int, int, int, int]] = (),
) -> tuple[list[tuple[Point, list[Point]]], list[Segment]]:
    """同信号相近引脚簇规划（Phase XXII D4，Q4 仅接线 parallel_short）。

    对非 GND 同信号引脚簇（间距 ≤ ``max_dist``）生成 hub 短接计划：
    csa_writer 路由前调用本函数，把簇内引脚替换为合成 hub 路由点
    （``PARALLEL_HUB_*``，只进 route_map 不进 net_pin_map/LASTPIN），
    路由后把短接段并入对应网 —— 每簇 WIRE 段数 = 簇内引脚数（hub
    短接）+ 1（引出）。

    Args:
        pins: 同信号引脚坐标列表。
        max_dist: 并联判定距离阈值（``parallel_short_dist``，默认 500）。
        stub_lead: 引脚外引距离。
        outlines: 元件 outline（避让，可选）。

    Returns:
        ``(clusters, short_wires)`` —— ``clusters`` 为 ``[(hub_coord,
        [成员引脚坐标...]), ...]``（每簇 ≥2 引脚）；``short_wires`` 为
        簇内短接 WIRE 段（端点 = 引脚坐标不变，全 25 网格）。
    """
    from .gnd_cluster_planner import hub_short_wires, route_cluster_parallel

    coords: list[Point] = [(int(p[0]), int(p[1])) for p in pins]
    if len(coords) < 2:
        return [], []
    hubs = route_cluster_parallel([("", c) for c in coords], max_dist=max_dist)
    clusters: list[tuple[Point, list[Point]]] = []
    short_wires: list[Segment] = []
    for h in hubs:
        if h.pin_count < 2:
            continue
        clusters.append((h.hub, list(h.pin_coords)))
        short_wires.extend(hub_short_wires(h, outlines, stub_lead))
    return clusters, short_wires


def long_wire_report(
    wires: Iterable[Segment], max_len: int,
) -> list[Segment]:
    """超长电线检测（用户 D5 max_wire_len 阈值）。

    Args:
        wires: 线段列表。
        max_len: 长度阈值（默认 5000）。

    Returns:
        长度 > max_len 的线段（建议断开改用网络名远程连接）。
    """
    limit = int(max_len or 5000)
    out: list[Segment] = []
    for s in wires:
        x1, y1, x2, y2 = s
        length = abs(x2 - x1) + abs(y2 - y1)
        if length > limit:
            out.append(s)
    return out


def split_long_wires(
    wires: Iterable[Segment],
    max_len: int = 5000,
    segment_len: int = 2500,
) -> tuple[list[Segment], list[tuple[Point, Point]]]:
    """超长电线分段（Phase XVIII R8：``wire_simplify.break_long``）。

    把长度 > ``max_len`` 的线段沿中点拆成两段（保留端点），并返回
    **断口两端坐标**——调用方在这些位置放网络名标签，表达"远程连接"
    语义（用户诉求：电线长度设限，超长断开改网络名）。

    Args:
        wires: 线段列表。
        max_len: 超长阈值（``max_wire_len``，默认 5000）。
        segment_len: 拆分目标段长（默认 2500；仅用于迭代分段）。

    Returns:
        ``(segments, breaks)``：拆分后的线段列表 + 断口
        ``((x1,y1),(x2,y2))`` 列表（每个断口两端的标签坐标）。
    """
    limit = int(max_len or 5000)
    target = int(segment_len or 2500) or limit
    out: list[Segment] = []
    breaks: list[tuple[Point, Point]] = []

    for s in wires:
        x1, y1, x2, y2 = s
        length = abs(x2 - x1) + abs(y2 - y1)
        if length <= limit:
            out.append(s)
            continue
        # 沿中点拆分（水平/垂直段：先拆长轴）。
        if abs(x2 - x1) >= abs(y2 - y1):
            pieces = _split_axis(x1, x2, y1, target, horizontal=True)
            for (ax, ay, bx, by) in pieces:
                out.append((ax, ay, bx, by))
                breaks.append(((ax, ay), (bx, by)))
        else:
            pieces = _split_axis(y1, y2, x1, target, horizontal=False)
            for (ax, ay, bx, by) in pieces:
                out.append((ax, ay, bx, by))
                breaks.append(((ax, ay), (bx, by)))
    return out, breaks


def _split_axis(
    a1: int, a2: int, b: int, target: int, horizontal: bool,
) -> list[Segment]:
    """沿长轴把线段切成 ≤ target 的子段（含原始端点）。

    Args:
        a1/a2: 长轴端点（x 或 y）。
        b: 短轴固定坐标。
        target: 目标子段长度。
        horizontal: True 时长轴是 x（段 ``(ax, b, bx, b)``）。

    Returns:
        子段列表（保持原始方向）。
    """
    lo, hi = min(a1, a2), max(a1, a2)
    if hi - lo <= target:
        return [((a1, b), (a2, b)) if horizontal else ((b, a1), (b, a2))]
    segs: list[Segment] = []
    cur = lo
    while cur < hi:
        nxt = min(cur + target, hi)
        if horizontal:
            segs.append((cur, b, nxt, b))
        else:
            segs.append((b, cur, b, nxt))
        cur = nxt
    # 保持原始方向（a1→a2 正向）：逆向时反转每段端点并倒序。
    if a1 > a2:
        segs = [(c, d, a, b2) for (a, b2, c, d) in reversed(segs)]
    return segs


def simplify_wires(
    wires: Iterable[Segment],
    pins: Iterable[Point],
    dot_merge: int = 50,
    max_wire_len: int = 5000,
    obstacles: Iterable[tuple[int, int, int, int]] = (),
    break_long: bool = False,
    net_display: str = "",
) -> SimplifyResult:
    """M4 主入口：merge → trim → remove_jogs → add_junctions。

    Phase XVIII R8：``break_long=true`` 时在化简后接入
    ``split_long_wires`` —— 超长段（> ``max_wire_len``）拆成 ≤ 段长的
    子段，断口两端坐标记入 ``net_labels``（调用方在这些位置放网络名
    标签，表达"远程连接"语义）。``parallel_short`` 由 csa_writer 在
    路由前调用 ``gnd_cluster_planner.route_cluster_parallel`` 复用。

    Args:
        wires: 原始 WIRE 线段列表。
        pins: 引脚坐标（锚定判定）。
        dot_merge: 就近 DOT 合并阈值。
        max_wire_len: 超长电线阈值。
        obstacles: 元件 outline（jog 避让）。
        break_long: R8 超长断线开关（默认 False 保持旧行为）。
        net_display: 当前网显示名（断口标签的 net_display 值）。

    Returns:
        SimplifyResult（化简后的 wires/junctions + 统计 + 超长清单）。
    """
    result = SimplifyResult()
    merged = merge_segments(wires)
    result.merged_count = len(wires) - len(merged)
    trimmed = trim_stubs(merged, pins)
    result.trimmed_count = len(merged) - len(trimmed)
    jogged = remove_jogs(trimmed, obstacles)
    result.jog_count = len(trimmed) - len(jogged)
    result.junctions = add_junctions(jogged, dot_merge)
    result.long_segments = long_wire_report(jogged, max_wire_len)
    result.wires = jogged
    if break_long and result.long_segments:
        segs, breaks = split_long_wires(jogged, max_wire_len)
        result.wires = segs
        for (p1, p2) in breaks:
            if net_display:
                result.net_labels.append((p1, net_display))
                result.net_labels.append((p2, net_display))
    logger.info(
        "wire_simplify: %d → %d wires (merge=%d trim=%d jog=%d), "
        "%d junction(s), %d long, %d labels",
        len(wires), len(result.wires), result.merged_count, result.trimmed_count,
        result.jog_count, len(result.junctions), len(result.long_segments),
        len(result.net_labels),
    )
    return result
