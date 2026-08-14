"""OrientationPlanner — 被动元件符号方向随连线（Phase XXIII P1-4）。

用户诉求（P1-4 未开发清点）：电阻/电感/磁珠等二端被动元件的**符号绘制
方向**未随连线方向旋转 —— ``placeholder_lib``/``mock_icon_lib`` 生成符号
时固定方向，真实库 R 类符号也只按 EDIF rotation 渲染。本模块提供纯几何
函数 ``apply_passive_orientation``：

* 对 prefix ∈ {R, L, FB, FERRI, BEAD} 的二端实例，取两个引脚绝对坐标
  （pin_coords 单源）判定连线主轴：
    - Δx > Δy（水平连线）→ 符号按水平方向（rotation 0 或 180）；
    - Δy > Δx（垂直连线）→ 符号按垂直方向（rotation 90 或 270）；
    - Δx == Δy（45° / 退化）→ 保持现状（不做判定）。
* 符号 outline 尺寸随之 swap（宽↔高，中心不动）：水平 200×100 ↔
  垂直 100×200 —— 旋转后 symbol.css outline 尺寸正确。
* 引脚偏移旋转链复用 ``coord_transform.rotate_point``（rotation 字段已
  支持 R90/R180/R270），csa_writer 设置实例有效旋转后自动生效。

设计原则（STANDARDS Part I）：独立模块 + 配置开关（``placement.
rotate_passives`` 默认 false —— 默认行为等价铁律）；纯几何函数与
csa_writer 接线分离，便于单测。
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

#: Phase XXIII P1-4：参与方向判定的被动元件 refdes 前缀。
_PASSIVE_PREFIXES: frozenset[str] = frozenset(
    {"R", "L", "FB", "FERRI", "BEAD"}
)

#: 45° / 退化阈值（Δx 与 Δy 差值小于该值视为方形/对角线，不做判定）。
_SQUARE_TOL: int = 25


def _ref_prefix(refdes: str) -> str:
    """Extract the alphabetic prefix of a reference designator.

    Args:
        refdes: Instance reference designator (e.g. ``R12`` / ``FB3``).

    Returns:
        Uppercased alphabetic prefix (e.g. ``R`` / ``FB``).
    """
    m = re.match(r"^([A-Za-z]+)", str(refdes or ""))
    return (m.group(1) if m else "").upper()


def is_passive_refdes(refdes: str) -> bool:
    """True when the refdes prefix belongs to a rotate-aware passive.

    Args:
        refdes: Instance reference designator.

    Returns:
        True for R/L/FB/FERRI/BEAD prefixes.
    """
    return _ref_prefix(refdes) in _PASSIVE_PREFIXES


def passive_axis(pin_coords: Sequence[tuple[int, int]]) -> str:
    """判定两引脚连线主轴（Δx vs Δy）。

    Args:
        pin_coords: 两个（或更多）引脚绝对坐标；取前两个判定。

    Returns:
        ``"horizontal"``（Δx > Δy + 容差）| ``"vertical"``（Δy > Δx +
        容差）| ``"square"``（45° / 退化，不做判定）。
    """
    coords = [(int(p[0]), int(p[1])) for p in pin_coords]
    if len(coords) < 2:
        return "square"
    x1, y1 = coords[0]
    x2, y2 = coords[1]
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dx - dy > _SQUARE_TOL:
        return "horizontal"
    if dy - dx > _SQUARE_TOL:
        return "vertical"
    return "square"


def rotation_for_axis(axis: str, current_rotation: int) -> int:
    """按连线主轴返回目标 EDIF rotation（保持同轴类现状）。

    Args:
        axis: ``"horizontal"`` | ``"vertical"``。
        current_rotation: 当前 EDIF rotation（0/90/180/270）。

    Returns:
        horizontal → 0 或 180（当前已在水平类则保持）；
        vertical → 90 或 270（当前已在垂直类则保持）。
    """
    rot = int(current_rotation or 0) % 360
    if axis == "vertical":
        if rot in (90, 270):
            return rot
        return 90
    # horizontal
    if rot in (0, 180):
        return rot
    return 0


def swap_outline(outline: str) -> str:
    """符号 outline 尺寸 swap（宽↔高，中心不动）。

    ``"x1,y1,x2,y2"`` 矩形的宽高互换：200×100 → 100×200。中心保持，
    数值四舍五入（25 网格由调用方保证）。非法输入原样返回。

    Args:
        outline: ``CDS_LMAN_SYM_OUTLINE`` 值（如 ``"-100,50,100,-50"``）。

    Returns:
        Swap 后的 outline 字符串。
    """
    try:
        x1, y1, x2, y2 = (float(v) for v in outline.split(","))
    except ValueError:
        return outline
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    nx1 = int(round(cx - h / 2.0))
    nx2 = int(round(cx + h / 2.0))
    # 保持角点顺序（左上 → 右下）：原 y1 > y2（top first）→ swap 后仍 top first。
    if y1 >= y2:
        ny1 = int(round(cy + w / 2.0))
        ny2 = int(round(cy - w / 2.0))
    else:
        ny1 = int(round(cy - w / 2.0))
        ny2 = int(round(cy + w / 2.0))
    return f"{nx1},{ny1},{nx2},{ny2}"


def apply_passive_orientation(
    refdes: str,
    pin_coords: Sequence[tuple[int, int]],
    outline: str,
    rotation: int = 0,
) -> tuple[int, str]:
    """被动元件符号方向随连线（纯几何，Phase XXIII P1-4）。

    对 prefix ∈ {R, L, FB, FERRI, BEAD} 且 ≥2 引脚实例：按两引脚连线
    主轴判定目标方向 —— 水平（Δx>Δy）→ rotation 0/180，垂直（Δy>Δx）
    → 90/270；outline 尺寸随之 swap（宽↔高）。非被动 / 引脚不足 / 45°
    退化 → 原样返回（零回归）。

    Args:
        refdes: 实例位号（如 ``R12``）。
        pin_coords: 该实例两个引脚绝对坐标（pin_coords 单源）。
        outline: ``CDS_LMAN_SYM_OUTLINE`` 值（如 ``"-100,50,100,-50"``）。
        rotation: 当前 EDIF rotation（0/90/180/270）。

    Returns:
        ``(target_rotation, target_outline)`` —— 全整数/合法字符串。
    """
    if not is_passive_refdes(refdes):
        return int(rotation or 0) % 360, outline
    axis = passive_axis(pin_coords)
    if axis == "square":
        return int(rotation or 0) % 360, outline
    target_rot = rotation_for_axis(axis, int(rotation or 0))
    target_outline = outline
    if target_rot in (90, 270):
        target_outline = swap_outline(outline)
    return target_rot, target_outline


def rotate_pin_coords(
    pin_coords: Sequence[tuple[int, int]],
    body: tuple[int, int],
    offsets: Sequence[tuple[int, int]],
    delta_rotation: int,
) -> list[tuple[int, int]]:
    """按增量旋转把引脚偏移旋转并重算绝对坐标（复用 coord_transform 链）。

    ``delta_rotation`` 为当前有效旋转到目标旋转的增量（90/270/-90）：
    每个偏移经 ``rotate_point(off, delta_rotation)`` 旋转后加回 body，
    得到旋转后的新绝对引脚坐标 —— 与 Pass 1 的
    ``body + rotate_point(css_offset, eff_rot_dehdl)`` 完全同链。

    Args:
        pin_coords: 该实例当前引脚绝对坐标（仅用于数量对齐）。
        body: 实例 body 绝对坐标 (x, y)。
        offsets: 该实例引脚 symbol.css 相对偏移（未旋转）。
        delta_rotation: 旋转增量（90/180/270/-90 等）。

    Returns:
        旋转后引脚绝对坐标列表（与 offsets 等长）。
    """
    from .coord_transform import rotate_point

    bx, by = int(body[0]), int(body[1])
    deltas = int(delta_rotation or 0) % 360
    out: list[tuple[int, int]] = []
    for off in offsets:
        ox, oy = rotate_point(off[0], off[1], deltas)
        out.append((bx + ox, by + oy))
    return out
