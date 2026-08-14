"""Phase XIV T7 — D4 电源芯片匹配评分（power_ic_scorer.py）。

Covers:
  * 6 引脚实例（IN/GND/EN/FB/SW/BST 网含 3v3）→ dc_dc sym_1 score≥0.80
  * 4 引脚（VIN/GND/VOUT+EN）→ ldo 候选
  * 主 SoC（引脚数 > max_pin_count）→ 不触发
  * 低分 → 不覆盖（best_auto 返回 None）
  * extract_pin_names_from_pstxnet 从 pstxnet.dat 提取引脚名
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "cis2hdl" / "config" / "power_ic.yaml"
PSTXNET = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "HG5015test" / "pstxnet.dat"


class TestPowerCandidateScorer:
    def test_6pin_dcdc_auto(self):
        from cis2hdl.core.matcher.power_ic_scorer import PowerCandidateScorer

        scorer = PowerCandidateScorer(CONFIG)
        best = scorer.best_auto(
            6,
            pin_names=["BOOT", "VIN", "GND", "EN", "SW", "FB"],
            connected_nets=["12V0", "GND", "$8N253845"],
        )
        assert best is not None
        assert best["library_id"] == "dc_dc"
        assert best["section"] == 1
        assert best["score"] >= 0.80

    def test_4pin_ldo_candidates(self):
        from cis2hdl.core.matcher.power_ic_scorer import PowerCandidateScorer

        scorer = PowerCandidateScorer(CONFIG)
        cands = scorer.candidates_for(
            4,
            pin_names=["VIN", "GND", "VOUT", "EN"],
            connected_nets=["3V3", "GND"],
        )
        assert cands
        assert cands[0]["library_id"] in ("ldo", "power_dip4", "dc_dc")
        assert cands[0]["pins"] == 4

    def test_soc_excluded(self):
        from cis2hdl.core.matcher.power_ic_scorer import PowerCandidateScorer

        scorer = PowerCandidateScorer(CONFIG)
        assert scorer.best_auto(531, pin_names=["A1"], connected_nets=["VDD"]) is None

    def test_low_score_no_auto(self):
        from cis2hdl.core.matcher.power_ic_scorer import PowerCandidateScorer

        scorer = PowerCandidateScorer(CONFIG)
        # 引脚数不在候选表 → 无候选 → None
        assert scorer.best_auto(17, pin_names=[], connected_nets=[]) is None

    def test_candidates_by_pin_count_loaded(self):
        from cis2hdl.core.matcher.power_ic_scorer import PowerCandidateScorer

        scorer = PowerCandidateScorer(CONFIG)
        assert scorer.candidates_for(6, [], [])  # 6 引脚候选存在


class TestExtractPinNames:
    def test_extract_u1(self):
        from cis2hdl.core.matcher.power_ic_scorer import extract_pin_names_from_pstxnet

        if not PSTXNET.exists():
            return
        names = extract_pin_names_from_pstxnet(PSTXNET, "U1")
        upper = {n.upper() for n in names}
        assert {"GND", "VIN", "EN", "SW", "FB", "BOOT", "BST"} & upper, names

    def test_extract_missing_refdes(self):
        from cis2hdl.core.matcher.power_ic_scorer import extract_pin_names_from_pstxnet

        if not PSTXNET.exists():
            return
        assert extract_pin_names_from_pstxnet(PSTXNET, "ZZ99") == []
