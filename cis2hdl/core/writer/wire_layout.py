"""WireLayoutEngine — CSA WIRE/DOT/SIG_NAME topology synthesis.

Phase XI P0-C (system_design.md B.4): for each net, route a **horizontal
trunk + vertical stubs** bus topology whose endpoints coincide exactly with
the pin coordinates (the only geometric rule Cadence uses to determine
connectivity).  DOTs are placed conservatively at every junction where two
or more segments meet.

All coordinates are in DEHDL C-paper space (already produced by
CoordTransform + SymbolCssPinParser offsets), so the routing output plugs
directly into CSA ``WIRE 16 -1 (x1 y1)(x2 y2);`` commands.

Phase XIII T4 (Q4 P0): ``route_nets`` additionally differentiates trunk
lanes — nets are routed longest-first and a trunk that would be collinear
with an already-used trunk (same orientation, overlapping span, within
±25) is pushed to a fresh lane (lane*50) until it is free and clear of
component bodies.  This removes the "44 wires sharing one y=4400 trunk"
overlap reported in Cadence 16.6.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .router_base import ROUTER_REGISTRY, WireRouterBase, register_router

logger = logging.getLogger(__name__)

#: DEHDL grid snap — all trunk coordinates are rounded to a multiple of 25.
_GRID: int = 25
#: Lane pitch — trunks are separated by 50 (2 grid steps) so distinct nets
#: never share or touch a trunk segment.
_LANE: int = 50
#: Collinear tolerance — trunks within this distance with overlapping
#: spans count as the same lane.
_TOL: int = 25
#: Phase XVII R2: 非均匀轨道搜索半径 —— 只考虑距中位 trunk 该范围内的
#: 元件 bbox 边坐标轨道（保持 trunk 贴近引脚；超出回退均匀车道）。
_TRACK_SEARCH_RADIUS: int = 1000
#: 每个轨道候选的对称试位层数（0, ±50, ±100, ..., ±350）。
_TRACK_K_MAX: int = 8
#: C 纸页面边界（R5 边缘冗余区）：x∈[-10750,-550]、y∈[400,7200]。
_PAGE_X0: int = -10750
_PAGE_X1: int = -550
_PAGE_Y0: int = 400
_PAGE_Y1: int = 7200

# ── Phase XXII D1（Q2 能力下沉）───────────────
# 三段式 stub 相关常量原定义于 detour_router.py（Phase XV P1-G /
# Phase XVIII R5）；随辅助函数一并下沉到 WireLayoutEngine 基类，
# p0/detour 共用同一实现（Q2 统一避让实现）。
#: 绕行余量（outline 外推 50 单位 = 2 格，保持 25 网格）。
_DETOUR_MARGIN: int = 50
#: stub 引出段默认距离（routing.yaml ``stub_lead`` 覆盖）。
_STUB_LEAD: int = 100
#: 差异化引出的错开步长。
_LEAD_STEP: int = 50


def _snap(value: float) -> int:
    """Round a coordinate to the DEHDL grid (nearest multiple of 25)."""
    return int(round(value / _GRID) * _GRID)


def _net_priority_key(
    coords: list[tuple[int, int]], order: str = "long_first"
) -> tuple[int, int]:
    """Net routing priority key (Phase XVII R2).

    ``long_first``（默认，保持现状）：返回 ``(span, len)``，配合
    ``reverse=True`` 降序 —— 长网先布；``short_first``（SKiDL
    ``rank_net`` 思想，研究 B.4）：返回负号键 → 配合 ``reverse=True``
    等效升序 —— 短网先布（短网先占车道不易被挤断）。

    Args:
        coords: Distinct pin coordinates of the net.
        order: ``"long_first"`` | ``"short_first"``.

    Returns:
        Sort key tuple.
    """
    if len(coords) < 2:
        return (0, 0)
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    span = (max(xs) - min(xs)) + (max(ys) - min(ys))
    if order == "short_first":
        return (-span, -len(coords))
    return (span, len(coords))


@dataclass
class WireSegment:
    """A single CSA ``WIRE 16 -1`` segment."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def is_horizontal(self) -> bool:
        return self.y1 == self.y2

    @property
    def is_vertical(self) -> bool:
        return self.x1 == self.x2


@dataclass
class RoutedNet:
    """Routing result for a single net."""

    net_name: str
    pins: list[tuple[int, int]] = field(default_factory=list)
    wires: list[WireSegment] = field(default_factory=list)
    dots: list[tuple[int, int]] = field(default_factory=list)
    sig_name_pos: tuple[int, int] = (0, 0)
    sig_on_pin: bool = True
    """True when the SIG_NAME label is placed on a pin (source pin);
    False when it must be placed on a wire midpoint instead."""


