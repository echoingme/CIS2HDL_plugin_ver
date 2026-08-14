"""Phase XVII R2：非均匀轨道（_collect_tracks）测试。

SKiDL ``create_routing_tracks`` 思想（元件 bbox 边坐标 → 轨道候选）：
同列/同行元件自然共线对齐。验证轨道收集与 _find_lane 轨道优先行为。
"""

from __future__ import annotations

import pytest

from cis2hdl.core.writer.wire_layout import WireLayoutEngine


class TestCollectTracks:
    """_collect_tracks：从元件 outline 边坐标收集非均匀轨道。"""

    def setup_method(self):
        self.engine = WireLayoutEngine()

    def test_horizontal_tracks_from_outline_edges(self):
        """水平 trunk（y 固定）：轨道 = 各 outline 的 min_y/max_y。"""
        outlines = [(0, 100, 200, 300)]  # min_y=100, max_y=300
        tracks = self.engine._collect_tracks(outlines, vertical=True)
        assert 100 in tracks
        assert 300 in tracks

    def test_vertical_tracks_from_outline_edges(self):
        """垂直 trunk（x 固定）：轨道 = 各 outline 的 min_x/max_x。"""
        outlines = [(0, 100, 200, 300)]  # min_x=0, max_x=200
        tracks = self.engine._collect_tracks(outlines, vertical=False)
        assert 0 in tracks
        assert 200 in tracks

    def test_multiple_outlines_dedup_and_sort(self):
        """多 outline 去重 + 排序。"""
        outlines = [(0, 100, 200, 300), (0, 100, 400, 500), (50, 300, 150, 400)]
        tracks = self.engine._collect_tracks(outlines, vertical=True)
        # min_y/max_y: 100,300 / 100,500 / 300,400 → 去重排序
        assert tracks == sorted(set([100, 300, 500, 400]))
        assert tracks == [100, 300, 400, 500]

    def test_empty_outlines_empty_tracks(self):
        """无 outline → 空轨道列表（回退均匀车道）。"""
        assert self.engine._collect_tracks([], vertical=True) == []
        assert self.engine._collect_tracks([], vertical=False) == []

    def test_tracks_snapped_to_grid(self):
        """轨道坐标吸 25 网格。"""
        outlines = [(3, 102, 197, 303)]
        tracks = self.engine._collect_tracks(outlines, vertical=True)
        assert all(t % 25 == 0 for t in tracks)

    def test_find_lane_prefers_tracks(self):
        """tracks 非空时 _find_lane 优先在轨道上找车道。

        轨道坐标 300 空闲时，trunk 中位 275 应被拉到 300（最近轨道）。
        """
        outlines = [(0, 100, 200, 300)]
        tracks = self.engine._collect_tracks(outlines, vertical=True)  # [100, 300]
        lane = self.engine._find_lane(
            trunk=275,
            lo=0,
            hi=500,
            used=[],
            body_outlines=[],
            vertical=True,
            tracks=tracks,
        )
        # 最近的轨道是 300（|300-275|=25 < |100-275|=175）
        assert lane == 300

    def test_find_lane_tracks_avoid_busy(self):
        """轨道被占用时尝试 ±50 层。"""
        outlines = [(0, 100, 200, 300)]
        tracks = self.engine._collect_tracks(outlines, vertical=True)  # [100, 300]
        # 300 被占用（span 覆盖），应尝试 350（+50）
        lane = self.engine._find_lane(
            trunk=275,
            lo=0,
            hi=500,
            used=[(300, 0, 500)],
            body_outlines=[],
            vertical=True,
            tracks=tracks,
        )
        assert lane == 350

    def test_find_lane_falls_back_without_tracks(self):
        """tracks=None 回退均匀车道（Phase XIII 原行为）。"""
        lane = self.engine._find_lane(
            trunk=275,
            lo=0,
            hi=500,
            used=[],
            body_outlines=[],
            vertical=True,
            tracks=None,
        )
        assert lane == 275
