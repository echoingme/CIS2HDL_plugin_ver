"""LayoutMapper — CIS 坐标到 HDL 网格映射器（B1.16）。

使用 ConvertDocToUser 公式：
    用户坐标 = 文档坐标 × (1.0 / 物理粒度)

参考：
    - ORCAD_SOURCE_ANALYSIS.md §10.2 + §13.2
    - BACKEND_DESIGN.md §5.2
"""

from __future__ import annotations


class LayoutMapper:
    """将 CIS 的文档坐标映射到 HDL 的网格坐标系统。

    CIS 使用内部文档坐标（从 DSN 二进制直接读取）。
    HDL 使用用户坐标 + 网格对齐。

    Usage:
        mapper = LayoutMapper()
        hdl_x, hdl_y = mapper.map_position(cis_x, cis_y)
    """

    # CIS to HDL coordinate scale factor
    # DSN 坐标是逻辑单位，HDL 默认使用英寸或自定义网格。
    # 这个因子根据实际 DPI 和 Cadence 物理粒度设定。
    # 从 TCL API 来看：ConvertDocToUser = doc_coord × (1.0 / physical_granularity)
    CIS_TO_HDL_SCALE: float = 1.0

    # HDL 网格间距（像素/单位）
    GRID_SPACING: int = 16

    def __init__(
        self,
        scale: float | None = None,
        grid_spacing: int | None = None,
    ) -> None:
        """初始化布局映射器。

        Args:
            scale: CIS→HDL 缩放因子（None = 默认 1.0）。
            grid_spacing: HDL 网格间距（None = 默认 16）。
        """
        self._scale = scale if scale is not None else self.CIS_TO_HDL_SCALE
        self._grid = grid_spacing if grid_spacing is not None else self.GRID_SPACING

    def map_position(self, cis_x: int, cis_y: int) -> tuple[int, int]:
        """将 CIS 坐标映射到 HDL 网格坐标。

        Args:
            cis_x: CIS X 坐标。
            cis_y: CIS Y 坐标。

        Returns:
            (hdl_x, hdl_y) 对齐到网格的 HDL 坐标。
        """
        hdl_x = int(cis_x * self._scale)
        hdl_y = int(cis_y * self._scale)

        # Snap to grid
        hdl_x = round(hdl_x / self._grid) * self._grid
        hdl_y = round(hdl_y / self._grid) * self._grid

        return hdl_x, hdl_y

    def map_position_raw(self, cis_x: int, cis_y: int) -> tuple[float, float]:
        """原始坐标映射（不做网格对齐）。

        Args:
            cis_x: CIS X 坐标。
            cis_y: CIS Y 坐标。

        Returns:
            (hdl_x, hdl_y) 浮点坐标。
        """
        return cis_x * self._scale, cis_y * self._scale

    def set_scale(self, scale: float) -> None:
        """设置缩放因子。"""
        self._scale = scale

    def set_grid_spacing(self, spacing: int) -> None:
        """设置网格间距。"""
        self._grid = spacing
