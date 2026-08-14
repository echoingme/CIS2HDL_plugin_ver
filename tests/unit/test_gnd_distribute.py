"""Phase XXIII P1-3 — GND 密度补点 + outlet 绕行（ensure_gnd_symbols）。

Covers:
  * `ensure_gnd_symbols`：页面 1/4 分块，每块 ≥3 个 GND 引脚且距最近
    GND 符号 >1500 时补 GND_SYM_B{block}（place_gnd_symbol 既有路径）
  * 密度补点触发 / 不触发（引脚数不足 / 距已有符号近）
  * hub→最近符号曼哈顿距离均值下降 ≥20%（密度改善验收）
  * `hub_to_symbol_wire` outlet→符号段受阻 90° 折线绕行（穿体 0）
  * 全部输出坐标 25 网格
"""

from __future__ import annotations

from cis2hdl.core.writer.gnd_cluster_planner import (
    _seg_intersects_rect,
    ensure_gnd_symbols,
    hub_to_symbol_wire,
)


def _block_top_left_pins():
    """页面 1/4 分块 3（x∈[-10750,-5650], y∈[3800,7200] 左上）的 4 个 GND 引脚。"""
    return [
        (-9200, 6200), (-9000, 6100), (-8800, 6300), (-8600, 6200),
    ]


def _block_top_right_pins():
    """页面 1/4 分块 4（x∈[-5650,-550], y∈[3800,7200] 右上）的 4 个 GND 引脚。"""
    return [
        (-2400, 6200), (-2200, 6100), (-2000, 6300), (-1800, 6200),
    ]


class TestEnsureGndSymbols:
    def test_triggers_when_pins_far_from_symbols(self):
        """块内 ≥3 引脚且无已有符号 → 补 GND_SYM_B3。"""
        symbols = ensure_gnd_symbols(_block_top_left_pins(), [], edge_clearance=100)
        assert len(symbols) == 1
        assert symbols[0]["refdes"] == "GND_SYM_B3"
        assert symbols[0]["x"] % 25 == 0 and symbols[0]["y"] % 25 == 0
        assert symbols[0]["pin_coord"][0] % 25 == 0
        assert symbols[0]["pin_coord"][1] % 25 == 0

    def test_no_trigger_when_few_pins(self):
        """块内引脚 < 3 → 不补点。"""
        pins = [(-9200, 6200), (-9000, 6100)]
        assert ensure_gnd_symbols(pins, [], edge_clearance=100) == []

    def test_no_trigger_when_near_existing_symbol(self):
        """距最近已有符号 ≤1500 → 不补点。"""
        # 块 3 中心 (-8200, 5500)；最近引脚 (-8800,6000) 距它 1100 ≤ 1500。
        existing = [(-8200, 5500)]
        assert ensure_gnd_symbols(_block_top_left_pins(), existing, edge_clearance=100) == []

    def test_trigger_both_blocks(self):
        """两个分块都满足条件 → 各补 1 个符号。"""
        symbols = ensure_gnd_symbols(
            _block_top_left_pins() + _block_top_right_pins(), [],
            edge_clearance=100,
        )
        refdeses = {s["refdes"] for s in symbols}
        assert refdeses == {"GND_SYM_B3", "GND_SYM_B4"}

    def test_symbol_avoids_outlines(self):
        """补点符号不落元件 outline（place_gnd_symbol 避让路径）。"""
        # 块 3 中心 (-8200,5500) 被 outline 覆盖 → 符号被推出。
        outlines = [(-8300, 5400, -8100, 5600)]
        symbols = ensure_gnd_symbols(
            _block_top_left_pins(), [], outlines=outlines,
            margin=50, edge_clearance=100,
        )
        assert len(symbols) == 1
        x, y = symbols[0]["x"], symbols[0]["y"]
        assert not (-8300 - 50 <= x <= -8100 + 50 and 5400 - 50 <= y <= 5600 + 50)

    def test_empty_input(self):
        assert ensure_gnd_symbols([], []) == []


class TestHubDistanceImprovement:
    def test_mean_hub_distance_drops_ge_20_percent(self):
        """补点后 hub→最近符号曼哈顿距离均值下降 ≥20%（验收口径）。"""
        pins = _block_top_left_pins() + _block_top_right_pins()
        # 已有 1 个远端符号（页角）。
        far_symbol = [(-10000, 600)]
        # 补点前：每块 hub → 最近符号距离。
        hub_before = []
        for group in (_block_top_left_pins(), _block_top_right_pins()):
            hx = sum(p[0] for p in group) // len(group)
            hy = sum(p[1] for p in group) // len(group)
            hub_before.append(
                min(abs(hx - s[0]) + abs(hy - s[1]) for s in far_symbol)
            )
        mean_before = sum(hub_before) / len(hub_before)

        symbols = ensure_gnd_symbols(
            pins, far_symbol, edge_clearance=100,
        )
        assert len(symbols) == 2  # 两个分块都补点
        all_pins = [tuple(s["pin_coord"]) for s in symbols] + far_symbol
        hub_after = []
        for group in (_block_top_left_pins(), _block_top_right_pins()):
            hx = sum(p[0] for p in group) // len(group)
            hy = sum(p[1] for p in group) // len(group)
            hub_after.append(
                min(abs(hx - s[0]) + abs(hy - s[1]) for s in all_pins)
            )
        mean_after = sum(hub_after) / len(hub_after)
        assert mean_after < mean_before * 0.8, (
            f"hub distance mean {mean_before} → {mean_after} "
            f"(需下降 ≥20%)"
        )


class TestOutletAvoidance:
    def test_outlet_wire_avoids_body_zero_crossing(self):
        """outlet→符号段受阻（两条 L 都穿 outline）→ 90° 折线绕行，穿体 0。"""
        hub = (-2900, 5000)
        symbol_pin = (-2400, 5200)
        outlines = [
            (-2600, 4950, -2500, 5050),   # 挡 L1（corner=(sx,hy) 水平段）
            (-2850, 5150, -2450, 5250),   # 挡 L2（corner=(hx,sy) 水平段）
        ]
        segs = hub_to_symbol_wire(hub, symbol_pin, outlines=outlines)
        assert len(segs) >= 3  # Z 路径（≤2 次折弯）
        # 端点保持。
        assert segs[0][:2] == hub
        assert segs[-1][2:] == symbol_pin
        # 穿体 0（outline 内部穿透判定与 _seg_intersects_rect 同语义）。
        for s in segs:
            for o in outlines:
                assert not _seg_intersects_rect(s, o), (
                    f"outlet 段 {s} 穿 outline {o}"
                )
        # 全 25 网格。
        for s in segs:
            for v in s:
                assert v % 25 == 0

    def test_outlet_wire_clear_l_unchanged(self):
        """通畅 L 路径保持 1-2 段直连（零回归）。"""
        segs = hub_to_symbol_wire((-2900, 5000), (-2400, 5200))
        assert 1 <= len(segs) <= 2
        assert segs[0][:2] == (-2900, 5000)
        assert segs[-1][2:] == (-2400, 5200)
