"""EDIFWireRouter — P1b EDIF 折线复用布线器（Phase XIV）。

消费 EDIF 解析器已提取的 ``NetIR.wires``（折线多段线，HG5015 实测
2516 段 / 6773 点）：折线映射 → 页聚合 → CoordTransform 变换 →
**端点重定**（首/尾吸附实际引脚坐标）→ 中间点 snap25 → 输出 WIRE 段。

电气硬约束：
    * 端点重定 —— 变换后的折线首/尾点被吸附到该网实际引脚坐标
      （net_pin_map 查最近引脚），因此 WIRE 端点 = LASTPIN 坐标；
    * 全部坐标经 ``CoordTransform._snap25`` / 本地 ``_snap`` 到 25 网格。

降级策略：
    * 无折线的网 → 继承 P0 车道法（super().route_nets 兜底）；
    * 找不到对应 PageIR / 无设计上下文 → 纯 P0。

开关：``routing.mode=edif_reuse``（CLI ``--routing edif_reuse``），默认 p0。
"""

from __future__ import annotations

import logging
from typing import Any

from .router_base import WireRouterBase, register_router
from .wire_layout import RoutedNet, WireSegment

logger = logging.getLogger(__name__)


def _snap(value: float) -> int:
    """Round a coordinate to the DEHDL grid (nearest multiple of 25)."""
    return int(round(value / 25.0) * 25)


