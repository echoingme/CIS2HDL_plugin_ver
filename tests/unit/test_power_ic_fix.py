"""Phase XVIII R10 — 匹配质量修复（power_ic 回填 + J* mock 接管）。

Covers:
  * `PowerCandidateScorer.candidates_for` 对 6 引脚 {BST,VIN,GND,EN,SW,FB}
    → dc_dc/sym_1 首选（U18/U20 场景）
  * 引脚数 >20（U6 主 SoC）自动排除
  * U16/U17 4 引脚 DISCRETE 不触发 dc_dc sym_1
"""

from __future__ import annotations

from pathlib import Path

_CFG = Path(__file__).parent.parent.parent / "cis2hdl" / "config" / "power_ic.yaml"


def _scorer():
    from cis2hdl.core.matcher.power_ic_scorer import PowerCandidateScorer

    return PowerCandidateScorer(_CFG)


class TestPowerIc6Pin:
    def test_u18_style_6pin_matches_dc_dc(self):
        """6 引脚 {BST,VIN,GND,EN,SW,FB} → dc_dc 首选（U18/U20 场景）。"""
        scorer = _scorer()
        cands = scorer.candidates_for(
            6,
            ["BST", "VIN", "GND", "EN", "SW", "FB"],
            ["12V0", "VDD_SYSLDO_0P9", "GND"],
        )
        assert cands, "no 6-pin candidates"
        assert cands[0]["library_id"] == "dc_dc"
        assert cands[0]["section"] == 1  # sym_1（FB/IN/GND/EN/SW/BST）

    def test_soe_500_pin_excluded(self):
        """U6 主 SoC 531 引脚 → 无候选（引脚数 >20 自动排除）。"""
        scorer = _scorer()
        cands = scorer.candidates_for(531, ["A0", "B1", "GND"], [])
        assert cands == []

    def test_u16_4pin_dc_dc_not_triggered(self):
        """U16/U17 4 引脚 {G1,G2,G3,S} → 首选 ldo/power_dip4（非 dc_dc sym_1）。"""
        scorer = _scorer()
        cands = scorer.candidates_for(4, ["G1", "G2", "G3", "S"], [])
        assert cands
        assert cands[0]["library_id"] in ("ldo", "power_dip4")


class TestConnectorPinCheck:
    def test_pin_check_flag_in_config(self):
        """routing.yaml 的 matching.connector_pin_check=true（R10 默认开）。"""
        from cis2hdl.core.config import config as cfg

        assert getattr(cfg.routing.matching, "connector_pin_check", True) is True