@register_router("p0_lane")
@register_router("p0")
class WireLayoutEngine(WireRouterBase):
    """Route page nets into trunk+stub WIRE segments and compute DOTs.

    Registered in ``ROUTER_REGISTRY`` as ``"p0_lane"`` (Phase XIV D5) —
    the default fallback router.  ``route_nets`` / ``_find_lane`` /
    ``_avoid_outlines`` / ``_route_*`` are the existing P0 lane method;
    behaviour is unchanged (regression zero-impact).

    Phase XXII QA 修复（Issue 1）：``CONDITIONAL_THREE_STAGE=True`` 时只对
    **受阻 stub**（穿 outline / 跨网共线）走三段式引出，通畅 stub 保持直连
    1 段 —— p0 默认模式 WIRE 段数收敛（10165 → 6708）。DetourRouter
    （P1-G 视觉引出）置 False 保持全部 stub 引出。

    Usage::

        engine = WireLayoutEngine()
        routed = engine.route_net("N1", [(x1, y1), (x2, y2)])
        # routed.wires -> CSA WIRE commands
        # routed.dots  -> CSA DOT commands

        results = engine.route_nets(net_pin_map, body_outlines)
        # results: {net_display: RoutedNet} with lane-differentiated trunks
    """

    #: Phase XXII QA 修复（Issue 1）：条件三段式（仅受阻 stub 引出）。
    CONDITIONAL_THREE_STAGE: bool = True

    @property
    def name(self) -> str:
        """Router registry name — always ``"p0_lane"``."""
        return "p0_lane"

    # ------------------------------------------------------------------
    #  Net routing (single net — public, kept for unit tests)
    # ------------------------------------------------------------------

    def route_net(
        self,
        net_name: str,
        pins: Iterable[tuple[int, int]],
        body_outlines: Iterable[tuple[float, float, float, float]] = (),
    ) -> RoutedNet:
        """Route a single net (no lane differentiation).

        Args:
            net_name: Display name of the net.
            pins: Distinct pin coordinates (deduplicated internally).
            body_outlines: Optional (min_x,min_y,max_x,max_y) outlines of
                bodies to avoid when choosing the trunk (system_design B.4.3).

        Returns:
            RoutedNet with wires/dots/sig-name placement.
        """
        unique: list[tuple[int, int]] = list(dict.fromkeys(pins))
        result = RoutedNet(net_name=net_name, pins=list(unique))
        # Phase XXIII R-2: 每网记录 trunk 线 + 无解回退标记（report 用）。
        self._trunk_line: dict[str, tuple[int, bool]] = {}
        self._trunk_blocked_nets: set[str] = set()

        if len(unique) < 2:
            # Single-pin net: no wire, label on the pin.
            if unique:
                result.sig_name_pos = unique[0]
                result.sig_on_pin = True
            return result

        # ── Choose trunk orientation ───────────────────────────────
        xs = [p[0] for p in unique]
        ys = [p[1] for p in unique]
        x_spread = max(xs) - min(xs)
        y_spread = max(ys) - min(ys)

        if x_spread >= y_spread:
            trunk = _snap(sorted(ys)[len(ys) // 2])
            trunk = self._avoid_outlines(
                trunk, body_outlines, vertical=True,
                edge_clearance=self._edge_clearance()
                + (50 if self._gnd_boost(net_name) else 0),
                span=(min(xs), max(xs)),
            )
            result.wires = self._route_horizontal(unique, trunk)
            # Phase XXIII R-2: 记录 trunk 线 + 穿体标记（reason=trunk_blocked）。
            self._trunk_line[net_name] = (trunk, True)
            if self._trunk_crosses_outlines(
                trunk, min(xs), max(xs), body_outlines, vertical=True,
            ):
                self._trunk_blocked_nets.add(net_name)
        else:
            trunk = _snap(sorted(xs)[len(xs) // 2])
            trunk = self._avoid_outlines(
                trunk, body_outlines, vertical=False,
                edge_clearance=self._edge_clearance()
                + (50 if self._gnd_boost(net_name) else 0),
                span=(min(ys), max(ys)),
            )
            result.wires = self._route_vertical(unique, trunk)
            self._trunk_line[net_name] = (trunk, False)
            if self._trunk_crosses_outlines(
                trunk, min(ys), max(ys), body_outlines, vertical=False,
            ):
                self._trunk_blocked_nets.add(net_name)

        # ── DOTs: every junction of >= 2 segments ──────────────────
        result.dots = self.compute_dots(result.wires)

        # ── SIG_NAME: source pin = first pin in input order ────────
        result.sig_name_pos = unique[0]
        result.sig_on_pin = True
        return result

    # ------------------------------------------------------------------
    #  Net routing (all nets — lane-differentiated trunks, Phase XIII T4)
    # ------------------------------------------------------------------

    def route_nets(
        self,
        net_pin_map: dict[str, list],
        body_outlines: Iterable[tuple[float, float, float, float]] = (),
        **ctx,
    ) -> dict[str, RoutedNet]:
        """Route every page net with trunk-lane differentiation.

        Nets are routed longest-first (high span / many pins) so long nets
        claim their lanes first.  For each net the median trunk is pushed
        to the first free lane — a lane is free when it is not within ±25
        of an already-used trunk with an overlapping span interval and not
        intersecting any body outline.  This guarantees no two nets share
        a visually collinear trunk segment.

        Args:
            net_pin_map: net display name → list of pin dicts with a
                ``"coord"`` key (or plain (x, y) tuples, both accepted).
            body_outlines: (min_x,min_y,max_x,max_y) body rectangles to
                avoid when choosing trunks.
            **ctx: 透传上下文（Phase XIV D5：csa 传 design/page 给
                高级布线器；本实现忽略 —— P0 车道法不消费上下文）。

        Returns:
            ``{net_display: RoutedNet}`` for every net with >= 2 pins.
            Single-pin nets are omitted (no wire needed).
        """
        outlines: list[tuple[float, float, float, float]] = list(body_outlines)
        # Phase XXIII R-2: trunk 线（net → (trunk, vertical)）+ 无解回退
        # 穿体网集合（report reason=trunk_blocked，csa_writer 读取）。
        self._trunk_line: dict[str, tuple[int, bool]] = {}
        self._trunk_blocked_nets: set[str] = set()
        # Phase XXII D1（Q2 能力下沉）：stash pin→body hints 与 outlines，
        # 供 _route_horizontal/_route_vertical 的三段式 stub（原
        # DetourRouter.route_nets 逻辑，基类共享）决定引出方向与避障。
        self._pin_bodies: dict[tuple[int, int], tuple[int, int]] = dict(
            ctx.get("pin_bodies") or {}
        )
        self._three_outlines: list[tuple[int, int, int, int]] = outlines
        results: dict[str, RoutedNet] = {}
        # Phase XVII R2: 从 RoutingConfig 读取"非均匀轨道 + 布线顺序"。
        cfg = getattr(self, "cfg", None)
        nonuniform = bool(
            getattr(cfg, "nonuniform_tracks", False) if cfg is not None else False
        )
        net_order = str(
            getattr(cfg, "net_order", "long_first") or "long_first"
        ) if cfg is not None else "long_first"
        if net_order not in ("long_first", "short_first"):
            logger.warning(
                "unknown net_order %r → long_first", net_order,
            )
            net_order = "long_first"
        # 轨道优先：路由前收集页面所有元件 outline 的 bbox 边坐标
        # （H 轨道 = min_y/max_y；V 轨道 = min_x/max_x），构成候选 trunk
        # 坐标集合（SKiDL create_routing_tracks 思想，研究 B.3）。
        h_tracks: list[int] | None = None
        v_tracks: list[int] | None = None
        if nonuniform:
            h_tracks = self._collect_tracks(outlines, vertical=True)
            v_tracks = self._collect_tracks(outlines, vertical=False)
        # Every horizontal / vertical segment already routed (trunk pieces
        # AND stubs).  A new trunk must stay clear of same-orientation
        # segments so no two nets share a colinear run (Phase XIII T4).
        busy_h: list[tuple[int, int, int]] = []  # (y, x0, x1)
        busy_v: list[tuple[int, int, int]] = []  # (x, y0, y1)

        def _priority(item: tuple[str, list]) -> tuple:
            _name, pins = item
            return _net_priority_key(self._coords(pins), net_order)

        # All pin coordinates on the page, used to keep every trunk clear of
        # OTHER nets' pins (Phase XIII Round 2): a trunk passing through
        # another net's pin makes that pin's stub endpoint land on the trunk
        # → DEHDL connects the two nets (short).
        all_pin_counts: dict[tuple[int, int], int] = {}
        for pins in net_pin_map.values():
            for coord in self._coords(pins):
                all_pin_counts[coord] = all_pin_counts.get(coord, 0) + 1

        for net_name, pins in sorted(
            net_pin_map.items(), key=_priority, reverse=True
        ):
            if "CIS2HDL_DEBUG_ORDER" in __import__("os").environ:
                print(f"DBG routing order: {net_name} key={_priority((net_name, pins))}")
            unique = list(dict.fromkeys(self._coords(pins)))
            if len(unique) < 2:
                continue
            result = RoutedNet(net_name=net_name, pins=list(unique))

            # Other nets' pins (a coordinate owned MORE times than this net
            # owns it belongs to another net — handles coincident pins).
            own = Counter(unique)
            other_pins = [
                coord for coord, cnt in all_pin_counts.items()
                if cnt > own.get(coord, 0)
            ]
            other_by_x: dict[int, list[int]] = defaultdict(list)
            other_by_y: dict[int, list[int]] = defaultdict(list)
            for px, py in other_pins:
                other_by_x[px].append(py)
                other_by_y[py].append(px)

            xs = [p[0] for p in unique]
            ys = [p[1] for p in unique]
            x_spread = max(xs) - min(xs)
            y_spread = max(ys) - min(ys)

            if x_spread >= y_spread:
                # horizontal trunk (y fixed): avoid other pins at the same y
                self._current_net_gnd = self._gnd_boost(net_name)
                _trunk_median = _snap(sorted(ys)[len(ys) // 2])
                trunk = self._find_lane(
                    _trunk_median, min(xs), max(xs), busy_h, outlines,
                    vertical=True, other_by_y=other_by_y, tracks=h_tracks,
                )
                # Phase XXIII R-2: 冲突计数优先（trunk+stub 总穿体最少）。
                trunk = self._min_crossing_trunk(
                    trunk, _trunk_median, unique, min(xs), max(xs),
                    busy_h, outlines, vertical=True, other_by_y=other_by_y,
                )
                result.wires = self._route_horizontal(
                    unique, trunk, busy_h=busy_h, busy_v=busy_v,
                )
                # Phase XXIII R-2: 记录 trunk 线 + 无解回退穿体标记。
                self._trunk_line[net_name] = (trunk, True)
                if self._trunk_crosses_outlines(
                    trunk, min(xs), max(xs), outlines, vertical=True,
                ):
                    self._trunk_blocked_nets.add(net_name)
            else:
                # vertical trunk (x fixed): avoid other pins at the same x
                self._current_net_gnd = self._gnd_boost(net_name)
                _trunk_median = _snap(sorted(xs)[len(xs) // 2])
                trunk = self._find_lane(
                    _trunk_median, min(ys), max(ys), busy_v, outlines,
                    vertical=False, other_by_x=other_by_x, tracks=v_tracks,
                )
                trunk = self._min_crossing_trunk(
                    trunk, _trunk_median, unique, min(ys), max(ys),
                    busy_v, outlines, vertical=False, other_by_x=other_by_x,
                )
                result.wires = self._route_vertical(
                    unique, trunk, busy_h=busy_h, busy_v=busy_v,
                )
                self._trunk_line[net_name] = (trunk, False)
                if self._trunk_crosses_outlines(
                    trunk, min(ys), max(ys), outlines, vertical=False,
                ):
                    self._trunk_blocked_nets.add(net_name)

            # Phase XXII D1: 三段式 stub 可能产生同网重复段（两个引脚路径
            # 共享同一段）——每网去重（零长/重复段剔除）。旧直 stub 无重复，
            # 去重是 no-op（零回归）。
            result.wires = self._dedupe_wires(result.wires)

            # record every segment so later trunks avoid them
            for w in result.wires:
                if w.is_horizontal:
                    busy_h.append(
                        (w.y1, min(w.x1, w.x2), max(w.x1, w.x2))
                    )
                else:
                    busy_v.append(
                        (w.x1, min(w.y1, w.y2), max(w.y1, w.y2))
                    )

            result.dots = self.compute_dots(result.wires)
            result.sig_name_pos = unique[0]
            result.sig_on_pin = True
            results[net_name] = result
        return results

    # ------------------------------------------------------------------
    #  R5 config helpers (edge clearance / pin avoidance radius)
    # ------------------------------------------------------------------

    def _edge_clearance(self) -> int:
        """Read ``routing.edge_clearance`` from the attached RoutingConfig.

        No cfg (standalone router / legacy callers) → 0 = no page-edge
        constraint, preserving the original behaviour.

        Returns:
            Page-edge red-zone width in units.
        """
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return 0
        return int(getattr(cfg, "edge_clearance", 0) or 0)

    def _gnd_boost(self, net_name: str) -> bool:
        """True when the net is GND and ``gnd.distribute_density`` is on.

        Phase XXIII P1-3（T1.2）：GND 网（``GND\\g`` 等）trunk 避让时
        lane 避让权重提高 —— ``_find_lane`` / ``route_net`` 对 GND 网用
        ``edge_clearance + 50`` 额外余量，降低 GND trunk 穿元件体。

        Args:
            net_name: Net display name.

        Returns:
            True when the +50 edge-clearance boost applies.
        """
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return False
        gnd_cfg = getattr(cfg, "gnd_distribution", None)
        if not bool(getattr(gnd_cfg, "distribute_density", False)):
            return False
        bare = str(net_name).replace("\\g", "").lower().split("@", 1)[0].strip()
        return bare in (
            "gnd", "gnd_power", "dgnd", "agnd", "pgnd",
            "gnd_earth", "gnd_signal", "gnd_chassis",
        )

    def _pin_radius(self) -> int:
        """Read ``overlap.pin_avoid_radius`` from the attached RoutingConfig.

        No cfg (standalone router / legacy callers) → 0 = exact-hit only,
        preserving the original ``_pin_on_trunk`` behaviour.

        Returns:
            Pin-avoidance radius in units (0 = disabled).
        """
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return 0
        overlap = getattr(cfg, "overlap", None)
        if overlap is None:
            return 0
        return int(getattr(overlap, "pin_avoid_radius", 0) or 0)

    # ------------------------------------------------------------------
    #  Lane selection (Phase XIII T4)
    # ------------------------------------------------------------------

    def _find_lane(
        self,
        trunk: int,
        lo: int,
        hi: int,
        used: list[tuple[int, int, int]],
        body_outlines: list[tuple[float, float, float, float]],
        vertical: bool,
        other_by_x: dict[int, list[int]] | None = None,
        other_by_y: dict[int, list[int]] | None = None,
        tracks: list[int] | None = None,
    ) -> int:
        """Push a trunk coordinate to the first free lane.

        Phase XVII R2（轨道优先）：当 ``tracks``（元件 bbox 边坐标轨道，
        见 ``_collect_tracks``）非空时，先在轨道上找空闲车道 —— 每个轨道
        按距中位 trunk 的距离升序尝试，轨道本身做 ±50 对称试位（0, +50,
        -50, +100, -100, ...，最多 ``_TRACK_K_MAX`` 层），命中即返回；
        全部未命中再回退现有均匀车道。这样同列/同行元件自然共线对齐
        （SKiDL ``create_routing_tracks`` 思想，研究 B.3），同时保持
        trunk 不穿 outline、端点重合、25 网格等既有约束。

        原有行为（``tracks=None``）：Starting at the median ``trunk``,
        try offsets 0, +50, -50, +100, -100, ... (both directions so dense
        pages spread lanes above AND below the median instead of stacking
        off-page).  Each candidate is first pushed out of any body outline
        it intersects, then checked against ``used`` trunks (same
        orientation, overlapping span, within ±25), and finally against
        OTHER nets' pins — a trunk must not pass through another net's pin
        or that pin's stub endpoint lands on the trunk (DEHDL short).
        Candidates outside the C-page bounds are skipped; if no free
        in-bounds lane exists the median is returned (graceful degradation
        on ultra-dense pages — better an on-page shared lane than an
        off-page wire).

        Args:
            trunk: Median trunk coordinate (snapped to grid).
            lo/hi: The net's span interval along the trunk direction.
            used: Busy same-orientation segments ``(value, span_lo,
                span_hi)`` (trunk lanes AND stubs of already-routed nets).
            body_outlines: Body rectangles to avoid.
            vertical: True when routing a horizontal trunk (y fixed).
            other_by_x: Other nets' pin y's indexed by pin x (vertical trunk
                pin-collision check).
            other_by_y: Other nets' pin x's indexed by pin y (horizontal
                trunk pin-collision check).
            tracks: 非均匀轨道候选坐标（元件 bbox 边，去重排序）；None 或
                空列表 = 只用均匀车道（Phase XIII T4 原行为）。

        Returns:
            Final trunk coordinate.
        """
        # C SIZE PAGE bounds for the trunk coordinate (full page frame).
        v_min, v_max = (0, 8275) if vertical else (-10750, 0)
        best: int = trunk
        # R5：页面边缘冗余区 + 引脚避让半径（配置驱动；无 cfg → 0 保持旧行为）。
        # Phase XXIII P1-3（T1.2）：GND 网（distribute_density）额外 +50
        # 余量 —— ``route_nets`` 已按当前网设置 ``self._current_net_gnd``。
        edge_clearance = self._edge_clearance() + (
            50 if getattr(self, "_current_net_gnd", False) else 0
        )
        pin_radius = self._pin_radius()

        # ── 轨道优先（Phase XVII R2，SKiDL create_routing_tracks 思想）──
        if tracks:
            # 只考虑搜索半径内的轨道（保持 trunk 贴近引脚），按距中位
            # trunk 的距离升序 —— 最近的元件边优先。
            candidates = [
                t for t in tracks if abs(t - trunk) <= _TRACK_SEARCH_RADIUS
            ]
            candidates.sort(key=lambda t: abs(t - trunk))
            for track in candidates:
                for k in range(0, _TRACK_K_MAX):
                    if k == 0:
                        offsets: list[int] = [0]
                    else:
                        # symmetric: try +k*50 then -k*50 at each distance
                        offsets = [k * _LANE, -k * _LANE]
                    for off in offsets:
                        candidate = track + off
                        if not (v_min <= candidate <= v_max):
                            continue
                        final = self._avoid_outlines(
                            candidate, body_outlines, vertical,
                            edge_clearance=edge_clearance,
                            span=(lo, hi),
                        )
                        if not (v_min <= final <= v_max):
                            continue
                        if not self._lane_free(final, lo, hi, used):
                            continue
                        if self._pin_on_trunk(
                            final, lo, hi, vertical, other_by_x, other_by_y,
                            pin_radius=pin_radius,
                        ):
                            continue
                        return final

        # ── 回退：现有均匀车道（中位 ±50 对称）─────────────────────
        for k in range(0, 401):
            if k == 0:
                offsets = [0]
            else:
                # symmetric: try +k*50 then -k*50 at each distance
                offsets = [k * _LANE, -k * _LANE]
            for off in offsets:
                candidate = trunk + off
                if not (v_min <= candidate <= v_max):
                    continue
                final = self._avoid_outlines(
                    candidate, body_outlines, vertical,
                    edge_clearance=edge_clearance,
                    span=(lo, hi),
                )
                if not (v_min <= final <= v_max):
                    continue
                if not self._lane_free(final, lo, hi, used):
                    continue
                if self._pin_on_trunk(
                    final, lo, hi, vertical, other_by_x, other_by_y,
                    pin_radius=pin_radius,
                ):
                    continue
                return final
        return best

    @staticmethod
    def _collect_tracks(
        body_outlines: Iterable[tuple[float, float, float, float]],
        vertical: bool,
    ) -> list[int]:
        """Collect non-uniform track coordinates from outline edges.

        SKiDL ``create_routing_tracks`` 思想（研究 B.3）：元件 bbox 的边
        坐标构成"轨道优先"候选 trunk 集 —— 同列/同行元件自然共线对齐。
        去重 + 排序 + 25 网格。

        Args:
            body_outlines: (min_x, min_y, max_x, max_y) 元件轮廓矩形。
            vertical: True（水平 trunk，y 固定）→ 各 outline 的
                min_y/max_y 构成 H 轨道；False（垂直 trunk，x 固定）→
                min_x/max_x 构成 V 轨道。

        Returns:
            去重排序的轨道坐标列表（可能为空）。
        """
        coords: set[int] = set()
        for (ox0, oy0, ox1, oy1) in body_outlines:
            if vertical:
                coords.add(_snap(float(oy0)))
                coords.add(_snap(float(oy1)))
            else:
                coords.add(_snap(float(ox0)))
                coords.add(_snap(float(ox1)))
        return sorted(coords)

    @staticmethod
    def _pin_on_trunk(
        candidate: int,
        lo: int,
        hi: int,
        vertical: bool,
        other_by_x: dict[int, list[int]] | None,
        other_by_y: dict[int, list[int]] | None,
        pin_radius: int = 0,
    ) -> bool:
        """True when the trunk line at ``candidate`` passes through another
        net's pin (a DEHDL short — the pin's stub endpoint would land on the
        trunk).

        Phase XVIII R5：由"精确命中"扩展为"±pin_avoid_radius 命中"
        （trunk 不得在引脚 ``pin_avoid_radius`` 单位内穿过 —— 防误连接）。
        ``pin_radius=0`` 保持旧精确行为。
        """
        radius = max(0, int(pin_radius or 0))
        if vertical:
            # horizontal trunk at y=candidate: other pins at the same y
            # whose x lies inside the trunk span [lo, hi]
            if not other_by_y:
                return False
            for y in range(candidate - radius, candidate + radius + 1):
                for px in other_by_y.get(y, ()):
                    if lo <= px <= hi:
                        return True
        else:
            # vertical trunk at x=candidate: other pins at the same x
            # whose y lies inside the trunk span [lo, hi]
            if not other_by_x:
                return False
            for x in range(candidate - radius, candidate + radius + 1):
                for py in other_by_x.get(x, ()):
                    if lo <= py <= hi:
                        return True
        return False

    @staticmethod
    def _lane_free(
        candidate: int, lo: int, hi: int, used: list[tuple[int, int, int]]
    ) -> bool:
        """True when ``candidate`` does not collide with any used lane.

        Two trunks are considered the same lane when their values differ
        by at most ``_TOL`` AND their span intervals overlap OR touch
        (closed interval).  Phase XIII Round 2 (QA short-circuit bug):
        two trunks whose spans meet at an endpoint share that coordinate —
        Cadence DEHDL connects coincident endpoints, so touching spans
        MUST be separated onto different lanes or the two nets short.
        """
        for u_val, u_lo, u_hi in used:
            if abs(u_val - candidate) <= _TOL and max(lo, u_lo) <= min(hi, u_hi):
                return False
        return True

    # ------------------------------------------------------------------
    #  Horizontal trunk routing
    # ------------------------------------------------------------------

    def _route_horizontal(
        self,
        pins: list[tuple[int, int]],
        trunk: int,
        busy_h: list[tuple[int, int, int]] | None = None,
        busy_v: list[tuple[int, int, int]] | None = None,
    ) -> list[WireSegment]:
        """Route with a horizontal trunk at ``trunk`` and vertical stubs.

        Phase XXII D1（Q2 能力下沉）：``self.cfg`` 存在且
        ``routing.three_stage_stub=true`` 时每条 stub 走三段式
        （延伸→折线→调头，原 DetourRouter._route_horizontal 逻辑，
        p0/detour 共用）；否则保持旧直 stub（无 cfg 单测零回归）。

        Phase XXII D1 增强（设计风险 #3）：``busy_h``/``busy_v`` 为其他网
        已路由段（route_nets 传入）——三段式 stub 避让跨网共线，防 DEHDL
        短路。``route_net``（单网）调用缺省空列表（同旧行为）。
        """
        if not self._three_stage_enabled():
            return self._route_horizontal_plain(pins, trunk)
        lead, differentiate, min_gap = self._stub_lead_cfg()
        if lead <= 0:
            return self._route_horizontal_plain(pins, trunk)

        busy_h = list(busy_h or ())
        busy_v = list(busy_v or ())
        lead_map = self._lead_map(pins, lead, differentiate, min_gap)
        segments: list[WireSegment] = []
        trunk_xs: set[int] = {min(p[0] for p in pins), max(p[0] for p in pins)}
        jog_lanes: list[int] = []  # 同网已占用折线车道（防同网共线）
        for x, y in pins:
            trunk_xs.add(x)
            if y == trunk:
                continue
            # Phase XXII QA 修复（Issue 1）：**条件三段式** —— 仅当直 stub
            # 受阻（穿 outline）才走引出段+折线；通畅 stub 保持直连 1 段
            # （WIRE 收敛）。detour（P1-G 视觉引出）置
            # CONDITIONAL_THREE_STAGE=False → 全部 stub 引出。
            plain = WireSegment(x, y, x, trunk)
            if (self.CONDITIONAL_THREE_STAGE
                    and not self._stub_direct_blocked(
                        [plain], self._three_stage_outlines(), [], [],
                        vertical=True, check_page_band=False,
                    )):
                segments.append(plain)
                continue
            lx, ly = self._lead_point(x, y, lead_map[(x, y)])
            if (lx, ly) == (x, y):
                segments.append(plain)
                continue
            pieces = self._three_stage_stub(
                (x, y), trunk, vertical=True,
                outlines=self._three_stage_outlines(),
                busy_h=busy_h, busy_v=busy_v,
                lead=lead_map[(x, y)], jog_lanes=jog_lanes,
            )
            for w in pieces:
                trunk_xs.update(self._trunk_end_coords(w, trunk, vertical=False))
            segments.extend(pieces)

        sorted_xs = sorted(trunk_xs)
        for a, b in zip(sorted_xs, sorted_xs[1:]):
            segments.append(WireSegment(a, trunk, b, trunk))
        return segments

    def _route_horizontal_plain(
        self,
        pins: list[tuple[int, int]],
        trunk: int,
    ) -> list[WireSegment]:
        """Horizontal trunk + straight vertical stubs（旧直 stub，无 cfg 零回归）。"""
        xs = [p[0] for p in pins]
        ys = [p[1] for p in pins]

        min_x, max_x = min(xs), max(xs)
        segments: list[WireSegment] = []

        # Vertical stubs from each pin to the trunk
        for x, y in pins:
            if y != trunk:
                segments.append(WireSegment(x, y, x, trunk))

        # Trunk segments, split at every pin x (on-trunk or off-trunk)
        # so passing pins become segment endpoints (Cadence coincidence rule).
        # When every pin lies ON the trunk line the pieces above already
        # span [min_x, max_x], so no extra full-span segment is emitted
        # (Phase XIII T4: a redundant full span would overlap the pieces).
        trunk_xs = sorted(set(x for x, _ in pins) | {min_x, max_x})
        for a, b in zip(trunk_xs, trunk_xs[1:]):
            segments.append(WireSegment(a, trunk, b, trunk))

        return segments

    def _route_vertical(
        self,
        pins: list[tuple[int, int]],
        trunk: int,
        busy_h: list[tuple[int, int, int]] | None = None,
        busy_v: list[tuple[int, int, int]] | None = None,
    ) -> list[WireSegment]:
        """Route with a vertical trunk at ``trunk`` and horizontal stubs.

        Phase XXII D1（Q2 能力下沉）：同 ``_route_horizontal`` ——
        cfg 且 three_stage_stub=true 时走三段式，否则旧直 stub；
        ``busy_h``/``busy_v`` 跨网段避让（设计风险 #3）。
        """
        if not self._three_stage_enabled():
            return self._route_vertical_plain(pins, trunk)
        lead, differentiate, min_gap = self._stub_lead_cfg()
        if lead <= 0:
            return self._route_vertical_plain(pins, trunk)

        busy_h = list(busy_h or ())
        busy_v = list(busy_v or ())
        lead_map = self._lead_map(pins, lead, differentiate, min_gap)
        segments: list[WireSegment] = []
        trunk_ys: set[int] = {min(p[1] for p in pins), max(p[1] for p in pins)}
        jog_lanes: list[int] = []  # 同网已占用折线车道（防同网共线）
        for x, y in pins:
            trunk_ys.add(y)
            if x == trunk:
                continue
            # Phase XXII QA 修复（Issue 1）：**条件三段式**（同 _route_horizontal）。
            plain = WireSegment(x, y, trunk, y)
            if (self.CONDITIONAL_THREE_STAGE
                    and not self._stub_direct_blocked(
                        [plain], self._three_stage_outlines(), [], [],
                        vertical=False, check_page_band=False,
                    )):
                segments.append(plain)
                continue
            lx, ly = self._lead_point(x, y, lead_map[(x, y)])
            if (lx, ly) == (x, y):
                segments.append(plain)
                continue
            pieces = self._three_stage_stub(
                (x, y), trunk, vertical=False,
                outlines=self._three_stage_outlines(),
                busy_h=busy_h, busy_v=busy_v,
                lead=lead_map[(x, y)], jog_lanes=jog_lanes,
            )
            for w in pieces:
                trunk_ys.update(self._trunk_end_coords(w, trunk, vertical=True))
            segments.extend(pieces)

        sorted_ys = sorted(trunk_ys)
        for a, b in zip(sorted_ys, sorted_ys[1:]):
            segments.append(WireSegment(trunk, a, trunk, b))
        return segments

    def _route_vertical_plain(
        self,
        pins: list[tuple[int, int]],
        trunk: int,
    ) -> list[WireSegment]:
        """Vertical trunk + straight horizontal stubs（旧直 stub，无 cfg 零回归）。"""
        xs = [p[0] for p in pins]
        ys = [p[1] for p in pins]

        min_y, max_y = min(ys), max(ys)
        segments: list[WireSegment] = []

        for x, y in pins:
            if x != trunk:
                segments.append(WireSegment(x, y, trunk, y))

        trunk_ys = sorted(set(y for x, y in pins) | {min_y, max_y})
        for a, b in zip(trunk_ys, trunk_ys[1:]):
            segments.append(WireSegment(trunk, a, trunk, b))

        return segments

    # ------------------------------------------------------------------
    #  Phase XXII D1 (Q2 能力下沉): stub 引出段 + 三段式 stub 辅助
    # ------------------------------------------------------------------
    # 以下纯几何 + cfg 辅助函数原定义于 DetourRouter（Phase XV P1-G /
    # Phase XVIII R5），现下沉到基类供 p0/detour 共用（Q2 统一实现，
    # 原样搬迁，无行为变化）。

    @staticmethod
    def _snap(value: float) -> int:
        """Round a coordinate to the DEHDL grid (nearest multiple of 25)."""
        return _snap(value)

    def _stub_lead_cfg(self) -> tuple[int, bool, int]:
        """Read stub-lead parameters from the RoutingConfig (or defaults).

        ``stub_lead=0`` is a valid "disable" value (no lead-out).

        Returns:
            ``(stub_lead, differentiate, min_gap)``.
        """
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return _STUB_LEAD, True, 75
        lead_raw = getattr(cfg, "stub_lead", None)
        lead = _STUB_LEAD if lead_raw is None else int(lead_raw)
        differentiate = bool(getattr(cfg, "lead_differentiate", True))
        min_gap = int(getattr(cfg, "lead_diff_min_gap", 75) or 75)
        return lead, differentiate, min_gap

    def _three_stage_enabled(self) -> bool:
        """Read ``routing.three_stage_stub`` from the attached config.

        No cfg (standalone router / legacy callers) → False, preserving
        the original straight-stub behaviour.

        Returns:
            True when the three-stage stub is enabled.
        """
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return False
        return bool(getattr(cfg, "three_stage_stub", False))

    def _three_stage_outlines(self) -> list:
        """Outlines stashed by ``route_nets`` for the three-stage stub.

        Returns:
            Body outline list (default empty when not stashed).
        """
        return list(getattr(self, "_three_outlines", []) or [])

    def _edge_clearance_cfg(self) -> int:
        """Read ``routing.edge_clearance`` from the attached config."""
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return 0
        return int(getattr(cfg, "edge_clearance", 0) or 0)

    def _detour_margin(self) -> int:
        """Read the detour margin from RoutingConfig (``max_detour``).

        Returns:
            Detour margin in units (default ``_DETOUR_MARGIN``).
        """
        cfg = getattr(self, "cfg", None)
        if cfg is None:
            return _DETOUR_MARGIN
        raw = getattr(cfg, "max_detour", None)
        return _DETOUR_MARGIN if raw is None else int(raw)

    def _lead_map(
        self,
        pins: list[tuple[int, int]],
        base_lead: int,
        differentiate: bool,
        min_gap: int,
    ) -> dict[tuple[int, int], int]:
        """Assign per-pin lead distances (differentiated for near pins).

        Pins whose x-coordinate lies within ``min_gap`` of each other
        (parallel vertical stubs) form a cluster — members get alternating
        distances ``base, base+50, base+100, base, ...`` so adjacent exit
        segments never overlap.

        Args:
            pins: Distinct pin coordinates.
            base_lead: Base lead distance.
            differentiate: Whether to stagger adjacent pins.
            min_gap: Adjacency threshold.

        Returns:
            ``{pin: lead_distance}`` for every pin.
        """
        lead_map: dict[tuple[int, int], int] = {}
        if not differentiate:
            for pin in pins:
                lead_map[pin] = base_lead
            return lead_map
        # Greedy x-clustering: consecutive sorted pins with x-gap ≤ min_gap
        # belong to the same cluster (they route to the same trunk lane).
        clusters: list[list[tuple[int, int]]] = []
        for pin in sorted(pins):
            if clusters and abs(pin[0] - clusters[-1][-1][0]) <= min_gap:
                clusters[-1].append(pin)
            else:
                clusters.append([pin])
        for cluster in clusters:
            for run, pin in enumerate(cluster):
                lead_map[pin] = base_lead + (run % 3) * _LEAD_STEP
        return lead_map

    def _lead_point(
        self, x: int, y: int, lead: int,
    ) -> tuple[int, int]:
        """Compute the lead-out point for a pin.

        The direction is AWAY from the component body center
        (``self._pin_bodies``); when no body hint exists the pin leads
        toward the page's positive direction (up/right) as a safe default.

        Args:
            x/y: Pin coordinate.
            lead: Lead distance for this pin.

        Returns:
            ``(lx, ly)`` snapped to the 25-unit grid.
        """
        bx, by = getattr(self, "_pin_bodies", {}).get((x, y), (x, y))
        dx = x - bx
        dy = y - by
        if dx == 0 and dy == 0:
            # No body hint → lead up (positive y), the common exit side.
            return (self._snap(x), self._snap(y + lead))
        if abs(dx) >= abs(dy):
            sign = 1 if dx > 0 else -1
            return (self._snap(x + sign * lead), self._snap(y))
        sign = 1 if dy > 0 else -1
        return (self._snap(x), self._snap(y + sign * lead))

    @staticmethod
    def _trunk_end_coords(
        w: WireSegment, trunk: int, vertical: bool,
    ) -> set[int]:
        """Stub 段中落在 trunk 上的端点坐标（供 trunk 段拼接）。

        Args:
            w: Stub wire segment.
            trunk: Trunk coordinate.
            vertical: True = 垂直 trunk（x 固定）→ 返回端点 y；
                False = 水平 trunk（y 固定）→ 返回端点 x。

        Returns:
            ``{coord}``（可能为空）。
        """
        out: set[int] = set()
        if vertical:  # trunk x fixed
            if w.x1 == trunk:
                out.add(w.y1)
            if w.x2 == trunk:
                out.add(w.y2)
        else:  # horizontal trunk (y fixed)
            if w.y1 == trunk:
                out.add(w.x1)
            if w.y2 == trunk:
                out.add(w.x2)
        return out

    def _three_stage_stub(
        self,
        pin: tuple[int, int],
        trunk: int,
        vertical: bool,
        outlines: list,
        busy_h: list,
        busy_v: list,
        lead: int | None = None,
        jog_lanes: list[int] | None = None,
    ) -> list[WireSegment]:
        """三段式 stub（用户明确要求"先延伸→折线避让→调头"）。

        1. 延伸：pin → E（沿背离 body 方向外引 stub_lead）；
        2. 折线：E → J（垂直于 E→trunk 方向外推，绕开 outline + 页面
           冗余区 + 已占用车道，取最近空闲 50 倍数车道）；
        3. 调头：J → T'（回到 trunk 方向，最终接到 trunk）。

        直接路径无冲突时退化为 2 段（延伸 + 直达 trunk）—— 折线只在该
        绕不可避时启用，保证同网折线车道互不共线（``jog_lanes``）。

        Args:
            pin: 引脚坐标（端点不动）。
            trunk: trunk 值（水平 trunk = y；垂直 trunk = x）。
            vertical: True = 水平 trunk（stub 垂直）；False = 垂直 trunk。
            outlines: 元件 outline 矩形（避让）。
            busy_h/busy_v: 其他网段占用车道（避让）。
            lead: 该引脚引出距离（缺省从配置读取）。
            jog_lanes: 同网已占用折线车道（同一可变列表，防同网共线）。

        Returns:
            1-3 段 WireSegment（零长剔除；端点 pin 坐标不变，全 25 网格）。
        """
        lead_val = int(lead) if lead is not None else self._stub_lead_cfg()[0]
        if lead_val <= 0:
            if vertical:
                return [WireSegment(pin[0], pin[1], pin[0], trunk)]
            return [WireSegment(pin[0], pin[1], trunk, pin[1])]
        ex, ey = self._lead_point(pin[0], pin[1], lead_val)
        if vertical:
            direct = [
                WireSegment(pin[0], pin[1], ex, ey),
                WireSegment(ex, ey, ex, trunk),
            ]
        else:
            direct = [
                WireSegment(pin[0], pin[1], ex, ey),
                WireSegment(ex, ey, trunk, ey),
            ]
        if not self._stub_direct_blocked(
            direct, outlines, busy_h, busy_v, vertical,
        ):
            return direct
        base = self._detour_margin() + self._edge_clearance_cfg()
        pieces = self._try_jog_candidates(
            pin, ex, ey, trunk, vertical, outlines, busy_h, busy_v,
            jog_lanes, base,
        )
        if pieces:
            return pieces
        # 无空闲折线车道 → 回退**直 stub**（pin→trunk，不带引出段）——
        # 比"带引出段的直接路径"穿体更少（引出段会额外穿邻居元件体）；
        # 正交绕障回退实测更差（绕障路径穿相邻元件体，Issue 2 已文档化）。
        if vertical:
            return [WireSegment(pin[0], pin[1], pin[0], trunk)]
        return [WireSegment(pin[0], pin[1], trunk, pin[1])]

    def _try_jog_candidates(
        self,
        pin: tuple[int, int],
        ex: int, ey: int,
        trunk: int,
        vertical: bool,
        outlines: list,
        busy_h: list,
        busy_v: list,
        jog_lanes: list[int] | None,
        base: int,
    ) -> list[WireSegment]:
        """三段式折线候选：E→J→T'（两个方向、递增 50，取最近空闲）。

        Args:
            pin: 引脚坐标（端点不动）。
            ex/ey: 引出点 E。
            trunk: trunk 值。
            vertical: True = 水平 trunk（stub 垂直）。
            outlines/busy_h/busy_v: 避让障碍。
            jog_lanes: 同网已占用折线车道（可变列表，命中即占用）。
            base: 折线基础偏移（max_detour + edge_clearance）。

        Returns:
            3 段折线路径；无空闲车道返回空列表。
        """
        for k in range(0, 16):
            off = self._snap(base + k * 50)
            for sign in (1, -1):
                if vertical:
                    lane = self._snap(ex + sign * off)
                    if jog_lanes is not None and lane in jog_lanes:
                        continue
                    if not self._jog_clear(
                        lane, ey, ex, ey, trunk, vertical, outlines,
                        busy_h, busy_v,
                    ):
                        continue
                    pieces = [
                        WireSegment(pin[0], pin[1], ex, ey),
                        WireSegment(ex, ey, lane, ey),
                        WireSegment(lane, ey, lane, trunk),
                    ]
                else:
                    lane = self._snap(ey + sign * off)
                    if jog_lanes is not None and lane in jog_lanes:
                        continue
                    if not self._jog_clear(
                        ex, lane, ex, ey, trunk, vertical, outlines,
                        busy_h, busy_v,
                    ):
                        continue
                    pieces = [
                        WireSegment(pin[0], pin[1], ex, ey),
                        WireSegment(ex, ey, ex, lane),
                        WireSegment(ex, lane, trunk, lane),
                    ]
                cleaned = self._clean_pieces(pieces)
                if cleaned:
                    if jog_lanes is not None:
                        jog_lanes.append(lane)
                    return cleaned
        return []

    def _stub_direct_blocked(
        self,
        direct: list[WireSegment],
        outlines: list,
        busy_h: list,
        busy_v: list,
        vertical: bool,
        check_page_band: bool = True,
    ) -> bool:
        """True 时三段式需要折线绕行（直接路径穿 outline/占用车道/页边）。

        检查**每段**（P→E 引出段与 E→trunk 段）对 outline 与同向占用
        车道的冲突；页边带只对 E→trunk 最终段检查（Phase XXII D1 增强：
        跨网共线由 route_nets 传入 busy_h/busy_v 避让，设计风险 #3）。

        Phase XXII QA 修复（Issue 1）：``check_page_band=False`` 时忽略页
        边带 —— 条件三段式的"是否阻塞"判定只认 outline/车道冲突（页边带
        是软约束，避免 WIRE 段数过度增长）；``_three_stage_stub`` 内部仍
        检查页边带（折线路径本身不进带）。
        """
        for w in direct:
            for (ox0, oy0, ox1, oy1) in outlines:
                if self._segment_intersects(w, ox0, oy0, ox1, oy1):
                    return True
            if w.is_horizontal and self._lane_conflict(
                w.y1, min(w.x1, w.x2), max(w.x1, w.x2), busy_h,
            ):
                return True
            if w.is_vertical and self._lane_conflict(
                w.x1, min(w.y1, w.y2), max(w.y1, w.y2), busy_v,
            ):
                return True
        final = direct[-1]
        if check_page_band and self._segment_in_page_band(
            final, self._edge_clearance_cfg(),
        ):
            return True
        return False

    def _jog_clear(
        self,
        jx: int, jy: int,
        ex: int, ey: int,
        trunk: int,
        vertical: bool,
        outlines: list,
        busy_h: list,
        busy_v: list,
    ) -> bool:
        """折线候选 (E→J, J→T') 是否空闲（不穿 outline/占用车道/页边）。

        Phase XXII D2 增强：**E→J 段与 J→T' 段都检查 outline** —— 旧版
        只查 J→T' 段，E→J 段（垂直于 stub 方向）可能穿过元件体。
        """
        if vertical:  # stub 垂直 → E→J 水平 (ex,ey)→(jx,jy)；J→T' 垂直
            e_j = WireSegment(ex, ey, jx, jy)
            run = WireSegment(jx, jy, jx, trunk)
        else:  # stub 水平 → E→J 垂直 (ex,ey)→(jx,jy)；J→T' 水平
            e_j = WireSegment(ex, ey, jx, jy)
            run = WireSegment(jx, jy, trunk, jy)
        for seg in (e_j, run):
            for (ox0, oy0, ox1, oy1) in outlines:
                if self._segment_intersects(seg, ox0, oy0, ox1, oy1):
                    return False
        if self._segment_in_page_band(run, self._edge_clearance_cfg()):
            return False
        if run.is_horizontal and self._lane_conflict(
            run.y1, min(run.x1, run.x2), max(run.x1, run.x2), busy_h,
        ):
            return False
        if run.is_vertical and self._lane_conflict(
            run.x1, min(run.y1, run.y2), max(run.y1, run.y2), busy_v,
        ):
            return False
        return True

    @staticmethod
    def _segment_in_page_band(w: WireSegment, edge_clearance: int) -> bool:
        """线段是否进入 C 纸边界 ± edge_clearance 带（R5 页边冗余区）。

        C 纸边界：x∈[-10750,-550]、y∈[400,7200]。``edge_clearance=0``
        时永不判定为带内（保持旧行为）。
        """
        if edge_clearance <= 0:
            return False
        if w.is_horizontal:
            y = w.y1
            return y < 400 + edge_clearance or y > 7200 - edge_clearance
        x = w.x1
        return x < -10750 + edge_clearance or x > -550 - edge_clearance

    @staticmethod
    def _clean_pieces(pieces: list[WireSegment]) -> list[WireSegment]:
        """剔除零长段与重复段（顺序保持）。"""
        seen: set[tuple] = set()
        out: list[WireSegment] = []
        for w in pieces:
            if (w.x1, w.y1) == (w.x2, w.y2):
                continue
            key = ((w.x1, w.y1), (w.x2, w.y2))
            rkey = ((w.x2, w.y2), (w.x1, w.y1))
            if key in seen or rkey in seen:
                continue
            seen.add(key)
            out.append(w)
        return out

    @staticmethod
    def _dedupe_wires(wires: list[WireSegment]) -> list[WireSegment]:
        """Drop zero-length segments and merge duplicate pieces globally.

        Two segments are duplicates when they share both endpoints
        (either direction) — overlapping detour/lead paths from
        neighbouring stubs collapse into one.  Used by ``route_nets``
        per net (Phase XXII D1 三段式可能产生同网重复段).

        Args:
            wires: Raw routed segments (may contain zero-length/duplicates).

        Returns:
            Cleaned segment list (order preserved, first occurrence wins).
        """
        return WireLayoutEngine._clean_pieces(wires)

    # ------------------------------------------------------------------
    #  Phase XXII QA 修复（Issue 2）：正交绕障后处理（能力下沉）
    # ------------------------------------------------------------------
    # ``_detour_segment``/``_build_detour`` 原定义于 DetourRouter（Phase XIV
    # P1a）；QA 复核发现 p0 模式三段式在密集页无空闲折线车道时回退直 stub
    # 仍穿元件体 → 把正交绕障后处理下沉到基类，p0 路由后同样绕障。

    def _detour_segment(
        self,
        seg: WireSegment,
        outlines: list[tuple[int, int, int, int]],
        busy_h: list[tuple[int, int, int]] | None = None,
        busy_v: list[tuple[int, int, int]] | None = None,
    ) -> list[WireSegment]:
        """Return the segment, or a detour path when it crosses an outline.

        Only axis-aligned segments can be detoured (orthogonal routing).
        The path keeps both endpoints identical; intermediate detour points
        are snapped to the 25-unit grid and pushed ``max_detour`` units
        outside the outline (L/Z shape).  ``busy_h``/``busy_v`` hold OTHER
        nets' routed segments — the escape lanes are pushed clear of them
        so two nets never share a collinear run (QA Phase XIV Bug 1
        short-circuit).

        Args:
            seg: Original wire segment.
            outlines: Body rectangles to avoid.
            busy_h: Other nets' horizontal segments (y, x0, x1).
            busy_v: Other nets' vertical segments (x, y0, y1).

        Returns:
            ``[seg]`` when clear; otherwise 3-4 segments forming the detour.
        """
        for (ox0, oy0, ox1, oy1) in outlines:
            if self._segment_intersects(seg, ox0, oy0, ox1, oy1):
                return self._build_detour(
                    seg, ox0, oy0, ox1, oy1, busy_h, busy_v,
                )
        return [seg]

    def _build_detour(
        self,
        seg: WireSegment,
        ox0: int, oy0: int, ox1: int, oy1: int,
        busy_h: list[tuple[int, int, int]] | None = None,
        busy_v: list[tuple[int, int, int]] | None = None,
    ) -> list[WireSegment]:
        """Build the 4-segment detour path around a rectangle.

        Path (endpoints preserved)::

            (x1,y1) ─► (x1, y_escape) ─► (detour_x, y_escape)
                   ─► (detour_x, y2)   ─► (x2, y2)

        Degenerate cases are guarded (QA Phase XIV Bug 1):
          * when the source pin sits exactly ``max_detour`` outside the
            outline, ``y_escape == y1`` / ``x_escape == x1`` would produce
            zero-length segments — they are dropped;
          * escape lanes that would sit on ANOTHER net's segment
            (``busy_h``/``busy_v``, closed-interval check) are pushed
            further away so two nets never share a collinear run;
          * if the cleaned path degenerates back to the original segment,
            the original is returned unchanged.
        """
        margin = self._detour_margin()
        x1, y1, x2, y2 = seg.x1, seg.y1, seg.x2, seg.y2
        lo_x, hi_x = (ox0, ox1) if ox0 < ox1 else (ox1, ox0)
        lo_y, hi_y = (oy0, oy1) if oy0 < oy1 else (oy1, oy0)
        busy_h = list(busy_h or ())
        busy_v = list(busy_v or ())

        if seg.is_vertical:
            # Source side: the segment start y tells us which side of the
            # outline the detour must escape toward.
            if y1 < lo_y:
                y_escape = lo_y - margin
            else:
                y_escape = hi_y + margin
            # horizontal jog toward the nearer body edge
            if abs(x1 - lo_x) <= abs(x1 - hi_x):
                detour_x = lo_x - margin
            else:
                detour_x = hi_x + margin
            detour_x = self._snap(detour_x)
            y_escape = self._snap(y_escape)
            # Push the horizontal escape lane off other nets' segments.
            for _ in range(8):
                if self._lane_conflict(
                    y_escape, min(x1, detour_x), max(x1, detour_x), busy_h
                ):
                    y_escape = self._snap(y_escape + margin)
                else:
                    break
            # Push the vertical jog lane off other nets' segments.
            for _ in range(8):
                if self._lane_conflict(
                    detour_x, min(y_escape, y2), max(y_escape, y2), busy_v
                ):
                    detour_x = self._snap(
                        detour_x + (margin if detour_x > x1 else -margin)
                    )
                else:
                    break
            candidates = [
                WireSegment(x1, y1, x1, y_escape),
                WireSegment(x1, y_escape, detour_x, y_escape),
                WireSegment(detour_x, y_escape, detour_x, y2),
                WireSegment(detour_x, y2, x2, y2),
            ]
        else:  # horizontal segment
            if x1 < lo_x:
                x_escape = lo_x - margin
            else:
                x_escape = hi_x + margin
            if abs(y1 - lo_y) <= abs(y1 - hi_y):
                detour_y = lo_y - margin
            else:
                detour_y = hi_y + margin
            x_escape = self._snap(x_escape)
            detour_y = self._snap(detour_y)
            # Push the vertical escape lane off other nets' segments.
            for _ in range(8):
                if self._lane_conflict(
                    x_escape, min(y1, detour_y), max(y1, detour_y), busy_v
                ):
                    x_escape = self._snap(x_escape + margin)
                else:
                    break
            # Push the horizontal jog lane off other nets' segments.
            for _ in range(8):
                if self._lane_conflict(
                    detour_y, min(x_escape, x2), max(x_escape, x2), busy_h
                ):
                    detour_y = self._snap(
                        detour_y + (margin if detour_y > y1 else -margin)
                    )
                else:
                    break
            candidates = [
                WireSegment(x1, y1, x_escape, y1),
                WireSegment(x_escape, y1, x_escape, detour_y),
                WireSegment(x_escape, detour_y, x2, detour_y),
                WireSegment(x2, detour_y, x2, y2),
            ]

        # Drop zero-length segments and merge duplicate pieces.
        cleaned: list[WireSegment] = []
        seen: set[tuple] = set()
        for w in candidates:
            if (w.x1, w.y1) == (w.x2, w.y2):
                continue  # zero-length (degenerate escape == source)
            key = ((w.x1, w.y1), (w.x2, w.y2))
            rkey = ((w.x2, w.y2), (w.x1, w.y1))
            if key in seen or rkey in seen:
                continue  # duplicate piece
            seen.add(key)
            cleaned.append(w)

        if not cleaned:
            return [seg]
        # Path degenerated back to the original straight segment.
        if len(cleaned) == 1 and (
            cleaned[0].x1, cleaned[0].y1, cleaned[0].x2, cleaned[0].y2
        ) == (x1, y1, x2, y2):
            return [seg]
        return cleaned

    @staticmethod
    def _lane_conflict(
        candidate: int,
        lo: int,
        hi: int,
        busy: list[tuple[int, int, int]],
    ) -> bool:
        """True when ``candidate`` collides with an occupied lane.

        Closed-interval check (same rule as P0 ``_lane_free``): a segment
        whose coordinate is within ``_TOL`` of ``candidate`` AND whose span
        overlaps or touches ``[lo, hi]`` counts as a conflict — two nets
        sharing a collinear run would short in DEHDL.

        Args:
            candidate: Escape-lane coordinate.
            lo/hi: Span of the detour segment along the lane.
            busy: Occupied same-orientation segments ``(value, span_lo,
                span_hi)`` of OTHER nets.

        Returns:
            True when a push is needed.
        """
        for b_val, b_lo, b_hi in busy:
            if abs(b_val - candidate) <= _TOL and max(lo, b_lo) <= min(hi, b_hi):
                return True
        return False

    @staticmethod
    def _segment_intersects(
        seg: WireSegment, ox0: int, oy0: int, ox1: int, oy1: int,
    ) -> bool:
        """True when an axis-aligned segment crosses the rectangle interior.

        A segment touching only the outline edge is NOT a crossing (open
        interval) — pure edge contact does not cut through the body.
        """
        lo_x, hi_x = (ox0, ox1) if ox0 < ox1 else (ox1, ox0)
        lo_y, hi_y = (oy0, oy1) if oy0 < oy1 else (oy1, oy0)
        if seg.is_horizontal:
            if not (lo_y < seg.y1 < hi_y):
                return False
            a, b = (seg.x1, seg.x2) if seg.x1 < seg.x2 else (seg.x2, seg.x1)
            return lo_x < a < hi_x or lo_x < b < hi_x or (a <= lo_x and b >= hi_x)
        if seg.is_vertical:
            if not (lo_x < seg.x1 < hi_x):
                return False
            a, b = (seg.y1, seg.y2) if seg.y1 < seg.y2 else (seg.y2, seg.y1)
            return lo_y < a < hi_y or lo_y < b < hi_y or (a <= lo_y and b >= hi_y)
        return False

    @staticmethod
    def _net_crossing_cost(
        pins: Iterable[tuple[int, int]],
        trunk: int,
        lo: int,
        hi: int,
        outlines: Iterable[tuple[float, float, float, float]],
        vertical: bool,
    ) -> int:
        """候选 trunk 车道的总穿体成本（trunk 线 + 全部直 stub）。

        Phase XXIII R-2（冲突计数优先）：对候选 trunk 车道，统计
          * trunk 线（沿 trunk 方向 span [lo, hi]）穿过的 outline 数；
          * 每条引脚直 stub（pin → trunk）穿过的 outline 数。
        用作车道选择的成本 —— 选总穿体最少者（stub 端点为直线近似，
        与三段式实际路径相关但计算廉价；仅供车道选择，不影响最终线段）。

        Args:
            pins: 网引脚坐标列表。
            trunk: 候选 trunk 坐标（水平 trunk = y / 垂直 trunk = x）。
            lo/hi: 网沿 trunk 方向的 span（引脚 min/max）。
            outlines: 元件轮廓矩形。
            vertical: True = 水平 trunk（y 固定）；False = 垂直 trunk。

        Returns:
            总穿体成本（0 = 完全避让）。
        """
        outlines = list(outlines)
        cost = 0
        if vertical:
            tseg = WireSegment(int(lo), int(trunk), int(hi), int(trunk))
            for o in outlines:
                if WireLayoutEngine._segment_intersects(tseg, *o):
                    cost += 1
            for (px, py) in pins:
                sseg = WireSegment(int(px), int(py), int(px), int(trunk))
                for o in outlines:
                    if WireLayoutEngine._segment_intersects(sseg, *o):
                        cost += 1
        else:
            tseg = WireSegment(int(trunk), int(lo), int(trunk), int(hi))
            for o in outlines:
                if WireLayoutEngine._segment_intersects(tseg, *o):
                    cost += 1
            for (px, py) in pins:
                sseg = WireSegment(int(px), int(py), int(trunk), int(py))
                for o in outlines:
                    if WireLayoutEngine._segment_intersects(sseg, *o):
                        cost += 1
        return cost

    @staticmethod
    def _push_below(
        coord: int,
        body_outlines: Iterable[tuple[float, float, float, float]],
        vertical: bool,
        edge_clearance: int = 0,
        span: tuple[int, int] | None = None,
    ) -> int:
        """向下推离 trunk 坐标（对称于 ``_avoid_outlines`` 的向上推离）。

        Phase XXIII R-2（冲突计数优先）：车道选择需要同时探索 outline
        上方（``_avoid_outlines``）与下方（本函数）两条避让方向 —— 上方
        车道让下方引脚长 stub 穿体，下方车道让上方引脚长 stub 穿体，
        取总成本低者。

        Args:
            coord: Candidate trunk coordinate.
            body_outlines: Body rectangles.
            vertical: True = horizontal trunk; False = vertical trunk.
            edge_clearance: Page-edge red-zone width.
            span: Trunk span along the trunk direction.

        Returns:
            Adjusted trunk coordinate (pushed below, snapped to grid).
        """
        outlines = list(body_outlines)
        result = coord
        while True:
            conflict = False
            for (ox0, oy0, ox1, oy1) in outlines:
                if vertical:
                    lo_f, hi_f = float(min(oy0, oy1)), float(max(oy0, oy1))
                    if not (lo_f < result < hi_f):
                        continue
                    if span is not None:
                        o_lo, o_hi = float(min(ox0, ox1)), float(max(ox0, ox1))
                        s_lo, s_hi = float(min(span)), float(max(span))
                        if not (o_lo < s_hi and s_lo < o_hi):
                            continue
                    result = int(lo_f) - 50
                    conflict = True
                else:
                    lo_f, hi_f = float(min(ox0, ox1)), float(max(ox0, ox1))
                    if not (lo_f < result < hi_f):
                        continue
                    if span is not None:
                        o_lo, o_hi = float(min(oy0, oy1)), float(max(oy0, oy1))
                        s_lo, s_hi = float(min(span)), float(max(span))
                        if not (o_lo < s_hi and s_lo < o_hi):
                            continue
                    result = int(lo_f) - 50
                    conflict = True
            if not conflict:
                break
        if edge_clearance > 0:
            if vertical:
                lo, hi = _PAGE_Y0 + edge_clearance, _PAGE_Y1 - edge_clearance
            else:
                lo, hi = _PAGE_X0 + edge_clearance, _PAGE_X1 - edge_clearance
            if result < lo:
                result = lo
            elif result > hi:
                result = hi
        return _snap(result)

    def _min_crossing_trunk(
        self,
        current: int,
        median: int,
        pins: list[tuple[int, int]],
        lo: int,
        hi: int,
        used: list[tuple[int, int, int]],
        body_outlines: Iterable[tuple[float, float, float, float]],
        vertical: bool,
        other_by_x: dict[int, list[int]] | None = None,
        other_by_y: dict[int, list[int]] | None = None,
        max_steps: int = 8,
    ) -> int:
        """候选 trunk 车道冲突计数优先（Phase XXIII R-2 T3.1）。

        仅对当前 trunk 总穿体成本 >0 的网触发：以**中位**为中心 ±50..
        ±``max_steps``*50 双向扫描，每个候选同时评估**上方推离**
        （``_avoid_outlines``）与**下方推离**（``_push_below``）两个避让
        方向，选通过 lane-free / pin-on-trunk / 页界检查且
        ``_net_crossing_cost``（trunk + stub 总穿体）最小（同成本取距
        中位最近）的车道；无更优则保持 ``current``（零回归 —— 干净网
        完全不触发，成本不降不改）。

        Args:
            current: ``_find_lane`` 返回的当前 trunk 坐标。
            median: 网中位 trunk 坐标（扫描中心）。
            pins: 网引脚坐标列表。
            lo/hi: 网沿 trunk 方向的 span。
            used: 已占用同向段（lane-free 检查）。
            body_outlines: 元件轮廓。
            vertical: True = 水平 trunk；False = 垂直 trunk。
            other_by_x/other_by_y: 其他网引脚索引（pin-on-trunk 检查）。
            max_steps: 双向扫描层数（每层 ±50）。

        Returns:
            冲突最少的 trunk 坐标（无更优时保持 ``current``）。
        """
        v_min, v_max = (0, 8275) if vertical else (-10750, 0)
        edge_clearance = self._edge_clearance() + (
            50 if getattr(self, "_current_net_gnd", False) else 0
        )
        pin_radius = self._pin_radius()
        outlines = list(body_outlines)
        cur_cost = self._net_crossing_cost(
            pins, current, lo, hi, outlines, vertical,
        )
        if cur_cost == 0:
            return current
        best = current
        best_cost = cur_cost
        best_dist = abs(current - median)

        def _try(final: int) -> None:
            nonlocal best, best_cost, best_dist
            if not (v_min <= final <= v_max):
                return
            if not self._lane_free(final, lo, hi, used):
                return
            if self._pin_on_trunk(
                final, lo, hi, vertical, other_by_x, other_by_y,
                pin_radius=pin_radius,
            ):
                return
            cost = self._net_crossing_cost(
                pins, final, lo, hi, outlines, vertical,
            )
            dist = abs(final - median)
            if cost < best_cost or (cost == best_cost and dist < best_dist):
                best, best_cost, best_dist = final, cost, dist

        # 候选：中位 ±50..±max_steps*50 + 冲突 outline 边（上方 hi+50 /
        # 下方 lo-50）—— 让 trunk 可以跳到元件体外侧（旧 ±窗口可能够不到
        # 密集页的大元件，GND 长 stub 穿体正源于此）。
        candidates: list[int] = [median]
        for k in range(1, max_steps + 1):
            candidates.append(median + k * _LANE)
            candidates.append(median - k * _LANE)
        for (ox0, oy0, ox1, oy1) in outlines:
            if vertical:
                o_lo, o_hi = float(min(ox0, ox1)), float(max(ox0, ox1))
                if not (o_lo < hi and lo < o_hi):
                    continue
                candidates.append(_snap(float(max(oy0, oy1)) + 50))
                candidates.append(_snap(float(min(oy0, oy1)) - 50))
            else:
                o_lo, o_hi = float(min(oy0, oy1)), float(max(oy0, oy1))
                if not (o_lo < hi and lo < o_hi):
                    continue
                candidates.append(_snap(float(max(ox0, ox1)) + 50))
                candidates.append(_snap(float(min(ox0, ox1)) - 50))
        for cand in candidates:
            if not (v_min <= cand <= v_max):
                continue
            _try(self._avoid_outlines(
                cand, outlines, vertical,
                edge_clearance=edge_clearance, span=(lo, hi),
            ))
            _try(self._push_below(
                cand, outlines, vertical,
                edge_clearance=edge_clearance, span=(lo, hi),
            ))
        return best

    @staticmethod
    def _avoid_outlines(
        coord: int,
        body_outlines: Iterable[tuple[float, float, float, float]],
        vertical: bool,
        edge_clearance: int = 0,
        span: tuple[int, int] | None = None,
    ) -> int:
        """Shift a trunk coordinate outside overlapping body outlines.

        Phase XIII T4: loops until the coordinate is outside EVERY
        outline's range (conflict chain), moving +50 each time so a shift
        cannot land inside another body.

        Phase XXIII R-2 (T3.1): 避让算法从"推离首个重叠 outline"升级为
        "推离**所有重叠 outline** 的最大扩展"—— 保持单向 +50（与旧行为
        一致，WIRE 零回归），但按"真穿体"判定（``span`` 提供时：y/x 区间
        含 trunk 坐标 **且** x/y span 与 outline 重叠）—— 不再推离 x 方向
        根本不重叠的远端 outline（旧实现密集页推太远 → 车道被占 → 回退
        直穿，正是 283 条 trunk 穿体根因）。循环直到不与任何 outline
        重叠；无可选坐标（页界截断）时由调用方标记 ``reason=trunk_blocked``。

        Phase XVIII R5：追加页面边界约束 —— trunk 不得进入
        ``C 纸边界 ± edge_clearance`` 带（x∈[-10750,-550]、y∈[400,7200]）；
        冲突则向内侧推 50。``edge_clearance=0`` 保持旧行为（无页边约束）。

        Args:
            coord: Candidate trunk coordinate.
            body_outlines: (min_x,min_y,max_x,max_y) tuples.
            vertical: True when routing a horizontal trunk (y fixed) —
                checks y-ranges; False checks x-ranges.
            edge_clearance: Page-edge red-zone width (0 = disabled).
            span: Trunk span along the trunk direction ``(lo, hi)``；
                None = 仅区间判定（向后兼容旧调用）。

        Returns:
            Adjusted trunk coordinate (min-crossing, nearest), snapped to
            the 25-unit grid.
        """
        outlines = list(body_outlines)
        result = coord
        if outlines:
            # Phase XXIII R-2（T3.1）：span 感知的真穿体判定 —— 只推离
            # trunk 线段**实际穿过**的 outline（y/x 区间含 trunk 坐标且
            # x/y span 与 outline 重叠）。旧实现只查区间（忽略 span）→
            # 密集页把 trunk 推离 x 方向根本不重叠的远端 outline，推太远
            # → 车道被占 → 回退直穿（283 条 trunk 穿体根因）。
            while True:
                conflict = False
                for (ox0, oy0, ox1, oy1) in outlines:
                    if vertical:
                        lo_f, hi_f = float(min(oy0, oy1)), float(max(oy0, oy1))
                        if not (lo_f < result < hi_f):
                            continue
                        if span is not None:
                            o_lo, o_hi = float(min(ox0, ox1)), float(max(ox0, ox1))
                            s_lo, s_hi = float(min(span)), float(max(span))
                            if not (o_lo < s_hi and s_lo < o_hi):
                                continue
                        result = int(hi_f) + 50
                        conflict = True
                    else:
                        lo_f, hi_f = float(min(ox0, ox1)), float(max(ox0, ox1))
                        if not (lo_f < result < hi_f):
                            continue
                        if span is not None:
                            o_lo, o_hi = float(min(oy0, oy1)), float(max(oy0, oy1))
                            s_lo, s_hi = float(min(span)), float(max(span))
                            if not (o_lo < s_hi and s_lo < o_hi):
                                continue
                        result = int(hi_f) + 50
                        conflict = True
                if not conflict:
                    break
        # R5: 页面边缘冗余区 —— 不得进入 C 纸边界 ± edge_clearance 带。
        if edge_clearance > 0:
            if vertical:
                # 水平 trunk（y 固定）：y ∈ [PAGE_Y0+ec, PAGE_Y1-ec]。
                lo, hi = _PAGE_Y0 + edge_clearance, _PAGE_Y1 - edge_clearance
            else:
                lo, hi = _PAGE_X0 + edge_clearance, _PAGE_X1 - edge_clearance
            if result < lo:
                result = lo
            elif result > hi:
                result = hi
        return _snap(result)

    @staticmethod
    def _trunk_crosses_outlines(
        trunk: int,
        lo: int,
        hi: int,
        outlines: Iterable[tuple[float, float, float, float]],
        vertical: bool,
    ) -> bool:
        """True when the trunk line crosses any body outline interior.

        Phase XXIII R-2 (T3.2)：trunk 避让无解回退直穿时，``route_nets``
        用它标记 ``reason=trunk_blocked``（与 ``_segment_intersects`` 同
        语义：端点贴边不算穿体）。

        Args:
            trunk: Final trunk coordinate (y for horizontal / x for vertical).
            lo/hi: Net span along the trunk direction (pin min/max).
            outlines: Body rectangles.
            vertical: True = horizontal trunk (y fixed); False = vertical.

        Returns:
            True when any outline interior contains part of the trunk line.
        """
        outlines = list(outlines)
        if vertical:
            seg = WireSegment(int(lo), int(trunk), int(hi), int(trunk))
        else:
            seg = WireSegment(int(trunk), int(lo), int(trunk), int(hi))
        return any(
            WireLayoutEngine._segment_intersects(seg, ox0, oy0, ox1, oy1)
            for (ox0, oy0, ox1, oy1) in outlines
        )

    @staticmethod
    def _coords(pins: Iterable) -> list[tuple[int, int]]:
        """Normalize net pin entries to (x, y) tuples.

        Accepts either plain coordinate tuples or pin dicts carrying a
        ``"coord"`` key (the csa_writer net_pin_map format).
        """
        out: list[tuple[int, int]] = []
        for p in pins:
            if isinstance(p, dict):
                out.append(tuple(p["coord"]))
            else:
                out.append(tuple(p))
        return out

    @staticmethod
    def wires_through_bodies(
        wires: Iterable["WireSegment"],
        body_outlines: Iterable[tuple[int, int, int, int]],
    ) -> list[tuple[tuple[int, int, int, int], tuple[int, int, int, int]]]:
        """List wire segments passing through a body outline interior.

        Phase XXI I（用户 Cadence 16.6 实测 P19"电线穿芯片/元件"）：P0
        trunk 已避让 outline（Phase XIII T4），但 pin→trunk 的 stub 直线
        段对**框内引脚**（真实库元件，引脚在体轮廓内）可能穿过元件体。
        本函数统计穿体线段（端点落在 outline 边界上不算穿体；只有段内部
        深入轮廓内才算），供 aesthetic_report [WIRE_THROUGH_BODY] 记录。

        Args:
            wires: Routed wire segments.
            body_outlines: (x0, y0, x1, y1) body rectangles.

        Returns:
            ``[(seg, body)]`` 穿体对清单（seg 为四元组）。
        """
        outlines: list[tuple[int, int, int, int]] = []
        for o in body_outlines:
            x0, y0, x1, y1 = (int(v) for v in o)
            outlines.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
        out: list[tuple[tuple[int, int, int, int], tuple[int, int, int, int]]] = []
        for w in wires:
            x1, y1, x2, y2 = int(w.x1), int(w.y1), int(w.x2), int(w.y2)
            seg = (x1, y1, x2, y2)
            for (ox0, oy0, ox1, oy1) in outlines:
                # 线段是否**内部**穿过矩形（端点恰在边界上不算）。
                if x1 == x2:  # vertical
                    if not (ox0 < x1 < ox1):
                        continue
                    lo, hi = min(y1, y2), max(y1, y2)
                    if lo < oy1 and hi > oy0 and not (lo == oy0 and hi == oy1):
                        out.append((seg, (ox0, oy0, ox1, oy1)))
                elif y1 == y2:  # horizontal
                    if not (oy0 < y1 < oy1):
                        continue
                    lo, hi = min(x1, x2), max(x1, x2)
                    if lo < ox1 and hi > ox0 and not (lo == ox0 and hi == ox1):
                        out.append((seg, (ox0, oy0, ox1, oy1)))
        return out

    # ------------------------------------------------------------------
    #  DOT computation
    # ------------------------------------------------------------------

    def compute_dots(self, wires: list[WireSegment]) -> list[tuple[int, int]]:
        """Find every junction where >= 2 wire segments meet.

        Conservative rule (system_design.md B.4.5): DOT at every point that
        is an endpoint shared by two or more segments, or an endpoint of one
        segment lying on the interior of another.  Extra DOTs are harmless;
        missing DOTs break connectivity in Cadence.

        Args:
            wires: Routed segments.

        Returns:
            List of (x, y) DOT coordinates (deduplicated).
        """
        dots: Counter[tuple[int, int]] = Counter()
        endpoints: list[tuple[int, int]] = []
        for w in wires:
            endpoints.append((w.x1, w.y1))
            endpoints.append((w.x2, w.y2))

        # 1. Shared endpoints
        for pt, count in Counter(endpoints).items():
            if count >= 2:
                dots[pt] += 1

        # 2. Endpoint lying on the interior of another segment
        for pt in set(endpoints):
            for w in wires:
                if pt in ((w.x1, w.y1), (w.x2, w.y2)):
                    continue
                if self._point_on_segment(pt, w):
                    dots[pt] += 1

        return list(dots.keys())

    @staticmethod
    def _point_on_segment(pt: tuple[int, int], w: WireSegment) -> bool:
        """True when pt lies on the (axis-aligned) segment w, exclusive of ends."""
        x, y = pt
        if w.is_horizontal:
            if y != w.y1:
                return False
            lo, hi = (w.x1, w.x2) if w.x1 < w.x2 else (w.x2, w.x1)
            return lo < x < hi
        if w.is_vertical:
            if x != w.x1:
                return False
            lo, hi = (w.y1, w.y2) if w.y1 < w.y2 else (w.y2, w.y1)
            return lo < y < hi
        return False


#: ``"p0"`` 别名 → WireLayoutEngine（routing.mode 默认值即 "p0"，
#: 直接映射到默认车道法，避免 create_router 的 unknown-mode 告警）。
ROUTER_REGISTRY.setdefault("p0", WireLayoutEngine)