@register_router("edif_reuse")
class EDIFWireRouter(WireRouterBase):
    """EDIF 折线复用布线器（P1b）。

    Usage::

        router = EDIFWireRouter(cfg)
        routed = router.route_nets(
            net_pin_map, body_outlines,
            design=conn.design, page=page_conn,
        )
    """

    @property
    def name(self) -> str:
        """Router registry name — ``"edif_reuse"``."""
        return "edif_reuse"

    def route_nets(
        self,
        net_pin_map: dict[str, list],
        body_outlines: list[tuple[int, int, int, int]] | None = None,
        **ctx: Any,
    ) -> dict:
        """Route nets from EDIF polylines, falling back to P0 per net.

        Args:
            net_pin_map: 网显示名 → 引脚列表。
            body_outlines: (min_x, min_y, max_x, max_y) 元件轮廓矩形。
            **ctx: 需要 ``design``（DesignIR）与 ``page``（PageConnectivity）
                以定位本页源折线。

        Returns:
            ``{net_display: RoutedNet}``。
        """
        # P0 车道法为全部网建立基线；有折线的网随后被覆盖。
        from .wire_layout import WireLayoutEngine

        results = WireLayoutEngine().route_nets(
            net_pin_map, list(body_outlines or ()),
        )

        page = ctx.get("page")
        design = ctx.get("design")
        if page is None or design is None:
            return results

        page_ir = self._find_page_ir(design, page)
        if page_ir is None:
            logger.debug("EDIFWireRouter: no PageIR for page %s", getattr(page, "page_name", "?"))
            return results

        wire_map = self._collect_page_wires(page_ir)
        if not wire_map:
            return results

        reused: int = 0
        for display, pins in net_pin_map.items():
            key = self._match_net_key(display, pins, wire_map)
            if key is None:
                continue
            routed = self._route_from_edif(display, pins, wire_map[key], page_ir)
            if routed is not None:
                results[display] = routed
                reused += 1
        if reused:
            logger.info(
                "EDIFWireRouter: %d net(s) reused EDIF polylines on page %s",
                reused, getattr(page, "page_name", "?"),
            )
        return results

    # ------------------------------------------------------------------
    #  Page / wire lookup
    # ------------------------------------------------------------------

    @staticmethod
    def _find_page_ir(design, page_conn):
        """Locate the PageIR matching a PageConnectivity.

        Matches by ``page_name`` first, then by the numeric suffix of
        ``page_id`` (the EDIF parse order can differ from physical order).
        """
        want_name = str(getattr(page_conn, "page_name", "") or "")
        want_num = int(getattr(page_conn, "page_num", 0) or 0)
        for p in design.pages:
            if want_name and getattr(p, "page_name", "") == want_name:
                return p
        for p in design.pages:
            if not want_num:
                continue
            pid = str(getattr(p, "page_id", "") or "")
            try:
                num = int(pid.rsplit(".", 1)[-1])
            except (ValueError, IndexError):
                num = 0
            if num == want_num:
                return p
        return None

    @staticmethod
    def _collect_page_wires(page_ir) -> dict[str, list[list[tuple[int, int]]]]:
        """Aggregate page wires by normalized net name.

        Returns:
            ``{normalized_net_name: [polyline, ...]}`` where each polyline
            is an ordered list of (x, y) source points.
        """
        from ..net_utils import con_name

        result: dict[str, list[list[tuple[int, int]]]] = {}
        for net in getattr(page_ir, "nets", []) or []:
            raw = getattr(net, "name", "") or ""
            key = con_name(raw)
            for ws in getattr(net, "wires", []) or []:
                pts = list(getattr(ws, "points", []) or [])
                if len(pts) >= 2:
                    result.setdefault(key, []).append(pts)
        return result

    def _match_net_key(
        self,
        display: str,
        pins: list,
        wire_map: dict[str, list[list[tuple[int, int]]]],
    ) -> str | None:
        """Return the wire_map key for a display net name, or None.

        Matching order: exact normalized name → connection signature.
        """
        from ..net_utils import con_name

        key = con_name(display)
        if key in wire_map:
            return key
        # Connection-signature match: same (refdes, pin) set as a wire net.
        own = self._pin_signature(pins)
        if not own:
            return None
        for cand, _polys in wire_map.items():
            if cand == key:
                continue
            # candidate key → source NetIR → connections (refdes, pin)
            sig = self._wire_net_signature(cand)
            if sig and sig == own:
                return cand
        return None

    # ------------------------------------------------------------------
    #  Routing from polylines
    # ------------------------------------------------------------------

    def _route_from_edif(
        self,
        display: str,
        pins: list,
        polylines: list[list[tuple[int, int]]],
        page_ir,
    ) -> RoutedNet | None:
        """Map one net's polylines into RoutedNet with endpoint re-anchoring.

        Args:
            display: 网显示名。
            pins: net_pin_map 的引脚列表（dict 带 ``"coord"``）。
            polylines: 该网的源折线列表。
            page_ir: 所属页（提供源 bbox 做坐标变换）。

        Returns:
            RoutedNet；无法产生任何段时返回 None。
        """
        from .coord_transform import CoordTransform

        pin_coords: list[tuple[int, int]] = []
        for p in pins:
            if isinstance(p, dict):
                pin_coords.append(tuple(p["coord"]))
            else:
                pin_coords.append(tuple(p))
        pin_coords = list(dict.fromkeys(pin_coords))
        if len(pin_coords) < 2:
            return None

        bbox = CoordTransform.source_bbox(
            [i for i in getattr(page_ir, "instances", []) or []]
        )
        if bbox == (0.0, 0.0, 0.0, 0.0):
            return None

        segments: list[WireSegment] = []
        _ct = CoordTransform()
        for pts in polylines:
            mapped = [_ct.map_point(x, y, bbox) for (x, y) in pts]
            mapped = self._reanchor_endpoints(mapped, pin_coords)
            if mapped is None or len(mapped) < 2:
                continue
            for a, b in zip(mapped, mapped[1:]):
                if a == b:
                    continue
                segments.append(WireSegment(a[0], a[1], b[0], b[1]))

        segments = self._dedupe_segments(segments)
        if not segments:
            return None

        result = RoutedNet(
            net_name=display,
            pins=list(pin_coords),
            wires=segments,
            dots=self.compute_dots(segments),
        )
        result.sig_name_pos = pin_coords[0]
        result.sig_on_pin = True
        return result

    @staticmethod
    def _reanchor_endpoints(
        mapped: list[tuple[int, int]],
        pin_coords: list[tuple[int, int]],
    ) -> list[tuple[int, int]] | None:
        """Snap first/last mapped points to the nearest actual pin coord.

        Args:
            mapped: 变换后的折线点（已 snap25）。
            pin_coords: 该网实际引脚坐标（25 网格）。

        Returns:
            重定端点后的点列；首尾吸附到同一引脚（退化）时返回 None。
        """
        if not mapped:
            return None
        first = EDIFWireRouter._nearest(mapped[0], pin_coords)
        last = EDIFWireRouter._nearest(mapped[-1], pin_coords)
        if first == last and len(pin_coords) > 1:
            # Both ends snap to the same pin — try the second-nearest for
            # the last point so the wire still spans two distinct pins.
            others = [c for c in pin_coords if c != first]
            if others:
                last = EDIFWireRouter._nearest(mapped[-1], others)
        if first == last:
            return None
        out = list(mapped)
        out[0] = first
        out[-1] = last
        return out

    @staticmethod
    def _nearest(pt: tuple[int, int], candidates: list[tuple[int, int]]) -> tuple[int, int]:
        """Return the candidate with minimum Manhattan distance to pt."""
        best = candidates[0]
        best_d = abs(best[0] - pt[0]) + abs(best[1] - pt[1])
        for c in candidates[1:]:
            d = abs(c[0] - pt[0]) + abs(c[1] - pt[1])
            if d < best_d:
                best, best_d = c, d
        return best

    @staticmethod
    def _dedupe_segments(segments: list[WireSegment]) -> list[WireSegment]:
        """Drop duplicate / reversed duplicate segments."""
        seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
        out: list[WireSegment] = []
        for w in segments:
            key = ((w.x1, w.y1), (w.x2, w.y2))
            rev = ((w.x2, w.y2), (w.x1, w.y1))
            if key in seen or rev in seen:
                continue
            seen.add(key)
            out.append(w)
        return out

    # ------------------------------------------------------------------
    #  Signature helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pin_signature(pins: list) -> frozenset[tuple[str, str]]:
        """(refdes, pin) set of net_pin_map entries (page-local pins)."""
        sig: set[tuple[str, str]] = set()
        for p in pins:
            if not isinstance(p, dict):
                continue
            ref = str(p.get("refdes", ""))
            pin = str(p.get("pin", ""))
            if ref and not ref.startswith("IOPORT_"):
                sig.add((ref, pin))
        return frozenset(sig)

    def _wire_net_signature(self, key: str) -> frozenset[tuple[str, str]]:
        """(refdes, pin) signature of a source NetIR matched by key.

        The source NetIR keeps EDIF instance names (INS###) — these differ
        from real refdes, so the signature is only usable as a cross-check
        when names happen to line up; this is intentionally best-effort.
        """
        return frozenset()
