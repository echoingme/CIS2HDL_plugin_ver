"""Phase XVII R2：net_order 布线顺序测试（短网先布 vs 长网先布）。"""

from __future__ import annotations

import pytest

from cis2hdl.core.writer.wire_layout import _net_priority_key


class TestNetPriorityKey:
    """_net_priority_key 排序键行为（SKiDL rank_net 思想落地）。"""

    def test_long_first_returns_span_positive(self):
        """long_first：返回 (span, len)，配合 reverse=True = 长网先布。"""
        coords = [(0, 0), (1000, 0)]
        assert _net_priority_key(coords, "long_first") == (1000, 2)

    def test_short_first_returns_negative_span(self):
        """short_first：返回 (-span, -len)，配合 reverse=True = 短网先布。"""
        coords = [(0, 0), (1000, 0)]
        assert _net_priority_key(coords, "short_first") == (-1000, -2)

    def test_long_first_orders_long_first(self):
        """long_first 排序：span 大的网排前面（reverse=True 后）。"""
        short = [(0, 0), (100, 0)]
        long = [(0, 0), (5000, 0)]
        key_short = _net_priority_key(short, "long_first")
        key_long = _net_priority_key(long, "long_first")
        # reverse=True 时 key 大的先布 → long 应先
        assert key_long > key_short

    def test_short_first_orders_short_first(self):
        """short_first 排序：span 小的网排前面（负号键 + reverse=True）。"""
        short = [(0, 0), (100, 0)]
        long = [(0, 0), (5000, 0)]
        key_short = _net_priority_key(short, "short_first")
        key_long = _net_priority_key(long, "short_first")
        # reverse=True 时 key 大的先布；short_first 下 short 的 key 更大
        assert key_short > key_long

    def test_single_pin_zero_key(self):
        """单引脚网返回 (0,0)，不会被优先。"""
        assert _net_priority_key([(5, 5)], "long_first") == (0, 0)
        assert _net_priority_key([(5, 5)], "short_first") == (0, 0)

    def test_span_is_manhattan(self):
        """span = (max_x-min_x) + (max_y-min_y)，曼哈顿跨度。"""
        coords = [(0, 0), (300, 400)]
        assert _net_priority_key(coords, "long_first") == (700, 2)

    def test_pin_count_secondary_key(self):
        """同 span 时按引脚数排序（长网先布 = 引脚多者先）。"""
        a = [(0, 0), (100, 0)]
        b = [(0, 0), (100, 0), (100, 50)]
        assert _net_priority_key(a, "long_first")[1] < _net_priority_key(b, "long_first")[1]
