"""Phase XXII T03 — aes LASTPIN miss 修复（D8，P1-7）。

Covers:
  * 微移引脚（_nudged_pin_keys）豁免：不报 [LASTPIN_MISS]
  * expected 用 _pin_offset_map 同源链：name-bridge 场景不假 miss
  * 非微移引脚仍严格命中校验（不破坏 R3d）
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _writer_with_css():
    """预置 css 偏移缓存的 CSAWriter（模拟 hdl_lib symbol.css）。"""
    from cis2hdl.core.config import RoutingConfig
    from cis2hdl.core.writer.csa_writer import CSAWriter

    w = CSAWriter(routing_cfg=RoutingConfig())
    w._hdl_lib_path = None  # 全部走缓存
    # 关闭 mock_all：让 U1 走"具体符号"分支（否则多引脚芯片一律 mock
    # 图标 → 跳过 LASTPIN 命中校验，测不到 miss 逻辑）。
    w._routing_cfg.temp_lib.mock_all = False
    w._prop_offset_cache["MYIC:1"] = {"1": (-50, 0), "2": (50, 0)}
    w._prop_offset_cache["pinmap:MYIC"] = {}
    w._effective_views["U1"] = (1, 0)
    return w


class _Report:
    """捕获 add_lastpin_miss 调用的桩报告。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add_lastpin_miss(self, **kw) -> None:
        self.calls.append(kw)


def _irec(pins):
    return SimpleNamespace(
        refdes="U1", cell_name="MYIC", cell_id="c1", section=1,
        pins=pins, rotation=0, mirror=0, is_power_symbol=False,
    )


class TestLastpinMissFix:
    def test_nudged_pin_exempt_from_miss(self):
        """微移引脚（key ∈ _nudged_pin_keys）→ 跳过坐标强校验，不报 miss。"""
        w = _writer_with_css()
        # 模拟 Pass 1：U1.2 被 _unique_pin_coord 微移（+25）。
        w._nudged_pin_keys.add("U1.2")
        w._pin_offset_map["U1.1"] = (-50, 0)
        w._pin_offset_map["U1.2"] = (50, 0)
        body = (1000, 1000)
        pin_coords = {"U1.1": (950, 1000), "U1.2": (1075, 1000)}
        report = _Report()
        w._aesthetic_report = report

        pre1 = SimpleNamespace(pin_number="1", pin_name="1", net_id="N1")
        pre2 = SimpleNamespace(pin_number="2", pin_name="2", net_id="N2")
        conn = SimpleNamespace(cells=[])
        page_conn = SimpleNamespace(nets=[])
        lines = w._lastpins_for_instance(
            conn, page_conn, _irec([pre1, pre2]), pin_coords, set(),
            body_coord=body,
        )
        # 两个引脚都不报 miss（微移豁免 + 同源命中）。
        assert report.calls == [], f"unexpected misses: {report.calls}"
        # 微移引脚 U1.2 仍正常发射 LASTPIN $PN。
        assert any(
            "LASTPIN (1075 1000) $PN 2" in ln for ln in lines
        ), "nudged pin LASTPIN missing"

    def test_same_source_offset_no_false_miss(self):
        """expected 用 _pin_offset_map 同源：name-bridge 场景不假 miss。

        旧逻辑用简化 css 查找（css.get('1') = (-50,0)）重算 expected →
        coord(body+(75,0)) ≠ expected → 假 miss；新逻辑用 Pass 1 实际
        解析偏移 (75,0) → 命中。
        """
        w = _writer_with_css()
        # chips.prt 名桥：引脚号 1 → 功能名 FUNC_A；实际解析偏移 (75,0)。
        w._prop_offset_cache["pinmap:MYIC"] = {"1": "FUNC_A"}
        w._pin_offset_map["U1.1"] = (75, 0)
        body = (1000, 1000)
        coord = (1075, 1000)  # body + (75,0) —— 非 css 偏移 (-50,0)
        pin_coords = {"U1.1": coord}
        report = _Report()
        w._aesthetic_report = report

        pre1 = SimpleNamespace(pin_number="1", pin_name="FUNC_A", net_id="N1")
        conn = SimpleNamespace(cells=[])
        page_conn = SimpleNamespace(nets=[])
        lines = w._lastpins_for_instance(
            conn, page_conn, _irec([pre1]), pin_coords, set(),
            body_coord=body,
        )
        assert report.calls == [], f"false miss: {report.calls}"
        assert any(
            f"LASTPIN ({coord[0]} {coord[1]}) $PN 1" in ln for ln in lines
        ), "pin LASTPIN missing"

    def test_unmapped_pin_still_strict_check(self):
        """无 _pin_offset_map 条目时仍走 css 查找严格校验（不破坏 R3d）。"""
        w = _writer_with_css()
        # U1.1 的 _pin_offset_map 缺失 → 回退 css 查找。
        w._pin_offset_map["U1.2"] = (50, 0)
        body = (1000, 1000)
        pin_coords = {
            "U1.1": (950, 1000),   # body + (-50,0) = css 命中 → 正常发射
            "U1.2": (1100, 1000),  # body + (100,0) ≠ css (50,0) → miss
        }
        report = _Report()
        w._aesthetic_report = report

        pre1 = SimpleNamespace(pin_number="1", pin_name="1", net_id="N1")
        pre2 = SimpleNamespace(pin_number="2", pin_name="2", net_id="N2")
        conn = SimpleNamespace(cells=[])
        page_conn = SimpleNamespace(nets=[])
        lines = w._lastpins_for_instance(
            conn, page_conn, _irec([pre1, pre2]), pin_coords, set(),
            body_coord=body,
        )
        # U1.1 发射；U1.2 未命中 → 报 miss 且跳过发射。
        assert any("LASTPIN (950 1000) $PN 1" in ln for ln in lines)
        assert any(c["pin"] == "2" for c in report.calls), "U1.2 miss not reported"
        assert not any("LASTPIN (1100 1000)" in ln for ln in lines)
