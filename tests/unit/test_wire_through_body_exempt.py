"""Phase XXII T01 — WIRE_THROUGH_BODY 自身引脚引出豁免（D2）。

Covers:
  * 穿体段端点 = 该 body 所属实例引脚坐标 → 豁免（exempt=True, reason=self-pin）
  * 电源符号挂轨（小体 outline）→ 豁免（reason=power_symbol）
  * 穿其他元件体的段仍计数（防误豁免）
  * aesthetic_report [WIRE_THROUGH_BODY] 输出 detected/exempt/violations 三口径
"""

from __future__ import annotations

from pathlib import Path


class TestWireThroughBodyExempt:
    def test_self_pin_lead_exempt(self):
        """自身引脚引出段 → (True, "self-pin")（段端点 ∈ 该 body 引脚坐标）。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter

        outline_map = {"U1": (50, 50, 200, 200)}
        pin_coords = {"U1.1": (100, 100), "U1.2": (150, 150)}
        # seg 端点 (100,100) ∈ U1 引脚坐标 → 自身引出 → 豁免。
        seg = (100, 100, 100, 300)
        assert CSAWriter._wire_through_body_exempt(
            seg, outline_map["U1"], outline_map, pin_coords,
        ) == (True, "self-pin")

    def test_power_symbol_hangrail_exempt(self):
        """电源网挂轨穿小体 → (True, "power_symbol")；非电源网小体不豁免。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter

        # 小体 outline（电源符号 GND 等）且无引脚归属 → power_symbol 豁免。
        outline_map = {"GND_SYM": (100, 100, 150, 150)}
        pin_coords = {}
        assert CSAWriter._wire_through_body_exempt(
            (125, 125, 125, 400), outline_map["GND_SYM"],
            outline_map, pin_coords, net_display="GND\\g",
        ) == (True, "power_symbol")
        # 非电源网穿小体 → 不豁免（防误豁免真实小元件）。
        assert CSAWriter._wire_through_body_exempt(
            (125, 125, 125, 400), outline_map["GND_SYM"],
            outline_map, pin_coords, net_display="SIG_A",
        ) == (False, "")

    def test_through_other_body_not_exempt(self):
        """穿其他元件体（段端点不属于该 body）→ (False, "")（仍计数）。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter

        # U1 引脚在 (100,100)；body U2 在 (300,300)-(400,400)，穿过它的
        # 段端点来自 U1 引脚（且 ≠ U2 自身引脚）→ 不是 U2 自身引出 → 真违规。
        outline_map = {"U1": (50, 50, 200, 200), "U2": (300, 300, 400, 400)}
        pin_coords = {"U1.1": (100, 100), "U2.1": (350, 350)}
        seg = (100, 100, 350, 380)  # 终点 (350,380) ≠ U2.1 (350,350)
        assert CSAWriter._wire_through_body_exempt(
            seg, outline_map["U2"], outline_map, pin_coords,
        ) == (False, "")

    def test_body_not_in_map_not_exempt(self):
        """outline 不在映射表 → 无法归属 → 不豁免（保守计数）。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter

        outline_map = {"U1": (50, 50, 200, 200)}
        pin_coords = {"U1.1": (100, 100)}
        assert CSAWriter._wire_through_body_exempt(
            (100, 100, 100, 300), (999, 999, 1100, 1100),
            outline_map, pin_coords,
        ) == (False, "")

    def test_seg_on_trunk(self):
        """Phase XXIII R-2：trunk 线段判定（水平/垂直 trunk 信息）。"""
        from cis2hdl.core.writer.csa_writer import CSAWriter

        # 水平 trunk y=200：同 y 水平段在 trunk 上。
        assert CSAWriter._seg_on_trunk((100, 200, 300, 200), (200, True))
        # 垂直段（stub）不在 trunk 上。
        assert not CSAWriter._seg_on_trunk((100, 200, 100, 300), (200, True))
        # 垂直 trunk x=200：同 x 垂直段在 trunk 上。
        assert CSAWriter._seg_on_trunk((200, 100, 200, 300), (200, False))
        # 水平段不在垂直 trunk 上。
        assert not CSAWriter._seg_on_trunk((100, 200, 300, 200), (200, False))

    def test_trunk_blocked_reason_in_report(self):
        """Phase XXIII R-2：violations 分项统计 trunk_blocked / non_trunk。"""
        from cis2hdl.core.writer.aesthetic_report import AestheticReport

        report = AestheticReport(enabled=True, project_name="T")
        # 1 条 trunk 无解回退（reason=trunk_blocked，非豁免）+ 1 条非 trunk。
        report.add_wire_through_body(
            1, "GND\\g", (100, 100, 500, 100), (50, 50, 200, 200),
            exempt=False, reason="trunk_blocked",
        )
        report.add_wire_through_body(
            1, "SIG_A", (100, 100, 500, 100), (300, 300, 400, 400),
        )
        out = Path("/tmp") / "phasexxiii_wtb_report"
        out.mkdir(parents=True, exist_ok=True)
        report.write(out)
        text = (out / "aesthetic_report.txt").read_text(encoding="utf-8")
        assert (
            "[WIRE_THROUGH_BODY] detected=2 exempt=0 violations=2 "
            "(trunk_blocked=1, non_trunk=1)" in text
        ), text
        assert "reason=trunk_blocked" in text


class TestReportExemptCounting:
    def test_report_counts_exempt_only(self):
        """write 输出 detected/exempt/violations 三口径。"""
        from cis2hdl.core.writer.aesthetic_report import AestheticReport

        report = AestheticReport(enabled=True, project_name="T")
        # 1 个真违规 + 1 个豁免。
        report.add_wire_through_body(1, "NET_A", (0, 0, 0, 100), (10, 10, 20, 20))
        report.add_wire_through_body(
            1, "NET_A", (100, 100, 100, 300), (50, 50, 200, 200),
            exempt=True, reason="self-pin",
        )
        out = Path("/tmp") / "phasexxii_wtb_report"
        out.mkdir(parents=True, exist_ok=True)
        report.write(out)
        text = (out / "aesthetic_report.txt").read_text(encoding="utf-8")
        assert "[WIRE_THROUGH_BODY] detected=2 exempt=1 violations=1" in text, text
        assert "exempt=self-pin" in text
        assert "自身引脚引出段" in text

    def test_all_exempt_shows_violations_zero(self):
        """全部豁免 → violations=0。"""
        from cis2hdl.core.writer.aesthetic_report import AestheticReport

        report = AestheticReport(enabled=True, project_name="T")
        report.add_wire_through_body(
            1, "GND", (100, 100, 100, 300), (50, 50, 200, 200),
            exempt=True, reason="power_symbol",
        )
        out = Path("/tmp") / "phasexxii_wtb_report2"
        out.mkdir(parents=True, exist_ok=True)
        report.write(out)
        text = (out / "aesthetic_report.txt").read_text(encoding="utf-8")
        assert "[WIRE_THROUGH_BODY] detected=1 exempt=1 violations=0" in text, text
        assert "exempt=power_symbol" in text

    def test_empty_shows_none(self):
        from cis2hdl.core.writer.aesthetic_report import AestheticReport

        report = AestheticReport(enabled=True, project_name="T")
        out = Path("/tmp") / "phasexxii_wtb_report3"
        out.mkdir(parents=True, exist_ok=True)
        report.write(out)
        text = (out / "aesthetic_report.txt").read_text(encoding="utf-8")
        assert "[WIRE_THROUGH_BODY] none" in text, text
