"""DetourRouter — P1a 正交绕障 + stub 引出段布线器（Phase XIV/XV/XXII）。

继承 P0 车道法（WireLayoutEngine），追加：
1. stub 正交绕障：当一个 WIRE 段与元件 body_outline 相交时，拆成 L/Z
   形多段，绕行点取 outline 外最近 50 倍数（天然 25 网格）；
2. **stub 引出段（Phase XV P1-G）**：每条 stub 从引脚先沿"背离元件
   方向"外引 ``stub_lead``（默认 100）再转向 trunk —— 电线不再贴着
   引脚走；相邻引脚（间距 ≤ ``lead_diff_min_gap``）的引出段错开
   （100/150/200 交替），防并列重叠。

Phase XVIII R5（布线避让增强）：``_three_stage_stub`` ——
"引脚延伸 stub_lead → 最远端向外折线避让 → 再拐弯调头" 三段式，
消除"原地掉头"线头（电线折回压在自己身上）；``routing.three_stage_stub``
（默认 true）开启，可关回退旧直 stub。

Phase XXII D1（Q2 能力下沉）：三段式 stub 的全部纯几何 + cfg 辅助函数
（``_three_stage_stub``/``_try_jog_candidates``/``_stub_direct_blocked``/
``_jog_clear``/``_lead_map``/``_lead_point``/``_stub_lead_cfg`` 等）
**原样下沉到 WireLayoutEngine 基类** —— p0/detour 共用同一实现，
本类不再重复定义；保留 ``route_nets`` 覆写（stash pin_bodies + 绕障
后处理）与 ``_detour_segment``/``_build_detour``。

电气硬约束：
    * 端点不变 —— 每个被拆分的段保持 (x1,y1)/(x2,y2) 两个端点，
      因此引脚坐标（LASTPIN）与 WIRE 端点依然精确重合；
    * 绕行点全部 _snap 到 25 网格（DEHDL SPCOCN-1329 防告警）。

开关：``routing.mode=detour``（CLI ``--routing detour``），或
``--aesthetic``（总开关自动把 mode 置 detour），默认 p0。
异常回退：ConversionEngine catch → logger.warning → p0_lane 重试。
"""

from __future__ import annotations

import logging
from typing import Any

from .router_base import register_router
from .wire_layout import WireLayoutEngine, WireSegment, _TOL

logger = logging.getLogger(__name__)

#: 绕行余量（outline 外推 50 单位 = 2 格，保持 25 网格）——与基类
#: ``_detour_margin`` 默认同源（Phase XXII D1 下沉后由基类提供）。
_DETOUR_MARGIN: int = 50


@register_router("detour")
class DetourRouter(WireLayoutEngine):
    """P0 车道法 + stub 正交绕障（P1a）+ stub 引出段（P1-G）。

    Phase XXII QA 修复（Issue 1）：``CONDITIONAL_THREE_STAGE=False`` ——
    detour 模式保留 P1-G **全部 stub 引出段**（视觉引出）；p0
    （WireLayoutEngine）只对受阻 stub 引出（WIRE 收敛）。

    Usage::

        router = DetourRouter()
        routed = router.route_nets(net_pin_map, body_outlines)
        # 与 WireLayoutEngine.route_nets 同签名；相交段被拆成绕障路径，
        # 每条 stub 带引出段（aesthetic 模式与 p0 明显不同）。
    """

    #: Phase XXII QA 修复（Issue 1）：detour 保留全部 stub 引出（非条件）。
    CONDITIONAL_THREE_STAGE: bool = False

    @property
    def name(self) -> str:
        """Router registry name — ``"detour"``."""
        return "detour"

    def route_nets(
        self,
        net_pin_map: dict[str, list],
        body_outlines: list[tuple[int, int, int, int]] | None = None,
        **ctx: Any,
    ) -> dict:
        """Route nets with P0 lane method + stub leads + detour.

        Args:
            net_pin_map: 网显示名 → 引脚列表。
            body_outlines: (min_x, min_y, max_x, max_y) 元件轮廓矩形。
            **ctx: 透传；``pin_bodies``（可选）为 ``{(px, py): (bx, by)}``
                引脚坐标 → 元件体中心映射，用于决定引出方向。

        Returns:
            ``{net_display: RoutedNet}`` —— 与 P0 相同，但相交段被绕障、
            stub 带引出段。
        """
        outlines: list[tuple[int, int, int, int]] = list(body_outlines or ())
        # Phase XV P1-G: pin → body-center hints (csa_writer provides them).
        self._pin_bodies: dict[tuple[int, int], tuple[int, int]] = dict(
            ctx.get("pin_bodies") or {}
        )
        # Phase XVIII R5: stash outlines so _route_horizontal/_route_vertical
        # (called from the inherited P0 lane builder) can run the three-stage
        # stub with outline avoidance.
        self._three_outlines: list[tuple[int, int, int, int]] = outlines
        results = super().route_nets(net_pin_map, outlines, **ctx)
        if not outlines:
            return results
        detoured: int = 0
        # QA Phase XIV Bug 1 (complete fix): detour escape lanes must also
        # avoid OTHER nets' already-routed segments — otherwise two nets'
        # detour paths collapse onto the same coordinates → DEHDL short.
        done_h: list[tuple[int, int, int]] = []  # (y, x0, x1) of finished nets
        done_v: list[tuple[int, int, int]] = []  # (x, y0, y1) of finished nets
        for routed in results.values():
            new_wires: list[WireSegment] = []
            for w in routed.wires:
                pieces = self._detour_segment(w, outlines, done_h, done_v)
                new_wires.extend(pieces)
                if len(pieces) > 1:
                    detoured += 1
            # 全局去重：同一网内绕障路径的重复段合并（跨网共线已在
            # _build_detour 的 lane 检查避免）。
            routed.wires = self._dedupe_wires(new_wires)
            routed.dots = self.compute_dots(routed.wires)
            # 本网段加入"已占用"，供后续网的绕障避让。
            for w in routed.wires:
                if w.is_horizontal:
                    done_h.append((w.y1, min(w.x1, w.x2), max(w.x1, w.x2)))
                else:
                    done_v.append((w.x1, min(w.y1, w.y2), max(w.y1, w.y2)))
        if detoured:
            logger.info(
                "DetourRouter: %d segment(s) detoured around body outlines", detoured,
            )
        return results

    @staticmethod
    def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
        """Manhattan distance between two points."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

