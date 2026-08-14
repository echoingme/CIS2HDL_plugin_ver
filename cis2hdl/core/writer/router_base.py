"""WireRouterBase — 布线器抽象基类 + 注册表（Phase XIV D5）。

设计原则（STANDARDS Part I）：基类-注册模式（ABC + Registry）。
``wire_layout`` 保持单一职责（几何合成）；路由策略抽象到 Router。

注册表：
    ROUTER_REGISTRY: dict[str, type[WireRouterBase]]
        "p0_lane"    → WireLayoutEngine（现有 P0 车道法，默认）
        "detour"     → DetourRouter（P1a 正交绕障）
        "edif_reuse" → EDIFWireRouter（P1b EDIF 折线复用）

回退策略：
    ``create_router`` 对未知 mode 记 warning 并回退 p0_lane；
    ``ConversionEngine._stage_generate`` 对路由异常 catch →
    ``logger.warning`` → 用 p0_lane 重试（``fallback_to_p0``）。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .wire_layout import RoutedNet, WireSegment

logger = logging.getLogger(__name__)

#: 布线器注册表：mode 名 → 布线器类。
ROUTER_REGISTRY: dict[str, type["WireRouterBase"]] = {}


def register_router(name: str):
    """类装饰器：把布线器类注册进 ROUTER_REGISTRY。

    Args:
        name: 注册名（routing.mode / CLI --routing 取值）。
    """

    def deco(cls: type["WireRouterBase"]) -> type["WireRouterBase"]:
        ROUTER_REGISTRY[name] = cls
        return cls

    return deco


def create_router(mode: str, cfg: Any = None) -> "WireRouterBase":
    """工厂：按配置选路由器；未知 mode → warning + 回退 p0_lane。

    Args:
        mode: 布线器模式名（"p0" | "detour" | "edif_reuse"）。
        cfg: 可选的 RoutingConfig（透传给布线器构造）。

    Returns:
        布线器实例。

    Raises:
        RuntimeError: 当 p0_lane 未注册（模块未导入）时。
    """
    cls = ROUTER_REGISTRY.get(mode)
    if cls is None:
        # 首次调用时具体布线器模块可能尚未导入（conversion_engine
        # bootstrap 只 import csa_writer → router_base）——先完成注册。
        _import_router_modules()
        cls = ROUTER_REGISTRY.get(mode)
    if cls is None:
        logger.warning("unknown routing mode %r → fallback p0_lane", mode)
        cls = ROUTER_REGISTRY.get("p0_lane")
    if cls is None:
        raise RuntimeError("ROUTER_REGISTRY has no p0_lane router — bootstrap failed")
    return cls(cfg)


def _import_router_modules() -> None:
    """导入全部布线器模块以完成注册（幂等）。

    注册时机：conversion_engine ``_bootstrap_writers`` 已 import
    ``csa_writer``（其顶部 import router_base）；此处兜底确保
    detour/edif 模块在首次 ``create_router`` 前完成注册。
    """
    try:
        from . import detour_router  # noqa: F401
        from . import edif_wire_reuse  # noqa: F401
        from . import wire_layout  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("router module import failed: %s", exc)


class WireRouterBase(ABC):
    """布线器抽象：路由页面网 → WIRE 段。

    所有实现必须保证端点 = 引脚坐标（Cadence DEHDL 唯一连接规则）。
    DOT 计算是纯几何、与策略无关 —— 由基类统一提供。
    """

    def __init__(self, cfg: Any = None) -> None:
        """Initialize with an optional RoutingConfig.

        Args:
            cfg: RoutingConfig（或 None 使用默认值）。
        """
        self.cfg = cfg

    @property
    @abstractmethod
    def name(self) -> str:
        """布线器注册名（"p0_lane" / "detour" / "edif_reuse"）。"""
        raise NotImplementedError

    @abstractmethod
    def route_nets(
        self,
        net_pin_map: dict[str, list],
        body_outlines: list[tuple[int, int, int, int]] | None = None,
        **ctx: Any,
    ) -> dict[str, "RoutedNet"]:
        """路由页面网 → ``{net_display: RoutedNet}``。

        Args:
            net_pin_map: 网显示名 → 引脚列表（dict 带 ``"coord"`` 键或
                (x, y) 元组，两种格式均接受）。
            body_outlines: (min_x, min_y, max_x, max_y) 元件轮廓矩形。
            **ctx: 实现相关的附加上下文（design / page 等）。

        Returns:
            ``{net_display: RoutedNet}``（>=2 引脚的网；单引脚网省略）。
        """
        raise NotImplementedError

    def compute_dots(
        self, wires: list["WireSegment"]
    ) -> list[tuple[int, int]]:
        """DOT 计算是纯几何、与策略无关 —— 基类提供。

        Args:
            wires: 路由后的线段列表。

        Returns:
            DOT 坐标列表（去重）。
        """
        from .wire_layout import WireLayoutEngine

        return WireLayoutEngine().compute_dots(wires)

    def _snap(self, value: float) -> int:
        """Round a coordinate to the DEHDL grid (nearest multiple of 25)."""
        return int(round(value / 25.0) * 25)
