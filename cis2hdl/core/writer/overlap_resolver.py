"""OverlapResolver — M3 重叠腾挪器（Phase XVII，用户 D10）。

检测到挤压 → 沿最小分离向量移动**可动件**（GND 符号 / 标签 / 跨页
网络名）；**芯片本体不动**（用户 D10：不移动芯片本体，只能移动 GND、
标签、跨页信号网络名）。最多 N 轮迭代（SKiDL ``overlap_force`` +
alpha 渐进思想，但只做局部腾挪：锚定固定件、推可动件）。

数据源：``detect_collisions``（M2 统一函数）—— 几何体 rect/point 两两
求交并返回最小分离向量。调用方把可动件几何放 ``movables``、固定件
（芯片/connector 轮廓）放 ``fixed``。

配置开关：``overlap.auto_placement``（默认 false；开启后作为
csa_writer/文本/GND 布局的后处理）。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from .overlap_detector import Collision, Geometry, detect_collisions

logger = logging.getLogger(__name__)

#: 默认最大迭代轮数（每轮只推一格 25，避免一次贪心移动过大）。
_DEFAULT_MAX_ITER: int = 4
#: 默认分离步长（DEHDL 25 网格）。
_DEFAULT_GRID: int = 25


@dataclass
class ResolverResult:
    """M3 腾挪结果。"""

    displacements: dict[str, tuple[int, int]] = field(default_factory=dict)
    """可动件 key → 累计位移 (dx, dy)。"""
    collisions_before: int = 0
    collisions_after: int = 0
    iterations: int = 0
    unresolved: list[str] = field(default_factory=list)


class OverlapResolver:
    """局部腾挪器：只推可动件，锚定固定件（芯片本体不动）。"""

    def __init__(
        self,
        max_iter: int = _DEFAULT_MAX_ITER,
        grid: int = _DEFAULT_GRID,
        margin: int = 25,
    ) -> None:
        """Initialize the resolver.

        Args:
            max_iter: 最大迭代轮数。
            grid: 位移 snap 网格（默认 25 = DEHDL 格点）。
            margin: 避让边距（传给 detect_collisions）。
        """
        self.max_iter = max(int(max_iter) or 1, 1)
        self.grid = int(grid) or 25
        self.margin = int(margin) or 25

    # ------------------------------------------------------------------
    #  Main entry
    # ------------------------------------------------------------------

    def resolve(
        self,
        movables: dict[str, Geometry],
        fixed: list[Geometry],
    ) -> ResolverResult:
        """迭代腾挪可动件，消除与固定件的挤压。

        Args:
            movables: 可动件 key → 几何体（point 或 rect）。位移按
                ``snap_to_grid`` 对齐网格后累计到结果。
            fixed: 固定件几何（芯片/connector outline 等，不移动）。

        Returns:
            ResolverResult（displacements / 前后碰撞数 / 迭代轮数 /
            未解决清单）。
        """
        result = ResolverResult()
        disp: dict[str, tuple[int, int]] = {k: (0, 0) for k in movables}
        positions: dict[str, Geometry] = dict(movables)

        def _count() -> int:
            collisions = detect_collisions(
                list(positions.values()), fixed, margin=self.margin,
            )
            return len(collisions)

        result.collisions_before = _count()
        for _round in range(self.max_iter):
            collisions = detect_collisions(
                list(positions.values()), fixed, margin=self.margin,
            )
            if not collisions:
                break
            changed = False
            for col in collisions:
                key = self._key_for(positions, col)
                if key is None:
                    continue
                geom = positions[key]
                dx, dy = col.separation
                if dx == 0 and dy == 0:
                    # 线段穿矩形等无分离向量情况：沿最近轴向退一格。
                    dx, dy = self._fallback_push(geom, col.b, self.margin)
                if dx == 0 and dy == 0:
                    result.unresolved.append(key)
                    continue
                moved = self._move(geom, dx, dy)
                positions[key] = moved
                # 位移按几何体参考点（点自身 / 矩形 x0,y0）累计。
                ref_dx = (moved[0] - geom[0]) if len(geom) >= 2 else 0
                ref_dy = (moved[1] - geom[1]) if len(geom) >= 2 else 0
                disp[key] = (disp[key][0] + ref_dx, disp[key][1] + ref_dy)
                changed = True
            if not changed:
                break
            result.iterations += 1

        result.collisions_after = _count()
        result.displacements = {
            k: (int(v[0]), int(v[1])) for k, v in disp.items() if v != (0, 0)
        }
        if result.displacements:
            logger.info(
                "OverlapResolver: %d collision(s) → %d after %d round(s), "
                "moved %d movable(s)",
                result.collisions_before, result.collisions_after,
                result.iterations, len(result.displacements),
            )
        return result

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key_for(
        positions: dict[str, Geometry], col: Collision,
    ) -> Optional[str]:
        """找到碰撞中可动件的 key（碰撞的 a 来自 movables 值）。

        Args:
            positions: 可动件几何表。
            col: detect_collisions 输出。

        Returns:
            可动件 key；找不到返回 None。
        """
        for key, geom in positions.items():
            if geom == col.a:
                return key
        return None

    def _fallback_push(
        self, geom: Geometry, other: Geometry, margin: int,
    ) -> tuple[int, int]:
        """无显式分离向量时的兜底：沿最近轴向推一格。

        Args:
            geom: 可动件几何。
            other: 障碍几何。
            margin: 避让边距。

        Returns:
            (dx, dy) 一个格点步长。
        """
        if len(geom) == 2:
            px, py = geom[0], geom[1]
            # 找到最近的膨胀矩形边。
            if len(other) == 4:
                x0, y0, x1, y1 = (
                    other[0] - margin, other[1] - margin,
                    other[2] + margin, other[3] + margin,
                )
                dx_right = x1 - px + self.grid
                dx_left = px - x0 + self.grid
                dy_top = y1 - py + self.grid
                dy_bottom = py - y0 + self.grid
                m = min(dx_right, dx_left, dy_top, dy_bottom)
                if m == dx_right:
                    return (self.grid, 0)
                if m == dx_left:
                    return (-self.grid, 0)
                if m == dy_top:
                    return (0, self.grid)
                return (0, -self.grid)
            return (self.grid, 0)
        return (self.grid, 0)

    def _move(self, geom: Geometry, dx: int, dy: int) -> Geometry:
        """移动几何体并把位移 snap 到网格（沿移动方向严格出界）。

        Args:
            geom: 原始几何。
            dx/dy: 分离向量（可能非网格对齐）。

        Returns:
            新几何（网格对齐；正方向取 ceil、负方向取 floor，保证
            严格越过障碍边界而非贴边）。
        """
        g = self.grid

        def _snap(v: float, positive: bool) -> int:
            q = v / g
            if positive:
                return int(math.ceil(q) * g)
            return int(math.floor(q) * g)

        def _move_axis(value: float, delta: float) -> int:
            if delta == 0:
                return int(round(value / g) * g)
            return _snap(value + delta, delta > 0)

        if len(geom) == 2:
            return (
                _move_axis(geom[0], dx),
                _move_axis(geom[1], dy),
            )
        if len(geom) == 4:
            x0, y0, x1, y1 = geom
            return (
                _move_axis(x0, dx), _move_axis(y0, dy),
                _move_axis(x1, dx), _move_axis(y1, dy),
            )
        return geom

    # ------------------------------------------------------------------
    #  R11: 被动元件微调（≤50，芯片本体不动）
    # ------------------------------------------------------------------

    def resolve_passives(
        self,
        passives: dict[str, tuple[int, int, int, int]],
        fixed: list[tuple[int, int, int, int]] | None = None,
        max_move: int = 50,
    ) -> ResolverResult:
        """被动元件（C/R/L）之间及其与固定件（芯片）的重叠微调。

        用户实测 R11：I18/I15 电阻重叠、J8/R118/R107 重叠 —— 被动元件
        允许**小范围微调**（≤ ``max_move``，默认 50，Q12），芯片本体
        不动（D10）。贪心：每对重叠，沿最小分离向量推移**后件**。

        Args:
            passives: ``{refdes: (x0, y0, x1, y1)}`` 被动元件 outline。
            fixed: 固定件 outline（芯片/connector，不移动）。
            max_move: 被动元件位移上限（``placement.max_passive_move``）。

        Returns:
            ResolverResult（displacements 为 refdes → 累计位移）。
        """
        limit = int(max_move or 50)
        result = ResolverResult()
        moves: dict[str, tuple[int, int]] = {k: (0, 0) for k in passives}
        rects: dict[str, tuple[int, int, int, int]] = dict(passives)
        fixed_list: list[tuple[int, int, int, int]] = list(fixed or [])
        keys = list(passives.keys())

        for _ in range(self.max_iter):
            moved = False
            for i in range(len(keys)):
                ka = keys[i]
                ra = rects[ka]
                for j in range(i + 1, len(keys)):
                    kb = keys[j]
                    rb = rects[kb]
                    hits = detect_collisions([ra], [rb], margin=self.margin)
                    if not hits:
                        continue
                    dx, dy = hits[0].separation
                    # Phase XXI G（用户 Cadence 16.6 实测 p16/p17/p21）：
                    # 源图坐标完全相同的 J/T 组（ra==rb）—— 分离向量是
                    # 完整推出量（宽+margin，远超 max_move）→ 被 limit 拦截
                    # 永远散不开。用**确定性偏移**兜底：按 refdes 序号
                    # 奇偶交替 ±grid（50），直接散开一格。
                    if ra == rb:
                        _alt = 1 if (i + j) % 2 == 0 else -1
                        _nudge = (_alt * self.grid, 0)
                        _cur = moves[kb]
                        _nx, _ny = _snap_mv(
                            _cur[0] + _nudge[0], _cur[1] + _nudge[1], self.grid,
                        )
                        if abs(_nx) > limit or abs(_ny) > limit:
                            continue
                        moves[kb] = (_nx, _ny)
                        rects[kb] = _shift_rect(
                            rb, _nudge[0], _nudge[1], self.grid,
                        )
                        moved = True
                        continue
                    if dx == 0 and dy == 0:
                        continue
                    # 推移后件 kb（separation 是移动 a 的向量；a=ra 前件
                    # 不动，等价于把 rb 反向移动 → 用 -separation）。
                    cur = moves[kb]
                    # 真实位移 = separation - margin 冗余（沿主轴裁剪）。
                    real_dx = _real_shift(dx, self.margin)
                    real_dy = _real_shift(dy, self.margin)
                    nx, ny = _snap_mv(cur[0] - real_dx, cur[1] - real_dy, self.grid)
                    if abs(nx) > limit or abs(ny) > limit:
                        continue
                    moves[kb] = (nx, ny)
                    # Phase XXI G（用户 Cadence 16.6 实测 p16/p17/p21）：
                    # 旧代码在此处**双重赋值** —— 第二次用完整分离向量
                    # -dx/-dy（含 margin 冗余）覆盖第一次的 real 位移 →
                    # 位移量错误/偏大，且 moves 记录 real 而 rects 记录 dx
                    # → 迭代失真、J/T 元件散不开。修复：只保留一次
                    # ``_shift_rect(rb, -real_dx, -real_dy)``（与 moves 同源）。
                    rects[kb] = _shift_rect(rb, -real_dx, -real_dy, self.grid)
                    moved = True
            if not moved:
                break
            result.iterations += 1

        # 与固定件（芯片）重叠时也微调被动件。
        if fixed_list:
            for _ in range(self.max_iter):
                moved = False
                for k in keys:
                    rk = rects[k]
                    hits = detect_collisions([rk], fixed_list, margin=self.margin)
                    if not hits:
                        continue
                    dx, dy = hits[0].separation
                    if dx == 0 and dy == 0:
                        continue
                    cur = moves[k]
                    real_dx = _real_shift(dx, self.margin)
                    real_dy = _real_shift(dy, self.margin)
                    nx, ny = _snap_mv(cur[0] - real_dx, cur[1] - real_dy, self.grid)
                    if abs(nx) > limit or abs(ny) > limit:
                        continue
                    moves[k] = (nx, ny)
                    rects[k] = _shift_rect(rk, -real_dx, -real_dy, self.grid)
                    moved = True
                if not moved:
                    break
                result.iterations += 1

        result.displacements = {k: v for k, v in moves.items() if v != (0, 0)}
        result.iterations = min(result.iterations, self.max_iter * 2)
        return result


def _shift_rect(
    rect: tuple[int, int, int, int], dx: int, dy: int, grid: int,
) -> tuple[int, int, int, int]:
    """把矩形整体平移 (dx, dy) 并 snap 到 grid。"""
    g = int(grid) or 25
    return (
        int(round((rect[0] + dx) / g)) * g,
        int(round((rect[1] + dy) / g)) * g,
        int(round((rect[2] + dx) / g)) * g,
        int(round((rect[3] + dy) / g)) * g,
    )


def _real_shift(separation_component: int, margin: int) -> int:
    """分离向量分量 - margin 冗余 = 真实位移量（同号裁剪）。

    Args:
        separation_component: 分离向量的一维分量（可为负）。
        margin: 避让冗余区（margin 不算真实位移）。

    Returns:
        真实位移量（向 0 收缩 margin；|sep| < margin 时为 0）。
    """
    m = abs(int(margin))
    if separation_component > 0:
        return max(separation_component - m, 0)
    if separation_component < 0:
        return min(separation_component + m, 0)
    return 0


def _snap_mv(dx: int, dy: int, grid: int) -> tuple[int, int]:
    """把位移 snap 到 grid（向 0 取整，位移量不小于 0）。"""
    g = int(grid) or 25

    def _one(v: int) -> int:
        if v == 0:
            return 0
        return int(v // g) * g if v > 0 else -int((-v) // g) * g

    return (_one(int(dx)), _one(int(dy)))
